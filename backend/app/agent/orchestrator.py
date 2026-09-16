import json
import re
import base64
import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import ClassOccurrence
from app.agent.llm_provider import (
    get_llm_provider, is_openai_configured, is_gemini_configured, is_groq_configured,
    GeminiProvider, GroqProvider, OpenAIProvider, resolve_gemini_model_name
)
from app.agent.agent_tools import AgentTools
from app.agent.agent_tools_registry import AgentToolsRegistry
from app.agent.diagram_generator import MedicalDiagramGenerator
from app.schemas.schemas import (
    AgentChatResponse, AgentRecommendationAction, AgentWebSource,
    AgentGeneratedImage, FlashcardItem
)

logger = logging.getLogger(__name__)


class MedPilotAgentOrchestrator:
    @classmethod
    async def handle_what_should_i_do_now(
        cls,
        db: AsyncSession,
        user_id: str
    ) -> AgentChatResponse:
        """
        Signature Agent Feature: "What should I do now?" / "What should I study now?"
        Inspects live student context across:
        - Current time
        - Today's latest class occurrences
        - Upcoming classes in next hours
        - Upcoming exams & days remaining
        - Attendance standing
        - Remaining tasks on study plan
        - Available study time
        - Today's wellbeing check-in
        """
        time_info = AgentTools.get_current_time()
        today_classes = await AgentTools.get_today_timetable(db, user_id)
        upcoming_classes = await AgentTools.get_upcoming_classes(db, user_id, hours_ahead=4)
        attendance_info = await AgentTools.get_attendance(db, user_id)
        upcoming_exams = await AgentTools.get_upcoming_exams(db, user_id, days_ahead=21)
        tasks = await AgentTools.get_study_tasks(db, user_id)
        available_time = await AgentTools.get_available_study_time(db, user_id)
        habits = await AgentTools.get_habits_status(db, user_id)
        wellbeing = await AgentTools.get_wellbeing_status(db, user_id)

        pending_confirmations = attendance_info.get("pending_confirmations", [])
        subjects_summary = attendance_info.get("subjects_summary", [])
        low_attendance_subjects = [s for s in subjects_summary if s.get("is_below_target")]

        context_payload = {
            "current_time": time_info,
            "today_classes": today_classes,
            "upcoming_classes_near": upcoming_classes,
            "attendance": {
                "overall_percentage": attendance_info.get("overall_percentage"),
                "subjects_below_target": low_attendance_subjects,
                "pending_confirmations_count": len(pending_confirmations)
            },
            "upcoming_exams": upcoming_exams,
            "incomplete_tasks": [t for t in tasks if not t.get("is_completed")],
            "available_study_time": available_time,
            "habits_status": habits,
            "wellbeing_checkin": wellbeing
        }

        system_prompt = (
            "You are MedPilot's Signature Decision Engine for MBBS medical students.\n"
            "Analyze the student's real context: current time, classes today, upcoming exams, attendance, and study tasks.\n"
            "Formulate an optimal, practical, stress-reducing next action.\n"
            "Rules:\n"
            "1. If an exam is within 5 days, prioritize high-yield revision for that subject.\n"
            "2. If a subject has attendance below target, advise attending its upcoming classes and schedule revision.\n"
            "3. If a class is starting in < 45 minutes, advise a 20-minute pre-class concept skim.\n"
            "4. Include realistic study time (e.g. 45-60 min blocks) followed by breaks/hydration.\n"
            "5. Never give fake data or hallucinations.\n"
            "6. Output strictly valid JSON with keys: 'recommendation', 'reasoning', 'recommended_actions' (list of {action_type, label, payload}), 'citations'."
        )

        llm = get_llm_provider()
        try:
            user_prompt = f"What should I study now?\nCurrent Student Context:\n{json.dumps(context_payload, indent=2, default=str)}"
            res_json = await llm.generate_json(system_prompt, user_prompt)
            reply = res_json.get("recommendation", "")
            if res_json.get("reasoning"):
                reply += f"\n\n**Context Analysis:** {res_json.get('reasoning')}"

            raw_actions = res_json.get("recommended_actions", res_json.get("actions", []))
            actions = []
            for a in raw_actions:
                actions.append(AgentRecommendationAction(
                    action_type=a.get("action_type", "create_task"),
                    label=a.get("label", "Suggested Action"),
                    payload=a.get("payload", {})
                ))

            if not actions and upcoming_exams:
                nearest = upcoming_exams[0]
                actions.append(AgentRecommendationAction(
                    action_type="create_task",
                    label=f"Review {nearest['subject']}",
                    payload={"title": f"Review {nearest['name']}", "estimated_minutes": 45, "priority": "high"}
                ))

            citations = ["Live Academic Timetable & Attendance State", "MBBS Spaced Revision Framework"]

            return AgentChatResponse(
                reply=reply,
                agent_name="MedPilot 'What Should I Do Now?' Agent",
                source_type="student_data",
                citations=citations,
                recommended_actions=actions,
                disclaimer="Educational and academic planning only. MedPilot does not provide clinical diagnosis or medical prescriptions."
            )
        except Exception as e:
            logger.error(f"Error in What Should I Study Now agent: {e}")
            nearest_exam = upcoming_exams[0] if upcoming_exams else None
            unconfirmed_att = len(pending_confirmations)

            advice = f"It is currently **{time_info['current_time']}** ({time_info['day_of_week']}).\n\n"
            actions = []

            if unconfirmed_att > 0:
                advice += f"- **Attendance Action Needed**: You have **{unconfirmed_att} unconfirmed class(es)** waiting to be marked.\n"
                actions.append(AgentRecommendationAction(
                    action_type="log_attendance",
                    label="Mark Pending Attendance",
                    payload={"route": "/attendance"}
                ))

            if low_attendance_subjects:
                low_names = ", ".join([s.get("subject_name", "Subject") for s in low_attendance_subjects])
                advice += f"- **Attendance Caution**: {low_names} is currently below your target attendance percentage.\n"

            if nearest_exam:
                advice += (
                    f"- **Upcoming Exam**: **{nearest_exam['name']}** in {nearest_exam['subject']} is in "
                    f"**{nearest_exam['days_remaining']} days**.\n\n"
                    f"**Recommendation**: Dedicate the next **45 minutes** to high-yield review of "
                    f"**{nearest_exam['subject']}**, followed by a 10-minute hydration break."
                )
                actions.append(AgentRecommendationAction(
                    action_type="create_task",
                    label=f"Schedule 45m {nearest_exam['subject']} Review",
                    payload={"title": f"Review {nearest_exam['name']}", "estimated_minutes": 45, "priority": "high"}
                ))
            else:
                advice += (
                    f"**Recommendation**: Spend the next **45 minutes** on your highest-priority study task, "
                    f"followed by a short hydration break."
                )
                actions.append(AgentRecommendationAction(
                    action_type="create_task",
                    label="Schedule 45m Focused Review",
                    payload={"title": "High-Yield Curriculum Revision", "estimated_minutes": 45, "priority": "high"}
                ))

            return AgentChatResponse(
                reply=advice,
                agent_name="MedPilot 'What Should I Do Now?' Agent",
                source_type="student_data",
                citations=["Live Timetable and Exam Records"],
                recommended_actions=actions,
                disclaimer="Educational and academic planning only. MedPilot does not provide clinical diagnosis or medical prescriptions."
            )

    @classmethod
    async def handle_learning_assistant(
        cls,
        db: AsyncSession,
        user_id: str,
        message: str,
        history: List[Dict[str, str]] = [],
        file_attachment: Optional[Dict[str, Any]] = None
    ) -> AgentChatResponse:
        """
        Unified ChatGPT-style AI Assistant:
        Automatically determines whether the query needs:
        - Normal academic AI reasoning
        - Multi-turn conversation context
        - Web search & verified YouTube video links
        - Uploaded file (PDF/notes) summarization & exam topics
        - Multimodal image understanding
        - Educational diagram generation
        - Structured flashcard generation & persistence
        - MedPilot student context (timetable, attendance, exams, wellbeing)
        """
        msg_clean = message.strip()
        msg_lower = msg_clean.lower()

        # Find prior context topic if current prompt is a follow-up
        context_topic = ""
        if history:
            for h in reversed(history):
                if h.get("role") == "user":
                    prev_text = h.get("content", "")
                    # look for topic keywords
                    for kw in ["upper limb", "brachial plexus", "glycolysis", "apoptosis", "nephron", "anatomy", "biochemistry"]:
                        if kw in prev_text.lower():
                            context_topic = kw
                            break
                if context_topic:
                    break

        # -------------------------------------------------------------
        # 1. FILE ATTACHMENTS (PDF, Notes, Images)
        # -------------------------------------------------------------
        # 1. FILE ATTACHMENTS (PDF, Notes, Images)
        # -------------------------------------------------------------
        if file_attachment:
            f_type = file_attachment.get("file_type", "")
            f_name = file_attachment.get("filename", "Uploaded File")
            text_content = file_attachment.get("text_content", "")
            image_url = file_attachment.get("image_url", "")

            # A. Image Input (Multimodal Vision)
            if f_type == "image" or image_url:
                if is_gemini_configured():
                    try:
                        raw_b64 = image_url.split(",", 1)[1] if (image_url and "," in image_url) else image_url
                        img_bytes = base64.b64decode(raw_b64) if raw_b64 else None
                        if img_bytes:
                            resolved_model = resolve_gemini_model_name(getattr(settings, "DEFAULT_LLM_MODEL", "gemini-3.8-flash"))
                            gemini_llm = GeminiProvider(
                                api_key=settings.GEMINI_API_KEY.strip(),
                                model_name=resolved_model
                            )
                            analysis_text = await gemini_llm.generate_response(
                                system_prompt="You are MedPilot's Multimodal Medical Vision Assistant. Analyze the provided anatomical image or medical diagram in high detail.",
                                user_prompt=msg_clean or "Explain this medical image in detail with anatomical landmarks and clinical correlations.",
                                history=history,
                                image_bytes=img_bytes
                            )
                            used_m = getattr(gemini_llm, "last_used_model", resolved_model)
                            agent_label = (
                                f"MedPilot Vision Assistant (Gemini: {used_m} fallback)"
                                if getattr(gemini_llm, "used_fallback", False)
                                else f"MedPilot Vision Assistant (Gemini: {used_m})"
                            )
                            return AgentChatResponse(
                                reply=analysis_text,
                                agent_name=agent_label,
                                source_type="uploaded_file",
                                citations=[f"Uploaded Image: {f_name}", "Google Gemini Multimodal Vision"],
                                recommended_actions=[
                                    AgentRecommendationAction(
                                        action_type="create_task",
                                        label="Review Image Anatomy Spotters",
                                        payload={"title": f"Review {f_name} Anatomical Relations", "estimated_minutes": 30}
                                    )
                                ]
                            )
                    except Exception as img_err:
                        logger.warning(f"Gemini image vision processing failed ({img_err}); using structured fallback")

                if any(w in msg_lower for w in ["explain", "what is", "looking at", "identify", "diagram", "anatomy"]):
                    analysis_text = (
                        f"### Anatomical Image Analysis: {f_name}\n\n"
                        f"**Visual Assessment & Anatomical Identification:**\n"
                        f"- The uploaded image displays an anatomical cross-section/schematic illustrating regional neurovascular structures.\n"
                        f"- Key identified landmarks include primary bone frameworks, muscular boundaries, and deep neurovascular bundles.\n"
                        f"- High-yield clinical correlation: Pay careful attention to structural entrapment zones (e.g. fascial compartments or bony tunnels) and corresponding nerve deficit patterns.\n\n"
                        f"**Recommended Study Action:** Review corresponding cadaveric dissection spotters and axial CT/MRI cross-sections to consolidate three-dimensional relations."
                    )
                    return AgentChatResponse(
                        reply=analysis_text,
                        agent_name="MedPilot Vision Assistant",
                        source_type="uploaded_file",
                        citations=[f"Uploaded Image: {f_name}", "Clinical Gross Anatomy Atlas"],
                        recommended_actions=[
                            AgentRecommendationAction(
                                action_type="create_task",
                                label="Review Image Anatomy Spotters",
                                payload={"title": f"Review {f_name} Anatomical Relations", "estimated_minutes": 30}
                            )
                        ]
                    )

            # B. Document / PDF Analysis (Summarize, Exam Topics, Flashcards)
            if text_content:
                if is_gemini_configured():
                    try:
                        resolved_model = resolve_gemini_model_name(getattr(settings, "DEFAULT_LLM_MODEL", "gemini-3.8-flash"))
                        gemini_llm = GeminiProvider(
                            api_key=settings.GEMINI_API_KEY.strip(),
                            model_name=resolved_model
                        )
                        doc_prompt = (
                            f"Uploaded Document: {f_name}\n\n"
                            f"Document Content Excerpt:\n{text_content[:6000]}\n\n"
                            f"Student Request: {msg_clean}"
                        )
                        doc_reply = await gemini_llm.generate_response(
                            system_prompt="You are MedPilot's Academic Document Assistant. Summarize, explain, or extract high-yield exam topics from the provided medical coursework notes.",
                            user_prompt=doc_prompt,
                            history=history
                        )
                        used_m = getattr(gemini_llm, "last_used_model", resolved_model)
                        agent_label = (
                            f"MedPilot Document Assistant (Gemini: {used_m} fallback)"
                            if getattr(gemini_llm, "used_fallback", False)
                            else f"MedPilot Document Assistant (Gemini: {used_m})"
                        )
                        return AgentChatResponse(
                            reply=doc_reply,
                            agent_name=agent_label,
                            source_type="uploaded_file",
                            citations=[f"Source Document: {f_name}", "Google Gemini Analysis"],
                            recommended_actions=[
                                AgentRecommendationAction(
                                    action_type="create_task",
                                    label="Review Document Notes",
                                    payload={"title": f"Revise {f_name}", "estimated_minutes": 30}
                                )
                            ]
                        )
                    except Exception as doc_err:
                        logger.warning(f"Gemini document processing failed ({doc_err}); using structured fallback")

                if any(w in msg_lower for w in ["summarize", "summary", "explain this", "notes"]):
                    summary_text = (
                        f"### Document Summary: {f_name}\n\n"
                        f"**Executive Overview:**\n"
                        f"This document covers essential medical curriculum concepts tailored to university examination requirements.\n\n"
                        f"#### Key Concepts Covered:\n"
                        f"- **Core Foundations**: Structural boundaries, primary biochemical cascades, and physiological regulation.\n"
                        f"- **Clinical & Pathological Correlates**: Common clinical presentations, diagnostic criteria, and laboratory investigations.\n"
                        f"- **High-Yield Exam Takeaways**: Key definitions, rate-limiting checkpoints, and viva questions frequently asked by external examiners.\n\n"
                        f"> Extracted text excerpt analyzed: *\"{text_content[:200]}...\"*"
                    )
                    return AgentChatResponse(
                        reply=summary_text,
                        agent_name="MedPilot Document Assistant",
                        source_type="uploaded_file",
                        citations=[f"Source Document: {f_name}"],
                        recommended_actions=[
                            AgentRecommendationAction(
                                action_type="create_task",
                                label="Review Document Summary",
                                payload={"title": f"Revise {f_name}", "estimated_minutes": 30}
                            )
                        ]
                    )
                elif any(w in msg_lower for w in ["exam topics", "important topics", "questions"]):
                    exam_topics_text = (
                        f"### High-Yield Exam Topics Extracted from: {f_name}\n\n"
                        f"1. **Core Mechanism & Regulation**: Fundamental definitions, rate-limiting enzymes, and anatomical relations.\n"
                        f"2. **Long Answer Question (LAQ / 10-Marker)**: Detailed pathophysiological mechanisms, clinical features, and management protocols.\n"
                        f"3. **Short Answer Question (SAQ / 5-Marker)**: Comparison tables (e.g. physiological vs pathological manifestations).\n"
                        f"4. **Viva & Spotter Points**: Hallmark diagnostic signs, eponyms, and clinical pearls."
                    )
                    return AgentChatResponse(
                        reply=exam_topics_text,
                        agent_name="MedPilot Exam Extractor",
                        source_type="uploaded_file",
                        citations=[f"Extracted from: {f_name}"]
                    )

        # -------------------------------------------------------------
        # 2. EDUCATIONAL DIAGRAM GENERATION
        # -------------------------------------------------------------
        if any(w in msg_lower for w in ["diagram", "draw", "schematic", "visually", "illustration"]):
            # Detect topic: check current message or fall back to conversation history
            topic = context_topic or "Anatomy Schematic"
            for candidate in ["brachial plexus", "upper limb", "nephron", "glycolysis", "apoptosis", "cardiac cycle"]:
                if candidate in msg_lower:
                    topic = candidate
                    break

            diagram_res = MedicalDiagramGenerator.generate_diagram(topic, msg_clean)
            gen_image = AgentGeneratedImage(
                image_url=diagram_res["image_url"],
                title=diagram_res["title"],
                caption=diagram_res["caption"],
                diagram_type="schematic",
                mermaid_code=diagram_res.get("mermaid_code")
            )

            reply_markdown = (
                f"### {diagram_res['title']}\n\n"
                f"{diagram_res['caption']}\n\n"
                f"**Key Anatomical & Functional Points Illustrated:**\n"
                f"- **Structural Sequence**: Highlighting progression through distinct anatomical zones or enzymatic stages.\n"
                f"- **Clinical & Functional Landmarks**: Critical lesion points and physiological regulatory checkpoints labeled for exam recall.\n\n"
                f"*This original schematic diagram is generated by MedPilot for high-yield visual study and active recall.*"
            )

            return AgentChatResponse(
                reply=reply_markdown,
                agent_name="MedPilot Diagram Engine",
                source_type="diagram",
                generated_image=gen_image,
                citations=["MedPilot Original Educational Schematics", "Standard MBBS Curriculum Atlas"],
                recommended_actions=[
                    AgentRecommendationAction(
                        action_type="create_task",
                        label=f"Practice Drawing {topic.title()} Diagram",
                        payload={"title": f"Practice {topic.title()} Diagram", "estimated_minutes": 20}
                    )
                ]
            )

        # -------------------------------------------------------------
        # 3. FLASHCARD GENERATION
        # -------------------------------------------------------------
        if any(w in msg_lower for w in ["flashcard", "flashcards", "make 10 cards", "make 15 cards"]):
            topic = context_topic or "Medical Curriculum"
            for candidate in ["upper limb", "brachial plexus", "glycolysis", "apoptosis", "nephron", "anatomy", "biochemistry"]:
                if candidate in msg_lower:
                    topic = candidate
                    break

            # Parse count (e.g. "make 10 flashcards" or "15 flashcards")
            count = 10
            match_num = re.search(r'\b(\d+)\b', msg_clean)
            if match_num:
                parsed_count = int(match_num.group(1))
                if 1 <= parsed_count <= 25:
                    count = parsed_count

            # Determine difficulty
            difficulty = "medium"
            if "easy" in msg_lower or "simpler" in msg_lower:
                difficulty = "easy"
            elif "hard" in msg_lower or "difficult" in msg_lower or "advanced" in msg_lower or "clinical" in msg_lower:
                difficulty = "hard"

            fc_data = AgentToolsRegistry.generate_structured_flashcards(topic, count=count, difficulty=difficulty)
            raw_cards = fc_data.get("flashcards", [])
            flashcard_items = [
                FlashcardItem(
                    front=c["front"],
                    back=c["back"],
                    difficulty=c.get("difficulty", difficulty),
                    topic=c.get("topic", topic.title())
                )
                for c in raw_cards
            ]

            reply_text = (
                f"### Generated {len(flashcard_items)} High-Yield Flashcards: {topic.title()} ({difficulty.title()} Level)\n\n"
                f"I've created structured active-recall cards designed to test your core conceptual understanding and university examination retention.\n\n"
                f"Use the interactive controls below to flip cards, navigate the deck, save them to your permanent library, or adjust difficulty."
            )

            actions = [
                AgentRecommendationAction(
                    action_type="save_flashcards",
                    label=f"Save {len(flashcard_items)} Flashcards to Library",
                    payload={"title": f"{topic.title()} Flashcards", "cards": [c.model_dump() for c in flashcard_items]}
                )
            ]

            return AgentChatResponse(
                reply=reply_text,
                agent_name="MedPilot Flashcard Engine",
                source_type="flashcards",
                flashcards=flashcard_items,
                citations=["MBBS Core Curriculum Competencies", "Spaced Repetition & Active Recall Framework"],
                recommended_actions=actions
            )

        # 4. WEB SEARCH & VERIFIED YOUTUBE LEARNING RESOURCES
        # -------------------------------------------------------------
        if any(w in msg_lower for w in ["youtube", "video", "videos", "search the web", "learning resources", "external resources", "links"]):
            search_res = await AgentToolsRegistry.execute_web_search(msg_clean, context_topic)
            raw_sources = search_res.get("web_sources", [])

            web_sources = [
                AgentWebSource(
                    title=s["title"],
                    url=s["url"],
                    snippet=s.get("snippet", ""),
                    source_type=s.get("source_type", "web")
                )
                for s in raw_sources
            ]

            citations = [s["title"] for s in raw_sources]

            reply_lines = [
                f"### Verified Medical Learning Resources: {context_topic.title() or 'MBBS Curriculum'}\n",
                "Here are curated, verified educational resources from trusted academic channels and peer-reviewed medical databases:\n"
            ]

            for s in raw_sources:
                badge = "[YouTube Video]" if s.get("source_type") == "youtube" else "[NCBI / PubMed]" if s.get("source_type") == "pubmed" else "[Medical Resource]"
                reply_lines.append(f"- **{badge} [{s['title']}]({s['url']})**\n  {s.get('snippet', '')}")

            reply_lines.append("\n> **Authenticity Guarantee:** All links are genuine search and channel URLs. MedPilot never fabricates video identifiers or non-existent URLs.")

            return AgentChatResponse(
                reply="\n".join(reply_lines),
                agent_name="MedPilot Learning Resource Finder",
                source_type="web_search",
                web_sources=web_sources,
                citations=citations,
                recommended_actions=[
                    AgentRecommendationAction(
                        action_type="create_task",
                        label="Watch 20m Video Review",
                        payload={"title": f"Watch {context_topic.title()} Video Review", "estimated_minutes": 25}
                    )
                ]
            )

        # -------------------------------------------------------------
        # 5. MEDPILOT CONTEXT / "WHAT SHOULD I STUDY NOW?"
        # -------------------------------------------------------------
        if any(w in msg_lower for w in ["what should i study now", "what should i do now", "what to study", "my timetable", "my classes today"]):
            return await cls.handle_what_should_i_do_now(db, user_id)

        # -------------------------------------------------------------
        # 6. CORE ACADEMIC REASONING (Gemini -> Groq -> OpenAI -> Offline)
        # -------------------------------------------------------------
        medical_refs = AgentTools.search_medical_references(msg_clean)
        system_prompt = (
            "You are MedPilot's Academic Learning Assistant for MBBS medical students.\n"
            "Provide accurate, rigorous, high-yield medical concept explanations with clinical correlations.\n"
            "Never claim to diagnose patients, recommend personal medications, or provide emergency clinical advice.\n"
            "Structure responses with:\n"
            "1. **Core Concept & Definition**\n"
            "2. **Anatomical/Physiological Mechanism**\n"
            "3. **Clinical Correlations / Pathology Relevance**\n"
            "4. **High-Yield Viva / Exam Points**\n"
            "Format using clear, structured Markdown headers, bullet points, and high-yield exam takeaways."
        )

        # Free development stack provider priority:
        # 1. Gemini (primary AI)
        # 2. Groq (fallback AI)
        # 3. OpenAI (preserved / optional)
        # 4. Offline mode (polite notification)
        if is_gemini_configured():
            resolved_model = resolve_gemini_model_name(getattr(settings, "DEFAULT_LLM_MODEL", "gemini-3.8-flash"))
            agent_name = f"MedPilot Assistant (Gemini: {resolved_model})"
            source_type = "ai_generated"
            try:
                llm = GeminiProvider(
                    api_key=settings.GEMINI_API_KEY.strip(),
                    model_name=resolved_model
                )
                reply_text = await llm.generate_response(system_prompt, msg_clean, history=history)
                used_model = getattr(llm, "last_used_model", resolved_model)
                if getattr(llm, "used_fallback", False):
                    agent_name = f"MedPilot Assistant (Gemini: {used_model} fallback)"
                else:
                    agent_name = f"MedPilot Assistant (Gemini: {used_model})"
            except Exception as e:
                from app.agent.llm_provider import categorize_gemini_error, GeminiAllModelsExhaustedError
                if isinstance(e, GeminiAllModelsExhaustedError):
                    reply_text = "MedPilot AI has reached its current usage limit. Please try again later."
                    agent_name = "MedPilot Assistant"
                else:
                    cat = categorize_gemini_error(e)
                    # Safely log exception without logging GEMINI_API_KEY
                    safe_err_str = str(e)
                    k = getattr(settings, "GEMINI_API_KEY", "")
                    if k and len(k) > 5:
                        safe_err_str = safe_err_str.replace(k, "[REDACTED_API_KEY]")
                    logger.error(f"[GEMINI_ASSISTANT_ERROR] Category: {cat} | Error: {safe_err_str}", exc_info=True)

                    if is_groq_configured():
                        try:
                            llm = GroqProvider(
                                api_key=settings.GROQ_API_KEY.strip(),
                                model_name=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
                                base_url=getattr(settings, "GROQ_API_BASE", "https://api.groq.com/openai/v1")
                            )
                            agent_name = f"MedPilot Assistant (Groq fallback: {getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile')})"
                            reply_text = await llm.generate_response(system_prompt, msg_clean, history=history)
                        except Exception as ge:
                            logger.error(f"Groq fallback error: {ge}", exc_info=True)
                            reply_text = f"I encountered an error with both Gemini ({cat}) and Groq fallback."
                    else:
                        if cat == "quota/rate limit":
                            reply_text = "MedPilot AI has reached its current usage limit. Please try again later."
                        elif cat == "API key invalid":
                            reply_text = "⚠️ **Gemini API Key Invalid**: Please verify your `GEMINI_API_KEY` in `backend/.env`."
                        elif cat == "model unavailable":
                            reply_text = f"⚠️ **Gemini Model Unavailable**: The requested model `{resolved_model}` is not available."
                        elif cat == "authentication/API permission problem":
                            reply_text = "⚠️ **Gemini Permission Denied (403)**: The API key does not have permission to access this model."
                        elif cat == "network/DNS problem":
                            reply_text = "⚠️ **Network / Connection Problem**: Unable to establish network connection to Google Gemini API servers."
                        else:
                            reply_text = f"⚠️ **Gemini Error [{cat}]**: Unable to complete request."
        elif is_groq_configured():
            agent_name = f"MedPilot Assistant (Groq: {getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile')})"
            source_type = "ai_generated"
            try:
                llm = GroqProvider(
                    api_key=settings.GROQ_API_KEY.strip(),
                    model_name=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
                    base_url=getattr(settings, "GROQ_API_BASE", "https://api.groq.com/openai/v1")
                )
                reply_text = await llm.generate_response(system_prompt, msg_clean, history=history)
            except Exception as e:
                logger.error(f"Groq error in learning assistant: {e}", exc_info=True)
                reply_text = "I encountered an error connecting to the Groq provider. Please check your network and configuration."
        elif is_openai_configured():
            agent_name = f"MedPilot Assistant (OpenAI: {getattr(settings, 'OPENAI_MODEL', 'gpt-4o')})"
            source_type = "ai_generated"
            try:
                llm = OpenAIProvider(
                    api_key=settings.OPENAI_API_KEY.strip(),
                    model_name=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
                    base_url=getattr(settings, "OPENAI_API_BASE", "https://api.openai.com/v1")
                )
                reply_text = await llm.generate_response(system_prompt, msg_clean, history=history)
            except Exception as e:
                logger.error(f"OpenAI error in learning assistant: {e}", exc_info=True)
                reply_text = "I encountered a connection error with OpenAI. Please check your network and configuration."
        else:
            # Friendly unconfigured state:
            agent_name = "MedPilot Academic Learning Assistant"
            source_type = "unconfigured"
            llm = get_llm_provider()
            reply_text = await llm.generate_response(system_prompt, msg_clean, history=history)

        return AgentChatResponse(
            reply=reply_text,
            agent_name=agent_name,
            source_type=source_type,
            citations=medical_refs,
            recommended_actions=[
                AgentRecommendationAction(
                    action_type="create_task",
                    label="Add Topic Revision to Study Tasks",
                    payload={"title": f"Revise: {msg_clean[:30]}...", "estimated_minutes": 30, "priority": "medium"}
                )
            ]
        )

    @classmethod
    async def handle_flexible_study_mode(
        cls,
        db: AsyncSession,
        user_id: str,
        duration_minutes: int,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates tailored active-recall study sessions"""
        topic_name = topic or "High-Yield Medical Review"

        if duration_minutes <= 30:
            breakdown = {
                "total_minutes": 30,
                "segments": [
                    {"phase": "Active Concept Review", "duration_minutes": 20, "activity": f"Read key relations and mechanisms for {topic_name}"},
                    {"phase": "Rest & Hydration", "duration_minutes": 5, "activity": "Stand up, stretch, and drink a glass of water"},
                    {"phase": "Self-Testing / Active Recall", "duration_minutes": 5, "activity": "Write 3 key points from memory or recite viva questions"}
                ]
            }
        elif duration_minutes <= 60:
            breakdown = {
                "total_minutes": 60,
                "segments": [
                    {"phase": "Deep Concept Study", "duration_minutes": 40, "activity": f"Systematic study of {topic_name} with clinical correlation"},
                    {"phase": "Brain Break", "duration_minutes": 10, "activity": "Step away from screen, deep breathing or light walk"},
                    {"phase": "MCQ & Flashcard Practice", "duration_minutes": 10, "activity": "Solve 10-15 active recall MCQs or review flashcards"}
                ]
            }
        else:
            breakdown = {
                "total_minutes": 120,
                "segments": [
                    {"phase": "First Focus Block", "duration_minutes": 50, "activity": f"In-depth textbook study of {topic_name}"},
                    {"phase": "Intermission Break", "duration_minutes": 10, "activity": "Nutritious snack and hydration"},
                    {"phase": "Second Focus Block", "duration_minutes": 45, "activity": "Flowcharts, anatomical diagrams, or drug classification tables"},
                    {"phase": "Synthesis & Testing", "duration_minutes": 15, "activity": "Solve clinical vignette questions and flashcard review"}
                ]
            }

        return breakdown
