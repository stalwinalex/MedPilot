import pytest
import pytest_asyncio
import os
import uuid
from datetime import date, time, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.database import engine, Base
from app.core.security import create_access_token
from app.models.models import Profile, Subject, Exam, ClassOccurrence, Attendance
from app.services.pdf_service import PDFService
from app.agent.orchestrator import MedPilotAgentOrchestrator


@pytest_asyncio.fixture(autouse=True)
async def init_test_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "MedPilot"


@pytest.mark.asyncio
async def test_auth_and_profile_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register student
        unique_email = f"dr_ananya_{uuid.uuid4().hex[:8]}@aiims.edu"
        reg_payload = {
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Dr. Ananya Sharma",
            "college": "All India Institute of Medical Sciences",
            "year_of_study": "MBBS 2nd Year"
        }
        res_reg = await ac.post("/api/auth/register", json=reg_payload)
        assert res_reg.status_code == 200
        reg_data = res_reg.json()
        assert "access_token" in reg_data
        assert reg_data["user"]["email"] == unique_email
        token = reg_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check me
        res_me = await ac.get("/api/auth/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["full_name"] == "Dr. Ananya Sharma"

        # Update profile
        res_upd = await ac.put("/api/auth/me", headers=headers, json={"target_attendance_percentage": 80.0})
        assert res_upd.status_code == 200
        assert res_upd.json()["target_attendance_percentage"] == 80.0

        # Check subjects automatically seeded
        res_subjs = await ac.get("/api/subjects/", headers=headers)
        assert res_subjs.status_code == 200
        subjs = res_subjs.json()
        assert len(subjs) >= 8
        subj_names = [s["name"] for s in subjs]
        assert "Anatomy" in subj_names
        assert "Pharmacology" in subj_names


from unittest.mock import patch

async def mock_gemini_resp_api(self, system_prompt, user_prompt, history=None, temperature=0.2, image_bytes=None, image_mime=None):
    p = user_prompt.lower()
    if "upper limb" in p:
        return "The upper limb includes the clavicle, humerus, and brachial plexus with roots C5-T1."
    elif "glycolysis" in p:
        return "Glycolysis converts glucose to pyruvate producing net 2 ATP with PFK pathway regulation."
    elif "apoptosis" in p:
        return "Apoptosis is programmed cell death characterized by caspase activation and cytochrome c release."
    return "The cords of the brachial plexus are named according to their relation to the second part of the axillary artery."

async def mock_gemini_json_api(self, system_prompt, user_prompt, schema=None):
    return {
        "recommendation": "Review high-yield anatomy for 45 minutes.",
        "reasoning": "Live academic schedule evaluation.",
        "actions": [{"action_type": "create_task", "label": "Review Anatomy", "payload": {"title": "Anatomy", "estimated_minutes": 45}}]
    }

@pytest.mark.asyncio
@patch("app.agent.llm_provider.GeminiProvider.generate_response", new=mock_gemini_resp_api)
@patch("app.agent.llm_provider.GeminiProvider.generate_json", new=mock_gemini_json_api)
async def test_agent_signature_and_learning_assistant():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create test token
        token = create_access_token({"sub": "student-test-agent", "email": "agent_test@medpilot.io"})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. "What should I do now?" Signature Feature
        res_wsidn = await ac.get("/api/agent/what-should-i-do-now", headers=headers)
        assert res_wsidn.status_code == 200
        wsidn_data = res_wsidn.json()
        assert "reply" in wsidn_data
        assert wsidn_data["agent_name"] == "MedPilot 'What Should I Do Now?' Agent"
        assert len(wsidn_data["recommended_actions"]) > 0
        assert "Educational and academic planning only" in wsidn_data["disclaimer"]

        # 2. AI Learning Assistant
        chat_payload = {
            "message": "Explain the anatomical relations of the brachial plexus cords to the axillary artery.",
            "conversation_history": []
        }
        res_chat = await ac.post("/api/agent/chat", headers=headers, json=chat_payload)
        assert res_chat.status_code == 200
        chat_data = res_chat.json()
        assert "reply" in chat_data
        assert len(chat_data["citations"]) > 0

        # 3. Flexible Study Mode
        study_mode_payload = {
            "duration_minutes": 30,
            "topic": "Upper Limb Nerves & Clinical Lesions"
        }
        res_sm = await ac.post("/api/agent/study-mode", headers=headers, json=study_mode_payload)
        assert res_sm.status_code == 200
        sm_data = res_sm.json()
        assert sm_data["total_minutes"] == 30
        assert len(sm_data["segments"]) == 3


@pytest.mark.asyncio
async def test_pdf_generation_service():
    pdf_path = PDFService.generate_study_resource_pdf(
        title="Cardiac Cycle & Wiggers Diagram High-Yield Notes",
        subject_name="Physiology",
        resource_type="summary",
        content={
            "summary": "The cardiac cycle describes the electrical and mechanical events of the heart from one heartbeat to the next.",
            "key_points": [
                "Isovolumetric contraction: all valves closed, highest oxygen consumption.",
                "S1 heart sound: closure of AV valves (mitral and tricuspid).",
                "S2 heart sound: closure of semilunar valves (aortic and pulmonary)."
            ]
        },
        citations=["Guyton and Hall Medical Physiology 14th Ed."]
    )
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 500


@pytest.mark.asyncio
@patch("app.agent.llm_provider.GeminiProvider.generate_response", new=mock_gemini_resp_api)
@patch("app.agent.llm_provider.GeminiProvider.generate_json", new=mock_gemini_json_api)
async def test_ai_assistant_exact_queries_and_no_internal_server_error():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a registered MBBS student
        email = f"ai_student_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Dr. AI Test Student",
            "college": "KGMU Lucknow",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. "What should I do now?" must NEVER return Internal Server Error
        res_wsidn_get = await ac.get("/api/agent/what-should-i-do-now", headers=headers)
        assert res_wsidn_get.status_code == 200, f"GET failed with {res_wsidn_get.text}"
        data_get = res_wsidn_get.json()
        assert "reply" in data_get
        assert len(data_get["recommended_actions"]) > 0

        res_wsidn_post = await ac.post("/api/agent/what-should-i-do-now", headers=headers)
        assert res_wsidn_post.status_code == 200, f"POST failed with {res_wsidn_post.text}"
        data_post = res_wsidn_post.json()
        assert "reply" in data_post
        assert len(data_post["recommended_actions"]) > 0

        # 2. Query 1: "Explain upper limb briefly."
        q1 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain upper limb briefly.",
            "conversation_history": []
        })
        assert q1.status_code == 200
        d1 = q1.json()

        # 3. Query 2: "What is glycolysis?"
        q2 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "What is glycolysis?",
            "conversation_history": []
        })
        assert q2.status_code == 200
        d2 = q2.json()

        # 4. Query 3: "Give me a 5-mark answer on apoptosis."
        q3 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Give me a 5-mark answer on apoptosis.",
            "conversation_history": []
        })
        assert q3.status_code == 200
        d3 = q3.json()

        # All 3 must give different, relevant answers
        reply1 = d1["reply"]
        reply2 = d2["reply"]
        reply3 = d3["reply"]

        assert reply1 != reply2, "Upper limb and Glycolysis must return different answers"
        assert reply2 != reply3, "Glycolysis and Apoptosis must return different answers"
        assert reply1 != reply3, "Upper limb and Apoptosis must return different answers"

        # Check relevance
        assert any(k in reply1.lower() for k in ["upper limb", "brachial plexus", "humerus", "clavicle", "anatomy"])
        assert any(k in reply2.lower() for k in ["glycolysis", "pyruvate", "glucose", "atp", "pfk", "pathway"])
        assert any(k in reply3.lower() for k in ["apoptosis", "caspase", "programmed cell death", "mitochondrial", "cytochrome c"])

        # With active Gemini provider, source_type is ai_generated
        assert d1["source_type"] == "ai_generated"

        # Check unconfigured mode: when Gemini is not configured, returns clear friendly guide without fake answers
        with patch.object(settings, "GEMINI_API_KEY", ""):
            unconf_q = await ac.post("/api/agent/chat", headers=headers, json={"message": "Explain upper limb", "conversation_history": []})
            unconf_d = unconf_q.json()
            assert unconf_d["source_type"] == "unconfigured"
            assert "Google Gemini AI Assistant Not Configured" in unconf_d["reply"]
            assert "GEMINI_API_KEY" in unconf_d["reply"]

        # References must be subject-appropriate recommended references
        assert any("Anatomy" in r for r in d1["citations"])
        assert any("Biochem" in r for r in d2["citations"])
        assert any("Patholog" in r for r in d3["citations"])

        # 5. Follow-up question with conversation history
        follow_up = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "What is the clinical significance of it?",
            "conversation_history": [
                {"role": "user", "content": "What is glycolysis?"},
                {"role": "assistant", "content": reply2}
            ]
        })
        assert follow_up.status_code == 200
        assert "reply" in follow_up.json()
