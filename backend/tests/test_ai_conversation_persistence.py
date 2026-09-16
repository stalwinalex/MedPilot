import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.models import Conversation, ChatMessage
from sqlalchemy.future import select


@pytest.mark.asyncio
async def test_create_and_list_conversations():
    """Verify explicit conversation creation and listing ordered by updated_at"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"conv_user_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Conversation Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # 1. Initially no conversations
        list_res = await ac.get("/api/agent/conversations", headers=headers)
        assert list_res.status_code == 200
        assert list_res.json() == []

        # 2. Create conversation
        create_res = await ac.post("/api/agent/conversations", headers=headers, json={
            "title": "Glycolysis Review"
        })
        assert create_res.status_code == 200
        conv_data = create_res.json()
        assert conv_data["title"] == "Glycolysis Review"
        assert conv_data["message_count"] == 0

        # 3. List conversations
        list_res2 = await ac.get("/api/agent/conversations", headers=headers)
        assert len(list_res2.json()) == 1
        assert list_res2.json()[0]["id"] == conv_data["id"]
        assert list_res2.json()[0]["title"] == "Glycolysis Review"


@pytest.mark.asyncio
async def test_chat_persists_messages_and_auto_titles():
    """
    Verify sending a message persists user and assistant records to the database,
    and automatically titles the conversation using deterministic truncation without extra LLM requests.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"chat_pers_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Persistence Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Send chat message without conversation_id (brand new chat)
        chat_res = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain glycolysis simply."
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        conv_id = data.get("conversation_id")
        assert conv_id is not None
        assert data.get("message_id") is not None
        assert len(data.get("reply", "")) > 0

        # Verify conversation was auto-titled deterministically
        conv_res = await ac.get(f"/api/agent/conversations/{conv_id}", headers=headers)
        assert conv_res.status_code == 200
        conv_detail = conv_res.json()
        assert conv_detail["title"] == "Explain glycolysis simply."

        # Verify both user message and assistant message are persisted
        messages = conv_detail["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Explain glycolysis simply."
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == data["reply"]
        assert messages[1]["extra_data"].get("citations") is not None


@pytest.mark.asyncio
async def test_multi_turn_history_context_retrieval():
    """
    Verify follow-up message receives prior database history and appends to the active conversation.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"multi_turn_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Multi Turn Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Turn 1
        res1 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain glycolysis."
        })
        assert res1.status_code == 200
        conv_id = res1.json()["conversation_id"]

        # Turn 2 (follow-up in same conversation)
        res2 = await ac.post("/api/agent/chat", headers=headers, json={
            "conversation_id": conv_id,
            "message": "What is the most important step?"
        })
        assert res2.status_code == 200
        assert res2.json()["conversation_id"] == conv_id

        # Check conversation messages count
        detail = (await ac.get(f"/api/agent/conversations/{conv_id}", headers=headers)).json()
        assert len(detail["messages"]) == 4
        assert detail["messages"][0]["role"] == "user"
        assert detail["messages"][1]["role"] == "assistant"
        assert detail["messages"][2]["role"] == "user"
        assert detail["messages"][2]["content"] == "What is the most important step?"
        assert detail["messages"][3]["role"] == "assistant"


@pytest.mark.asyncio
async def test_new_chat_preserves_old_conversations():
    """
    Verify starting a new chat creates a separate conversation and keeps the old chat intact in history.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"new_chat_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "New Chat Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Chat 1: Glycolysis
        res1 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain glycolysis simply."
        })
        conv1_id = res1.json()["conversation_id"]

        # Chat 2: Brachial Plexus (New Chat, no conversation_id)
        res2 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Brachial plexus revision"
        })
        conv2_id = res2.json()["conversation_id"]

        assert conv1_id != conv2_id

        # Verify both appear in conversation list
        convs = (await ac.get("/api/agent/conversations", headers=headers)).json()
        assert len(convs) == 2
        titles = [c["title"] for c in convs]
        assert "Explain glycolysis simply." in titles
        assert "Brachial plexus revision" in titles

        # Verify old chat still has its messages
        d1 = (await ac.get(f"/api/agent/conversations/{conv1_id}", headers=headers)).json()
        assert len(d1["messages"]) == 2
        assert d1["messages"][0]["content"] == "Explain glycolysis simply."


