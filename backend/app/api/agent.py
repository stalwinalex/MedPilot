import os
import uuid
import base64
import zlib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, GeneratedResource, Conversation, ChatMessage
from app.schemas.schemas import (
    AgentChatRequest, AgentChatResponse,
    FlexibleStudyModeRequest, SaveFlashcardsRequest,
    ChatMessageItem, ConversationSummary, ConversationDetail,
    CreateConversationRequest, UpdateConversationRequest
)
from app.agent.orchestrator import MedPilotAgentOrchestrator

router = APIRouter(prefix="/agent", tags=["AI Agent"])


def _extract_text_from_pdf_bytes(data: bytes) -> str:
    """Pure-Python extraction of text from standard and FlateDecode compressed PDF streams"""
    text_chunks = []
    stream_matches = re.findall(b'stream[\r\n]+(.*?)[\r\n]+endstream', data, re.DOTALL)
    for s in stream_matches:
        raw = s
        try:
            raw = zlib.decompress(s)
        except Exception:
            pass

        # String literals: (Text) Tj
        matches = re.findall(rb'\(([^\)]+)\)\s*T[jJ]', raw)
        for m in matches:
            try:
                text_chunks.append(m.decode('latin1', errors='ignore'))
            except Exception:
                pass

        # Array of strings: [(Text) 20 (More)] TJ
        array_matches = re.findall(rb'\[(.*?)\]\s*TJ', raw, re.DOTALL)
        for arr in array_matches:
            inner = re.findall(rb'\(([^\)]+)\)', arr)
            for item in inner:
                try:
                    text_chunks.append(item.decode('latin1', errors='ignore'))
                except Exception:
                    pass

    if not text_chunks:
        # Fallback: extract any ASCII / latin1 textual fragments
        raw_fragments = re.findall(rb'[A-Za-z0-9\s,\.\-\(\):;]{6,}', data)
        text_chunks = [f.decode('latin1', errors='ignore').strip() for f in raw_fragments if f.strip()]

    extracted = ' '.join(text_chunks).strip()
    return extracted or "Extracted medical course notes."


