import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from app.main import app


@pytest.mark.asyncio
async def test_edit_study_task_details_and_persistence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_edit_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Edit Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch subjects
        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        assert len(subjects) >= 2
        s1 = subjects[0]
        s2 = subjects[1]

        today = date.today()

        # Create a study task
        create_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "subject_id": s1["id"],
            "title": "Initial Anatomy Reading",
            "priority": "medium",
            "estimated_minutes": 45,
            "scheduled_date": today.isoformat(),
            "description": "Read chapter 1"
        })
        assert create_res.status_code == 200
        task_id = create_res.json()["id"]

        # 1. Edit task: update title, duration, priority, subject, and description
        edit_payload = {
            "title": "Inguinal Canal & Hernia Boundaries",
            "subject_id": s2["id"],
            "estimated_minutes": 60,
            "priority": "high",
            "description": "Focus on deep ring vs superficial ring"
        }
        edit_res = await ac.put(f"/api/planner/tasks/{task_id}", headers=headers, json=edit_payload)
        assert edit_res.status_code == 200
        updated_data = edit_res.json()

        assert updated_data["title"] == "Inguinal Canal & Hernia Boundaries"
        assert updated_data["subject_id"] == s2["id"]
        assert updated_data["estimated_minutes"] == 60
        assert updated_data["priority"] == "high"
        assert updated_data["description"] == "Focus on deep ring vs superficial ring"

        # 2. Verify persistence after fresh fetch (refresh)
        list_res = await ac.get("/api/planner/tasks", headers=headers)
        assert list_res.status_code == 200
        tasks = list_res.json()
        persisted_task = next((t for t in tasks if t["id"] == task_id), None)
        assert persisted_task is not None
        assert persisted_task["title"] == "Inguinal Canal & Hernia Boundaries"
        assert persisted_task["subject_id"] == s2["id"]
        assert persisted_task["estimated_minutes"] == 60
        assert persisted_task["priority"] == "high"
        assert persisted_task["description"] == "Focus on deep ring vs superficial ring"


@pytest.mark.asyncio
async def test_reschedule_task_preserves_task_without_duplication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_move_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Move Student",
            "year_of_study": "MBBS 1st Year"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.get("/api/subjects/", headers=headers)
        s1 = subj_res.json()[0]
        today = date.today()

        # Create task scheduled for today
        create_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "subject_id": s1["id"],
            "title": "Brachial Plexus Branches",
            "priority": "high",
            "estimated_minutes": 45,
            "scheduled_date": today.isoformat(),
            "description": "Original scheduled task"
        })
        assert create_res.status_code == 200
        original_task_id = create_res.json()["id"]

        # Move/Reschedule to 3 days from now
        new_date = today + timedelta(days=3)
        resched_res = await ac.put(f"/api/planner/tasks/{original_task_id}", headers=headers, json={
            "scheduled_date": new_date.isoformat()
        })
        assert resched_res.status_code == 200
        resched_data = resched_res.json()

        # Verify same task ID, new date
        assert resched_data["id"] == original_task_id
        assert resched_data["scheduled_date"] == new_date.isoformat()

        # Verify no duplicate task was created
        all_tasks_res = await ac.get("/api/planner/tasks", headers=headers)
        all_tasks = all_tasks_res.json()
        assert len(all_tasks) == 1
        assert all_tasks[0]["id"] == original_task_id
        assert all_tasks[0]["scheduled_date"] == new_date.isoformat()


@pytest.mark.asyncio
async def test_delete_study_task_lifecycle_and_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        # Student A
        reg_a = await ac.post("/api/auth/register", json={
            "email": f"test_del_a_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Student A",
            "year_of_study": "MBBS 1st Year"
        })
        token_a = reg_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Student B
        reg_b = await ac.post("/api/auth/register", json={
            "email": f"test_del_b_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Student B",
            "year_of_study": "MBBS 1st Year"
        })
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        subj_res = await ac.get("/api/subjects/", headers=headers_a)
        s1 = subj_res.json()[0]
        today = date.today()

        # Create Task 1 and Task 2 for Student A
        t1_res = await ac.post("/api/planner/tasks", headers=headers_a, json={
            "subject_id": s1["id"],
            "title": "Task 1 To Delete",
            "priority": "low",
            "estimated_minutes": 30,
            "scheduled_date": today.isoformat()
        })
        t1_id = t1_res.json()["id"]

        t2_res = await ac.post("/api/planner/tasks", headers=headers_a, json={
            "subject_id": s1["id"],
            "title": "Task 2 To Keep",
            "priority": "medium",
            "estimated_minutes": 45,
            "scheduled_date": today.isoformat()
        })
        t2_id = t2_res.json()["id"]

        # Student B cannot delete Student A's task (isolation check)
        cross_del = await ac.delete(f"/api/planner/tasks/{t1_id}", headers=headers_b)
        assert cross_del.status_code == 404

        # Student A deletes Task 1
        del_res = await ac.delete(f"/api/planner/tasks/{t1_id}", headers=headers_a)
        assert del_res.status_code == 200

        # Verify only Task 1 is deleted, Task 2 is preserved
        remaining_res = await ac.get("/api/planner/tasks", headers=headers_a)
        remaining = remaining_res.json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == t2_id
        assert remaining[0]["title"] == "Task 2 To Keep"