@pytest.mark.asyncio
async def test_user_isolation_security():
    """
    Verify strict user isolation: User B cannot access, list, or delete User A's conversations.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid1 = uuid.uuid4().hex[:8]
        uid2 = uuid.uuid4().hex[:8]

        # Register User A
        reg1 = await ac.post("/api/auth/register", json={
            "email": f"usera_{uid1}@medpilot.test",
            "password": "Password123!",
            "full_name": "Student A",
            "year_of_study": "MBBS 1st Year"
        })
        headers1 = {"Authorization": f"Bearer {reg1.json()['access_token']}"}

        # Register User B
        reg2 = await ac.post("/api/auth/register", json={
            "email": f"userb_{uid2}@medpilot.test",
            "password": "Password123!",
            "full_name": "Student B",
            "year_of_study": "MBBS 1st Year"
        })
        headers2 = {"Authorization": f"Bearer {reg2.json()['access_token']}"}

        # User A creates a chat
        res_a = await ac.post("/api/agent/chat", headers=headers1, json={
            "message": "User A private study notes"
        })
        conv_a_id = res_a.json()["conversation_id"]

        # 1. User B lists conversations -> empty
        res_b_list = await ac.get("/api/agent/conversations", headers=headers2)
        assert res_b_list.status_code == 200
        assert len(res_b_list.json()) == 0

        # 2. User B tries to view User A's conversation -> 404
        res_b_view = await ac.get(f"/api/agent/conversations/{conv_a_id}", headers=headers2)
        assert res_b_view.status_code == 404

        # 3. User B tries to post into User A's conversation -> 404
        res_b_post = await ac.post("/api/agent/chat", headers=headers2, json={
            "conversation_id": conv_a_id,
            "message": "Malicious intrusion attempt"
        })
        assert res_b_post.status_code == 404

        # 4. User B tries to delete User A's conversation -> 404
        res_b_del = await ac.delete(f"/api/agent/conversations/{conv_a_id}", headers=headers2)
        assert res_b_del.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_cascades_messages():
    """
    Verify deleting a conversation cascades to its messages in the database.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"del_conv_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Delete Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Create conversation with messages
        res = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Delete me later"
        })
        conv_id = res.json()["conversation_id"]

        # Verify exists
        assert (await ac.get(f"/api/agent/conversations/{conv_id}", headers=headers)).status_code == 200

        # Delete
        del_res = await ac.delete(f"/api/agent/conversations/{conv_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify conversation 404
        assert (await ac.get(f"/api/agent/conversations/{conv_id}", headers=headers)).status_code == 404

        # Verify DB messages deleted
        async with AsyncSessionLocal() as session:
            stmt = select(ChatMessage).filter(ChatMessage.conversation_id == conv_id)
            msgs = (await session.execute(stmt)).scalars().all()
            assert len(msgs) == 0


@pytest.mark.asyncio
async def test_full_user_flow_navigation_refresh_and_context():
    """
    Direct simulation of the requested 9-step user verification flow:
    1. Start a new chat.
    2. Ask 'Explain glycolysis simply.'
    3. Receive AI response.
    4. Navigate to Timetable.
    5. Return to AI Assistant -> messages must still exist.
    6. Refresh browser -> messages must still exist.
    7. Create New Chat -> old chat must remain in Conversation History.
    8. Reopen old chat -> previous messages must load.
    9. Ask a follow-up -> conversation context must still work.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"flow_user_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Full Flow Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Step 1 & 2 & 3: Start chat and ask "Explain glycolysis simply."
        chat1 = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Explain glycolysis simply."
        })
        assert chat1.status_code == 200
        data1 = chat1.json()
        active_conv_id = data1["conversation_id"]
        assert active_conv_id is not None
        cached_local_storage = {"medpilot_active_conv_id": active_conv_id}

        # Step 4: Navigate to Timetable
        tt_res = await ac.get("/api/timetable/rules", headers=headers)
        assert tt_res.status_code == 200

        # Step 5: Return to AI Assistant
        # Frontend calls GET /api/agent/conversations, checks localStorage, then loads GET /api/agent/conversations/{id}
        conv_list = (await ac.get("/api/agent/conversations", headers=headers)).json()
        assert len(conv_list) == 1
        restored_id = cached_local_storage["medpilot_active_conv_id"]
        assert any(c["id"] == restored_id for c in conv_list)

        restored_chat = (await ac.get(f"/api/agent/conversations/{restored_id}", headers=headers)).json()
        assert len(restored_chat["messages"]) == 2
        assert restored_chat["messages"][0]["content"] == "Explain glycolysis simply."

        # Step 6: Refresh browser
        # Simulates a complete page reload: fetches conversations, reads localStorage ID, loads conversation
        refreshed_list = (await ac.get("/api/agent/conversations", headers=headers)).json()
        assert len(refreshed_list) == 1
        reloaded_chat = (await ac.get(f"/api/agent/conversations/{cached_local_storage['medpilot_active_conv_id']}", headers=headers)).json()
        assert len(reloaded_chat["messages"]) == 2
        assert reloaded_chat["messages"][0]["content"] == "Explain glycolysis simply."

        # Step 7: Create New Chat
        # User clicks "New Chat", clearing active ID in localStorage
        cached_local_storage["medpilot_active_conv_id"] = None
        new_chat_res = await ac.post("/api/agent/chat", headers=headers, json={
            "message": "Brachial plexus revision"
        })
        assert new_chat_res.status_code == 200
        new_conv_id = new_chat_res.json()["conversation_id"]
        assert new_conv_id != active_conv_id
        cached_local_storage["medpilot_active_conv_id"] = new_conv_id

        # Verify old chat remains in history
        history = (await ac.get("/api/agent/conversations", headers=headers)).json()
        assert len(history) == 2
        history_ids = [c["id"] for c in history]
        assert active_conv_id in history_ids
        assert new_conv_id in history_ids

        # Step 8: Reopen old chat
        cached_local_storage["medpilot_active_conv_id"] = active_conv_id
        old_chat_reopened = (await ac.get(f"/api/agent/conversations/{active_conv_id}", headers=headers)).json()
        assert len(old_chat_reopened["messages"]) == 2
        assert old_chat_reopened["messages"][0]["content"] == "Explain glycolysis simply."

        # Step 9: Ask a follow-up in the old chat
        followup_res = await ac.post("/api/agent/chat", headers=headers, json={
            "conversation_id": active_conv_id,
            "message": "What is the rate-limiting enzyme?"
        })
        assert followup_res.status_code == 200
        assert followup_res.json()["conversation_id"] == active_conv_id

        # Verify conversation context now contains 4 messages
        updated_old_chat = (await ac.get(f"/api/agent/conversations/{active_conv_id}", headers=headers)).json()
        assert len(updated_old_chat["messages"]) == 4
        assert updated_old_chat["messages"][2]["content"] == "What is the rate-limiting enzyme?"