@router.post("/upload")
async def upload_agent_file(
    file: UploadFile = File(...),
    current_user: Profile = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Accepts student study documents, PDFs, and medical images.
    Extracts text from PDFs/documents or encodes images for multimodal vision reasoning.
    """
    filename = file.filename or "uploaded_file"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    content_bytes = await file.read()

    file_id = str(uuid.uuid4())

    if ext in ["png", "jpg", "jpeg", "webp"]:
        mime_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
        b64_img = base64.b64encode(content_bytes).decode("utf-8")
        image_url = f"data:{mime_type};base64,{b64_img}"
        return {
            "file_id": file_id,
            "filename": filename,
            "file_type": "image",
            "text_content": f"Image file: {filename}",
            "image_url": image_url,
            "summary_hint": f"Uploaded medical image ({len(content_bytes)} bytes) ready for visual analysis"
        }

    elif ext == "pdf":
        extracted_text = _extract_text_from_pdf_bytes(content_bytes)
        return {
            "file_id": file_id,
            "filename": filename,
            "file_type": "pdf",
            "text_content": extracted_text,
            "image_url": None,
            "summary_hint": f"Extracted {len(extracted_text)} characters from {filename}"
        }

    else:
        # Plain text, markdown, or notes
        try:
            text_str = content_bytes.decode("utf-8")
        except Exception:
            text_str = content_bytes.decode("latin1", errors="ignore")
        return {
            "file_id": file_id,
            "filename": filename,
            "file_type": "text",
            "text_content": text_str,
            "image_url": None,
            "summary_hint": f"Uploaded text file ({len(text_str)} chars)"
        }


@router.post("/flashcards/save")
async def save_flashcard_deck(
    req: SaveFlashcardsRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Persists generated flashcards to the authenticated user's database.
    """
    cards_payload = [c.model_dump() for c in req.cards]
    resource = GeneratedResource(
        user_id=current_user.id,
        subject_id=req.subject_id,
        title=req.title or "High-Yield Flashcards",
        resource_type="flashcards",
        content_json={"cards": cards_payload},
        source_citations=["MedPilot AI Assistant Active Recall"]
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)

    return {
        "status": "success",
        "resource_id": resource.id,
        "title": resource.title,
        "card_count": len(cards_payload)
    }


@router.get("/flashcards")
async def get_saved_flashcard_decks(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves all flashcard decks saved by the student.
    """
    stmt = (
        select(GeneratedResource)
        .filter(
            GeneratedResource.user_id == current_user.id,
            GeneratedResource.resource_type == "flashcards"
        )
        .order_by(GeneratedResource.created_at.desc())
    )
    decks = (await db.execute(stmt)).scalars().all()
    results = []
    for d in decks:
        cards = d.content_json.get("cards", []) if isinstance(d.content_json, dict) else []
        results.append({
            "id": d.id,
            "title": d.title,
            "card_count": len(cards),
            "cards": cards,
            "created_at": d.created_at.isoformat() if d.created_at else None
        })
    return results


def generate_deterministic_title(message: str, max_length: int = 42) -> str:
    """Creates a clean deterministic title from the first prompt without invoking LLMs"""
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New Conversation"
    cleaned = cleaned[0].upper() + cleaned[1:]
    if len(cleaned) <= max_length:
        return cleaned
    truncated = cleaned[:max_length].rsplit(" ", 1)[0]
    if len(truncated) < 18:
        truncated = cleaned[:max_length]
    return truncated.rstrip(",.-:; ") + "..."


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all conversations for the authenticated student, ordered by most recently active.
    """
    stmt = (
        select(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    res = await db.execute(stmt)
    conversations = res.scalars().all()

    summaries = []
    for c in conversations:
        msg_stmt = (
            select(ChatMessage)
            .filter(ChatMessage.conversation_id == c.id)
            .order_by(ChatMessage.created_at.desc())
        )
        msg_res = await db.execute(msg_stmt)
        messages = msg_res.scalars().all()
        last_msg = messages[0].content if messages else None
        preview = (last_msg[:60] + "...") if (last_msg and len(last_msg) > 60) else last_msg
        summaries.append(ConversationSummary(
            id=c.id,
            user_id=c.user_id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(messages),
            last_message_preview=preview
        ))
    return summaries


@router.post("/conversations", response_model=ConversationSummary)
async def create_conversation(
    req: CreateConversationRequest = CreateConversationRequest(),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly start a new empty conversation.
    """
    conv = Conversation(
        user_id=current_user.id,
        title=req.title or "New Conversation"
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationSummary(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
        last_message_preview=None
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve an existing conversation and all its messages.
    Enforces student isolation (404 if not owned by current user).
    """
    stmt = (
        select(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_stmt = (
        select(ChatMessage)
        .filter(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = (await db.execute(msg_stmt)).scalars().all()

    return ConversationDetail(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            ChatMessageItem(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                model=m.model,
                created_at=m.created_at,
                extra_data=m.extra_data or {}
            )
            for m in messages
        ]
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation and its messages.
    Enforces student isolation (404 if not owned by current user).
    """
    stmt = (
        select(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"status": "deleted", "id": conversation_id}


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
async def update_conversation(
    conversation_id: str,
    req: UpdateConversationRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation title.
    """
    stmt = (
        select(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.title = req.title.strip() or conv.title
    conv.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(conv)
    return ConversationSummary(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )


@router.get("/what-should-i-do-now", response_model=AgentChatResponse)
@router.post("/what-should-i-do-now", response_model=AgentChatResponse)
async def what_should_i_do_now(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Signature MedPilot Agent:
    Evaluates current time, timetable, exams, attendance, and tasks to recommend the next best action.
    """
    response = await MedPilotAgentOrchestrator.handle_what_should_i_do_now(db, current_user.id)
    return response


@router.post("/chat", response_model=AgentChatResponse)
async def learning_assistant_chat(
    req: AgentChatRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    ChatGPT-style AI Assistant:
    - Persists conversation & messages in backend database.
    - Loads historical context from database for multi-turn coherence.
    - Auto-titles conversation deterministically from the first user inquiry.
    - Enforces user isolation per authenticated student.
    """
    conv = None
    if req.conversation_id:
        stmt = (
            select(Conversation)
            .filter(Conversation.id == req.conversation_id, Conversation.user_id == current_user.id)
        )
        conv = (await db.execute(stmt)).scalars().first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    if not conv:
        # Create new conversation with auto-title
        auto_title = generate_deterministic_title(req.message)
        conv = Conversation(
            user_id=current_user.id,
            title=auto_title
        )
        db.add(conv)
        await db.flush()

    # Query prior messages for this conversation from database
    msg_history_stmt = (
        select(ChatMessage)
        .filter(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.created_at.asc())
    )
    db_msgs = (await db.execute(msg_history_stmt)).scalars().all()

    # Update title if it was placeholder and we now have the first message
    if conv.title in ["New Conversation", "New Chat", ""] and not db_msgs:
        conv.title = generate_deterministic_title(req.message)

    # Format history for LLM (last 10 turns)
    history = []
    for m in db_msgs[-10:]:
        history.append({
            "role": m.role,
            "content": m.content
        })

    # If DB had no prior messages but client sent conversation_history, fallback to it
    if not history and req.conversation_history:
        history = req.conversation_history[-10:]

    # Persist the user message
    user_extra = {}
    if req.file_attachment:
        user_extra["file_attachment"] = req.file_attachment

    user_msg = ChatMessage(
        conversation_id=conv.id,
        role="user",
        content=req.message,
        extra_data=user_extra
    )
    db.add(user_msg)
    await db.flush()

    # Run AI Assistant
    response = await MedPilotAgentOrchestrator.handle_learning_assistant(
        db=db,
        user_id=current_user.id,
        message=req.message,
        history=history,
        file_attachment=req.file_attachment
    )

    # Persist assistant response
    asst_extra = {
        "agent_name": response.agent_name,
        "source_type": response.source_type,
        "citations": response.citations or [],
        "web_sources": [w.model_dump() if hasattr(w, "model_dump") else w for w in (response.web_sources or [])],
        "generated_image": response.generated_image.model_dump() if hasattr(response.generated_image, "model_dump") and response.generated_image else response.generated_image,
        "flashcards": [f.model_dump() if hasattr(f, "model_dump") else f for f in (response.flashcards or [])],
        "actions": [a.model_dump() if hasattr(a, "model_dump") else a for a in (response.recommended_actions or [])]
    }

    asst_msg = ChatMessage(
        conversation_id=conv.id,
        role="assistant",
        content=response.reply,
        model=getattr(response, "agent_name", "gemini"),
        extra_data=asst_extra
    )
    db.add(asst_msg)

    # Update conversation updated_at
    conv.updated_at = datetime.utcnow()
    await db.commit()

    # Return response with conversation_id and message_id
    response.conversation_id = conv.id
    response.message_id = asst_msg.id
    return response


@router.post("/study-mode")
async def flexible_study_mode(
    req: FlexibleStudyModeRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Flexible Study Mode:
    Generates tailored 30-minute, 1-hour, or 2-hour active recall study sessions.
    """
    breakdown = await MedPilotAgentOrchestrator.handle_flexible_study_mode(
        db=db,
        user_id=current_user.id,
        duration_minutes=req.duration_minutes,
        topic=req.topic
    )
    return breakdown


@router.get("/before-class/{occurrence_id}")
async def before_class_briefing(
    occurrence_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Before-Class Agent:
    Provides pre-class briefing, key topics, and clinical questions to listen for.
    """
    try:
        return await MedPilotAgentOrchestrator.handle_before_class_briefing(db, current_user.id, occurrence_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/after-class/{occurrence_id}")
async def after_class_debrief(
    occurrence_id: str,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    After-Class Agent:
    Prompts attendance confirmation, asks what topic was taught, and proposes revision.
    """
    try:
        return await MedPilotAgentOrchestrator.handle_after_class_debrief(db, current_user.id, occurrence_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
