import pytest
import pytest_asyncio
import uuid
from datetime import date, time, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine, Base
from app.models.models import (
    Profile,
    Subject,
    Exam,
    ClassOccurrence,
    Attendance,
    TimetableRule,
    StudyTask,
    StudyPlan,
    Habit,
    WellbeingCheckIn,
)
from app.core.security import get_password_hash


@pytest_asyncio.fixture(autouse=True)
async def init_test_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


async def register_student(ac: AsyncClient, name: str = "Test Student", year: str = "MBBS 1st Year (Pre-clinical)"):
    unique_email = f"user_{uuid.uuid4().hex[:8]}@medpilot.ai"
    password = "SecurePassword123!"
    reg_payload = {
        "email": unique_email,
        "password": password,
        "full_name": name,
        "college": "Test Medical College",
        "year_of_study": year,
    }
    res = await ac.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "email": unique_email,
        "password": password,
        "token": token,
        "user_id": user_id,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_reset_timetable_only():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        student = await register_student(ac, "Timetable Reset Student")
        headers = student["headers"]

        # Fetch default subjects
        res_sub = await ac.get("/api/subjects/", headers=headers)
        assert res_sub.status_code == 200
        subjects = res_sub.json()
        assert len(subjects) > 0
        subject_id = subjects[0]["id"]

        # 1. Create a timetable rule
        rule_payload = {
            "subject_id": subject_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "room": "LT 1",
            "faculty": "Dr. Smith",
        }
        res_rule = await ac.post("/api/timetable/rules", headers=headers, json=rule_payload)
        assert res_rule.status_code == 200, res_rule.text

        # 2. Add an exam (unrelated data that should be kept)
        exam_payload = {
            "subject_id": subject_id,
            "name": "Anatomy Internal Assessment 1",
            "exam_date": (date.today() + timedelta(days=14)).isoformat(),
        }
        res_exam = await ac.post("/api/exams/", headers=headers, json=exam_payload)
        assert res_exam.status_code == 200, res_exam.text

        # Verify timetable rule exists
        rules_res = await ac.get("/api/timetable/rules", headers=headers)
        assert len(rules_res.json()) >= 1

        # 3. Call Reset Timetable
        res_reset = await ac.post("/api/account/reset-timetable", headers=headers)
        assert res_reset.status_code == 200
        data = res_reset.json()
        assert data["success"] is True

        # Verify timetable rules are gone
        rules_res_after = await ac.get("/api/timetable/rules", headers=headers)
        assert len(rules_res_after.json()) == 0

        # Verify subjects and exam are preserved
        subs_after = await ac.get("/api/subjects/", headers=headers)
        assert len(subs_after.json()) == len(subjects)

        exams_after = await ac.get("/api/exams/", headers=headers)
        assert len(exams_after.json()) == 1


@pytest.mark.asyncio
async def test_reset_current_semester():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        student = await register_student(ac, "Semester Reset Student")
        headers = student["headers"]

        res_sub = await ac.get("/api/subjects/", headers=headers)
        subject_id = res_sub.json()[0]["id"]

        # Create timetable rule
        rule_payload = {
            "subject_id": subject_id,
            "day_of_week": 1,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "room": "Dissection Hall",
            "faculty": "Dr. Jones",
        }
        await ac.post("/api/timetable/rules", headers=headers, json=rule_payload)

        # Create an exam
        res_exam = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": subject_id,
            "name": "Mid-Semester Practical",
            "exam_date": (date.today() + timedelta(days=7)).isoformat(),
        })
        assert res_exam.status_code == 200

        # Reset Current Semester
        res_reset = await ac.post("/api/account/reset-semester", headers=headers)
        assert res_reset.status_code == 200
        assert res_reset.json()["success"] is True

        # Timetable rules and exams for current semester should be cleared
        rules_after = await ac.get("/api/timetable/rules", headers=headers)
        assert len(rules_after.json()) == 0

        exams_after = await ac.get("/api/exams/", headers=headers)
        assert len(exams_after.json()) == 0

        # User profile and subjects still exist
        me_res = await ac.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["full_name"] == "Semester Reset Student"


