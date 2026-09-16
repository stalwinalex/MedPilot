import io
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import engine, Base
from app.models.models import Profile, Subject, Exam, GeneratedResource


@pytest_asyncio.fixture(autouse=True)
async def init_test_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


from unittest.mock import patch

async def mock_gemini_response(self, system_prompt, user_prompt, history=None, temperature=0.2, image_bytes=None, image_mime=None):
    prompt_lower = user_prompt.lower()
    if "upper limb" in prompt_lower:
        return (
            "### Upper Limb Anatomy Overview\n\n"
            "The **upper limb** comprises the pectoral girdle (clavicle and scapula), arm, forearm, and hand. "
            "Innervation is mediated by the **brachial plexus** (nerve roots C5-T1). Important osteology landmarks include the clavicle."
        )
    elif "second point" in prompt_lower or "simply" in prompt_lower:
        return (
            "### Simplified: Brachial Plexus\n\n"
            "Think of the brachial plexus as a nerve tree originating from roots C5-T1 and dividing into trunks."
        )
    elif "summarize" in prompt_lower:
        return "### Document Summary\n\nThis summary covers essential medical curriculum concepts extracted from your notes."
    elif "looking at" in prompt_lower or "explain" in prompt_lower:
        return "### Anatomical Image Analysis\n\nThis anatomical image shows the cross-section of neurovascular structures."
async def mock_gemini_json(self, system_prompt, user_prompt, schema=None):
    return {
        "recommendation": "Dedicate 45 minutes to high-yield revision of Anatomy.",
        "reasoning": "Upcoming exam within 5 days and attendance requirements.",
        "actions": [
            {
                "action_type": "create_task",
                "label": "Schedule 45m Anatomy Review",
                "payload": {"title": "Review Anatomy", "estimated_minutes": 45}
            }
        ]
    }


