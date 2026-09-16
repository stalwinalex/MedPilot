import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, GeneratedResource, PYQAnalysis, Subject
from app.schemas.schemas import (
    ResourceGenerateRequest, GeneratedResourceResponse,
    PYQAnalyzeRequest, PYQAnalysisResponse
)
from app.agent.llm_provider import get_llm_provider
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/resources", tags=["Study Resources & PYQ"])


@router.get("/", response_model=List[GeneratedResourceResponse])
async def get_resources(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(GeneratedResource)
        .options(selectinload(GeneratedResource.subject))
        .filter(GeneratedResource.user_id == current_user.id)
        .order_by(GeneratedResource.created_at.desc())
    )
    resources = (await db.execute(stmt)).scalars().all()
    return resources


@router.post("/generate", response_model=GeneratedResourceResponse)
async def generate_resource(
    req: ResourceGenerateRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch subject name if provided
    subject_name = "General MBBS"
    if req.subject_id:
        subj_stmt = select(Subject).filter(Subject.id == req.subject_id, Subject.user_id == current_user.id)
        subj = (await db.execute(subj_stmt)).scalars().first()
        if subj:
            subject_name = subj.name

    system_prompt = (
        f"You are MedPilot's Study Resource Generator for MBBS students in {subject_name}.\n"
        f"Generate a high-yield, structured {req.resource_type.replace('_', ' ')} for topic: '{req.topic}'.\n"
        "Rules:\n"
        "- If 'summary' or 'revision_sheet' or 'study_notes': return JSON with 'title', 'summary', 'key_points' (list), 'citations' (list).\n"
        "- If 'flashcards': return JSON with 'title', 'cards' (list of {front, back}), 'citations' (list).\n"
        "- If 'mcq_bank': return JSON with 'title', 'questions' (list of {question, options, correct_answer, explanation}), 'citations' (list).\n"
        "- Prefer standard authoritative references (Gray's, Guyton, Robbins, KDT). Never invent references."
    )
    user_prompt = f"Topic: {req.topic}\nAdditional instructions: {req.additional_instructions}"

    llm = get_llm_provider()
    content_json = await llm.generate_json(system_prompt, user_prompt)
    title = content_json.get("title", f"{req.topic} {req.resource_type.title()}")
    citations = content_json.get("citations", ["Standard MBBS Approved Curriculum"])

    # Generate academic PDF
    pdf_path = PDFService.generate_study_resource_pdf(
        title=title,
        subject_name=subject_name,
        resource_type=req.resource_type,
        content=content_json,
        citations=citations
    )

    resource = GeneratedResource(
        user_id=current_user.id,
        subject_id=req.subject_id,
        title=title,
        resource_type=req.resource_type,
        content_json=content_json,
        pdf_storage_path=pdf_path,
        source_citations=citations
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)

    refreshed_stmt = select(GeneratedResource).options(selectinload(GeneratedResource.subject)).filter(GeneratedResource.id == resource.id)
    return (await db.execute(refreshed_stmt)).scalars().first()


@router.get("/{resource_id}/download")
async def download_resource_pdf(
    resource_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(GeneratedResource).filter(GeneratedResource.id == resource_id)
    res = (await db.execute(stmt)).scalars().first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Verify authorization: owner or recipient of shared resource
    if res.user_id != current_user.id:
        from app.models.models import SharedResource
        shared_stmt = select(SharedResource).filter(
            SharedResource.resource_id == resource_id,
            SharedResource.receiver_id == current_user.id
        )
        shared = (await db.execute(shared_stmt)).scalars().first()
        if not shared:
            raise HTTPException(status_code=403, detail="Not authorized to download this resource")

    if not res.pdf_storage_path or not os.path.exists(res.pdf_storage_path):
        # Regenerate PDF on the fly if missing
        subj_name = "Medical Resource"
        if res.subject_id:
            subj = (await db.execute(select(Subject).filter(Subject.id == res.subject_id))).scalars().first()
            if subj:
                subj_name = subj.name
        new_pdf = PDFService.generate_study_resource_pdf(
            title=res.title,
            subject_name=subj_name,
            resource_type=res.resource_type,
            content=res.content_json,
            citations=res.source_citations or []
        )
        res.pdf_storage_path = new_pdf
        await db.commit()

    safe_title = "".join(c for c in res.title if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")
    return FileResponse(
        res.pdf_storage_path,
        media_type="application/pdf",
        filename=f"MedPilot_{safe_title}.pdf"
    )


@router.post("/pyq", response_model=PYQAnalysisResponse)
async def analyze_pyq(
    req: PYQAnalyzeRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Previous-Year Question (PYQ) Analysis:
    Extracts repeated topics, frequently tested concepts, question patterns, and high-yield areas.
    """
    system_prompt = (
        "You are MedPilot's Previous-Year Question (PYQ) Analyzer for medical examinations.\n"
        "Analyze the provided examination questions.\n"
        "Identify:\n"
        "1. Repeated topics and frequency\n"
        "2. High-yield concept clusters\n"
        "3. Common question patterns (e.g. clinical vignette, direct definition, comparative table)\n"
        "4. Practical study guidance notes (without falsely claiming guaranteed appearance).\n"
        "Output strictly valid JSON with keys: 'topic_frequencies' (list of {topic, frequency, yield_level}), 'repeated_patterns' (list of {pattern, description}), 'high_yield_topics' (list of strings), 'guidance_notes' (string)."
    )
    user_prompt = f"Exam: {req.exam_name}\nYears: {req.years_covered}\nQuestions:\n{req.raw_questions}"

    llm = get_llm_provider()
    analysis_data = await llm.generate_json(system_prompt, user_prompt)

    pyq = PYQAnalysis(
        user_id=current_user.id,
        subject_id=req.subject_id,
        exam_name=req.exam_name,
        years_covered=req.years_covered,
        topic_frequencies=analysis_data.get("topic_frequencies", []),
        repeated_patterns=analysis_data.get("repeated_patterns", []),
        high_yield_topics=analysis_data.get("high_yield_topics", []),
        guidance_notes=analysis_data.get("guidance_notes", "Focus on clinical correlations and frequently tested anatomical landmarks.")
    )
    db.add(pyq)
    await db.commit()
    await db.refresh(pyq)

    refreshed_stmt = select(PYQAnalysis).options(selectinload(PYQAnalysis.subject)).filter(PYQAnalysis.id == pyq.id)
    return (await db.execute(refreshed_stmt)).scalars().first()