@pytest.mark.asyncio
async def test_reset_all_data():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        student = await register_student(ac, "Full Reset Student")
        headers = student["headers"]

        # 1. Test confirmation validation
        bad_res = await ac.post("/api/account/reset-all", headers=headers, json={"confirm_text": "reset"})
        assert bad_res.status_code == 200

        invalid_res = await ac.post("/api/account/reset-all", headers=headers, json={"confirm_text": "WRONG_KEYWORD"})
        assert invalid_res.status_code == 400
        assert "RESET" in invalid_res.json()["detail"]

        # 2. Add some custom data
        sub_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Forensic Special Topic",
            "code": "FST1",
            "color": "#FF5733",
            "target_attendance": 75.0,
        })
        assert sub_res.status_code == 200

        # 3. Perform full reset
        res_reset = await ac.post("/api/account/reset-all", headers=headers, json={"confirm_text": "RESET"})
        assert res_reset.status_code == 200
        data = res_reset.json()
        assert data["success"] is True

        # User account is still accessible
        me_res = await ac.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == student["email"]

        # Subjects were re-seeded to default MBBS 1st Year subjects (Anatomy, Physiology, Biochemistry)
        subs = (await ac.get("/api/subjects/", headers=headers)).json()
        sub_names = [s["name"] for s in subs]
        assert "Anatomy" in sub_names
        assert "Physiology" in sub_names
        assert "Biochemistry" in sub_names
        assert "Forensic Special Topic" not in sub_names


@pytest.mark.asyncio
async def test_delete_account_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        student = await register_student(ac, "Delete Account Student")
        headers = student["headers"]

        # 1. Test invalid confirmation text
        res_bad_confirm = await ac.post("/api/account/delete", headers=headers, json={
            "confirm_text": "NOPE",
            "password": student["password"]
        })
        assert res_bad_confirm.status_code == 400
        assert "DELETE" in res_bad_confirm.json()["detail"]

        # 2. Test incorrect password
        res_bad_pw = await ac.post("/api/account/delete", headers=headers, json={
            "confirm_text": "DELETE",
            "password": "WrongPassword123"
        })
        assert res_bad_pw.status_code == 401
        assert "password" in res_bad_pw.json()["detail"].lower()

        # 3. Successful account deletion
        res_delete = await ac.post("/api/account/delete", headers=headers, json={
            "confirm_text": "DELETE",
            "password": student["password"]
        })
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True

        # 4. Old token should no longer work
        res_me = await ac.get("/api/auth/me", headers=headers)
        assert res_me.status_code == 401

        # 5. Cannot login anymore
        res_login = await ac.post("/api/auth/login", json={
            "email": student["email"],
            "password": student["password"]
        })
        assert res_login.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        user_a = await register_student(ac, "User A")
        user_b = await register_student(ac, "User B")

        # User A creates a rule
        subs_a = (await ac.get("/api/subjects/", headers=user_a["headers"])).json()
        await ac.post("/api/timetable/rules", headers=user_a["headers"], json={
            "subject_id": subs_a[0]["id"],
            "day_of_week": 2,
            "start_time": "08:00:00",
            "end_time": "09:00:00",
            "room": "Room A",
            "faculty": "Dr. A"
        })

        # User B creates a rule
        subs_b = (await ac.get("/api/subjects/", headers=user_b["headers"])).json()
        await ac.post("/api/timetable/rules", headers=user_b["headers"], json={
            "subject_id": subs_b[0]["id"],
            "day_of_week": 3,
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "room": "Room B",
            "faculty": "Dr. B"
        })

        # Verify both have 1 rule
        assert len((await ac.get("/api/timetable/rules", headers=user_a["headers"])).json()) == 1
        assert len((await ac.get("/api/timetable/rules", headers=user_b["headers"])).json()) == 1

        # User A resets timetable
        res_reset_a = await ac.post("/api/account/reset-timetable", headers=user_a["headers"])
        assert res_reset_a.status_code == 200

        # User A rules are 0, User B rules MUST STILL BE 1
        assert len((await ac.get("/api/timetable/rules", headers=user_a["headers"])).json()) == 0
        rules_b_after = (await ac.get("/api/timetable/rules", headers=user_b["headers"])).json()
        assert len(rules_b_after) == 1
        assert rules_b_after[0]["room"] == "Room B"

        # User A deletes account
        res_del_a = await ac.post("/api/account/delete", headers=user_a["headers"], json={
            "confirm_text": "DELETE",
            "password": user_a["password"]
        })
        assert res_del_a.status_code == 200

        # User B is completely unaffected
        res_me_b = await ac.get("/api/auth/me", headers=user_b["headers"])
        assert res_me_b.status_code == 200
        assert res_me_b.json()["full_name"] == "User B"
        assert len((await ac.get("/api/timetable/rules", headers=user_b["headers"])).json()) == 1