@pytest.mark.asyncio
@patch("app.agent.llm_provider.GeminiProvider.generate_response", new=mock_gemini_response)
@patch("app.agent.llm_provider.GeminiProvider.generate_json", new=mock_gemini_json)
async def test_all_10_chatgpt_assistant_scenarios():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test medical student
        unique_email = f"dr_aarav_{uuid.uuid4().hex[:8]}@aiims.edu"
        reg_payload = {
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Dr. Aarav Patel",
            "college": "AIIMS New Delhi",
            "year_of_study": "MBBS 1st Year"
        }
        res_reg = await ac.post("/api/auth/register", json=reg_payload)
        assert res_reg.status_code == 200
        token = res_reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # -------------------------------------------------------------
        # SCENARIO 1: "Explain upper limb briefly."
        # -------------------------------------------------------------
        res_1 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain upper limb briefly.",
            "conversation_history": []
        })
        assert res_1.status_code == 200, f"Scenario 1 failed: {res_1.text}"
        data_1 = res_1.json()
        assert "reply" in data_1
        assert any(k in data_1["reply"].lower() for k in ["upper limb", "brachial plexus", "osteology", "clavicle", "anatomy"])
        assert len(data_1["citations"]) > 0
        reply_1 = data_1["reply"]

        # -------------------------------------------------------------
        # SCENARIO 2: "Explain the second point more simply."
        # (Multi-turn conversation context)
        # -------------------------------------------------------------
        res_2 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain the second point more simply.",
            "conversation_history": [
                {"role": "user", "content": "Explain upper limb briefly."},
                {"role": "assistant", "content": reply_1}
            ]
        })
        assert res_2.status_code == 200, f"Scenario 2 failed: {res_2.text}"
        data_2 = res_2.json()
        assert "reply" in data_2
        assert any(k in data_2["reply"].lower() for k in ["brachial plexus", "nerve", "tree", "simply", "roots", "trunk"])

        # -------------------------------------------------------------
        # SCENARIO 3: "Give me 3 good YouTube videos to study upper limb."
        # (Real verified YouTube channels and search links, NO fake IDs)
        # -------------------------------------------------------------
        res_3 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Give me 3 good YouTube videos to study upper limb.",
            "conversation_history": []
        })
        assert res_3.status_code == 200, f"Scenario 3 failed: {res_3.text}"
        data_3 = res_3.json()
        assert data_3["source_type"] == "web_search"
        assert len(data_3["web_sources"]) >= 3
        yt_sources = [s for s in data_3["web_sources"] if s.get("source_type") == "youtube"]
        assert len(yt_sources) >= 3
        # Check verified channels
        assert any("ninja nerd" in s["title"].lower() or "osmosis" in s["title"].lower() for s in yt_sources)
        for s in yt_sources:
            assert "youtube.com" in s["url"]
            assert not s["url"].endswith("watch?v=fake")

        # -------------------------------------------------------------
        # SCENARIO 4: "Search the web for useful upper limb learning resources."
        # -------------------------------------------------------------
        res_4 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Search the web for useful upper limb learning resources.",
            "conversation_history": []
        })
        assert res_4.status_code == 200, f"Scenario 4 failed: {res_4.text}"
        data_4 = res_4.json()
        assert data_4["source_type"] == "web_search"
        assert len(data_4["web_sources"]) > 0
        assert any("ncbi" in s["url"] or "teachmeanatomy" in s["url"] or "youtube" in s["url"] for s in data_4["web_sources"])

        # -------------------------------------------------------------
        # SCENARIO 5: Upload a PDF and ask: "Summarize this."
        # -------------------------------------------------------------
        # Create a simple valid PDF stream with clinical notes
        pdf_content = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length 110>>stream\n"
            b"BT /F1 12 Tf 72 712 Td (Brachial plexus cords surround the axillary artery. Roots are C5-T1.) Tj ET\n"
            b"endstream\nendobj\nxref\n0 5\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n300\n%%EOF"
        )
        files = {"file": ("brachial_plexus_notes.pdf", io.BytesIO(pdf_content), "application/pdf")}
        upload_res = await ac.post("/api/agent/upload", headers=headers, files=files)
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
        upload_data = upload_res.json()
        assert upload_data["file_type"] == "pdf"
        assert "brachial" in upload_data["text_content"].lower() or len(upload_data["text_content"]) > 0

        # Now ask: "Summarize this."
        res_5 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Summarize this.",
            "conversation_history": [],
            "file_attachment": upload_data
        })
        assert res_5.status_code == 200, f"Scenario 5 failed: {res_5.text}"
        data_5 = res_5.json()
        assert data_5["source_type"] == "uploaded_file"
        assert "summary" in data_5["reply"].lower()

        # -------------------------------------------------------------
        # SCENARIO 6: Upload an anatomy image and ask: "Explain what I'm looking at."
        # -------------------------------------------------------------
        # 1x1 dummy PNG bytes
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        img_files = {"file": ("axilla_dissection.png", io.BytesIO(png_bytes), "image/png")}
        img_upload_res = await ac.post("/api/agent/upload", headers=headers, files=img_files)
        assert img_upload_res.status_code == 200, f"Image upload failed: {img_upload_res.text}"
        img_upload_data = img_upload_res.json()
        assert img_upload_data["file_type"] == "image"
        assert img_upload_data["image_url"].startswith("data:image/png;base64,")

        # Now ask: "Explain what I'm looking at."
        res_6 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain what I'm looking at.",
            "conversation_history": [],
            "file_attachment": img_upload_data
        })
        assert res_6.status_code == 200, f"Scenario 6 failed: {res_6.text}"
        data_6 = res_6.json()
        assert data_6["source_type"] == "uploaded_file"
        assert "anatomical" in data_6["reply"].lower() or "image" in data_6["reply"].lower()

        # -------------------------------------------------------------
        # SCENARIO 7: "Create a simple labelled brachial plexus diagram."
        # -------------------------------------------------------------
        res_7 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Create a simple labelled brachial plexus diagram.",
            "conversation_history": []
        })
        assert res_7.status_code == 200, f"Scenario 7 failed: {res_7.text}"
        data_7 = res_7.json()
        assert data_7["source_type"] == "diagram"
        assert data_7["generated_image"] is not None
        assert "data:image/svg+xml;base64," in data_7["generated_image"]["image_url"]
        assert "Brachial Plexus" in data_7["generated_image"]["title"]

        # -------------------------------------------------------------
        # SCENARIO 8: "Make 10 flashcards from this conversation."
        # -------------------------------------------------------------
        res_8 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Make 10 flashcards from this conversation.",
            "conversation_history": [
                {"role": "user", "content": "Explain upper limb briefly."},
                {"role": "assistant", "content": reply_1}
            ]
        })
        assert res_8.status_code == 200, f"Scenario 8 failed: {res_8.text}"
        data_8 = res_8.json()
        assert data_8["source_type"] == "flashcards"
        assert len(data_8["flashcards"]) == 10
        for card in data_8["flashcards"]:
            assert "front" in card and len(card["front"]) > 0
            assert "back" in card and len(card["back"]) > 0
            assert card["difficulty"] in ["easy", "medium", "hard"]

        # -------------------------------------------------------------
        # SCENARIO 9: "Save these flashcards."
        # (Persists in authenticated user's database)
        # -------------------------------------------------------------
        save_payload = {
            "title": "Upper Limb & Brachial Plexus Flashcards",
            "cards": data_8["flashcards"]
        }
        res_9 = await ac.post("/api/agent/flashcards/save", headers=headers, json=save_payload)
        assert res_9.status_code == 200, f"Scenario 9 failed: {res_9.text}"
        data_9 = res_9.json()
        assert data_9["status"] == "success"
        assert data_9["card_count"] == 10
        assert "resource_id" in data_9

        # Verify flashcards retrieve endpoint
        res_saved = await ac.get("/api/agent/flashcards", headers=headers)
        assert res_saved.status_code == 200
        saved_decks = res_saved.json()
        assert len(saved_decks) >= 1
        assert saved_decks[0]["card_count"] == 10

        # -------------------------------------------------------------
        # SCENARIO 10: "What should I study now?"
        # (Retrieves MedPilot live timetable, exams, attendance, wellbeing)
        # -------------------------------------------------------------
        res_10 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "What should I study now?",
            "conversation_history": []
        })
        assert res_10.status_code == 200, f"Scenario 10 failed: {res_10.text}"
        data_10 = res_10.json()
        assert data_10["source_type"] == "student_data"
        assert "reply" in data_10
        assert len(data_10["recommended_actions"]) > 0
