import pytest
import pytest_asyncio
import uuid
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine, Base


@pytest_asyncio.fixture(autouse=True)
async def init_test_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_routine_and_wellbeing_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register student
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Routine Test Student",
            "college": "AIIMS",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Add routine
        today = date.today()
        today_dow = str(today.weekday())

        r1 = await ac.post("/api/habits/", headers=headers, json={
            "name": "Morning Hydration (750ml)",
            "category": "hydration",
            "selected_days": "0,1,2,3,4,5,6",
            "reminder_time": "morning",
            "note": "Drink before clinical posting"
        })
        assert r1.status_code == 200
        r1_id = r1.json()["id"]
        assert r1.json()["name"] == "Morning Hydration (750ml)"

        r2 = await ac.post("/api/habits/", headers=headers, json={
            "name": "Evening 20-min Walk",
            "category": "routine",
            "selected_days": today_dow,
            "reminder_time": "evening",
            "note": "Relax after rounds"
        })
        assert r2.status_code == 200
        r2_id = r2.json()["id"]

        # 3. Fetch today's routines
        today_res = await ac.get("/api/habits/", headers=headers)
        assert today_res.status_code == 200
        today_routines = today_res.json()
        ids = [r["id"] for r in today_routines]
        assert r1_id in ids
        assert r2_id in ids
        assert all(r["today_completed"] is False for r in today_routines)

        # 4. Mark r1 as done
        log_res = await ac.post("/api/habits/log", headers=headers, json={
            "habit_id": r1_id,
            "date": today.isoformat(),
            "status": "completed"
        })
        assert log_res.status_code == 200
        assert log_res.json()["status"] == "completed"

        # Check today's routines again
        today_res2 = await ac.get("/api/habits/", headers=headers)
        today_routines2 = today_res2.json()
        r1_item = next(r for r in today_routines2 if r["id"] == r1_id)
        assert r1_item["today_completed"] is True
        assert r1_item["today_status"] == "completed"

        # 5. Weekly summary
        summary_res = await ac.get("/api/habits/weekly-summary", headers=headers)
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert len(summary["days"]) == 7
        assert summary["total_completed"] >= 1

        # 6. Pause r2
        pause_res = await ac.post(f"/api/habits/{r2_id}/toggle-pause", headers=headers)
        assert pause_res.status_code == 200
        assert pause_res.json()["is_paused"] is True

        # Now r2 should not be in today's active routines
        today_res3 = await ac.get("/api/habits/", headers=headers)
        assert r2_id not in [r["id"] for r in today_res3.json()]

        # But r2 should be in /habits/all
        all_res = await ac.get("/api/habits/all", headers=headers)
        assert r2_id in [r["id"] for r in all_res.json()]

        # 7. Routine Settings
        settings_res = await ac.get("/api/habits/settings", headers=headers)
        assert settings_res.status_code == 200
        assert settings_res.json()["reminders_enabled"] is True

        upd_settings = await ac.put("/api/habits/settings", headers=headers, json={
            "reminders_enabled": True,
            "quiet_hours_enabled": True,
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "06:30",
            "pause_reminders_today": True,
            "avoid_during_classes": True
        })
        assert upd_settings.status_code == 200
        assert upd_settings.json()["quiet_hours_start"] == "23:00"
        assert upd_settings.json()["pause_reminders_today"] is True
        assert upd_settings.json()["avoid_during_classes"] is True

        # 8. History
        hist_res = await ac.get("/api/habits/history", headers=headers)
        assert hist_res.status_code == 200
        assert len(hist_res.json()) >= 1
        assert hist_res.json()[0]["habit_name"] == "Morning Hydration (750ml)"


@pytest.mark.asyncio
async def test_three_routine_statuses_and_summary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register student
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Routine Status Student",
            "college": "KMC Manipal",
            "year_of_study": "MBBS 3rd Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        today = date.today()
        today_str = today.isoformat()

        # Create 3 routines for daily tracking
        r_done = await ac.post("/api/habits/", headers=headers, json={
            "name": "Sleep 7-8 hours",
            "category": "sleep",
            "selected_days": "0,1,2,3,4,5,6"
        })
        assert r_done.status_code == 200
        id_done = r_done.json()["id"]

        r_partly = await ac.post("/api/habits/", headers=headers, json={
            "name": "Hydration 2.5L",
            "category": "hydration",
            "selected_days": "0,1,2,3,4,5,6"
        })
        assert r_partly.status_code == 200
        id_partly = r_partly.json()["id"]

        r_skip = await ac.post("/api/habits/", headers=headers, json={
            "name": "Evening Jog 30 min",
            "category": "routine",
            "selected_days": "0,1,2,3,4,5,6"
        })
        assert r_skip.status_code == 200
        id_skip = r_skip.json()["id"]

        # 1. Mark r_done as 'completed'
        log1 = await ac.post("/api/habits/log", headers=headers, json={
            "habit_id": id_done,
            "date": today_str,
            "status": "completed",
            "notes": "Full 8 hours"
        })
        assert log1.status_code == 200
        assert log1.json()["status"] == "completed"

        # 2. Mark r_partly as 'partial' with amount input (e.g., around half / 1.5L)
        log2 = await ac.post("/api/habits/log", headers=headers, json={
            "habit_id": id_partly,
            "date": today_str,
            "status": "partial",
            "notes": "1.5L (~half)"
        })
        assert log2.status_code == 200
        assert log2.json()["status"] == "partial"
        assert log2.json()["notes"] == "1.5L (~half)"

        # 3. Mark r_skip as 'skipped'
        log3 = await ac.post("/api/habits/log", headers=headers, json={
            "habit_id": id_skip,
            "date": today_str,
            "status": "skipped",
            "notes": "Rainy day"
        })
        assert log3.status_code == 200
        assert log3.json()["status"] == "skipped"

        # 4. Fetch today's routines and verify statuses & notes
        today_habits = await ac.get("/api/habits/", headers=headers)
        assert today_habits.status_code == 200
        habits_map = {h["id"]: h for h in today_habits.json()}

        assert habits_map[id_done]["today_status"] == "completed"
        assert habits_map[id_done]["today_completed"] is True

        assert habits_map[id_partly]["today_status"] == "partial"
        assert habits_map[id_partly]["today_notes"] == "1.5L (~half)"

        assert habits_map[id_skip]["today_status"] == "skipped"

        # 5. Allow changing status later (Done <-> Partly <-> Skip)
        # Change r_done to partial
        change_log = await ac.post("/api/habits/log", headers=headers, json={
            "habit_id": id_done,
            "date": today_str,
            "status": "partial",
            "notes": "6.5 hours"
        })
        assert change_log.status_code == 200
        assert change_log.json()["status"] == "partial"

        # Change r_done back to completed
        change_back = await ac.post("/api/habits/log", headers=headers, json={
            "habit_id": id_done,
            "date": today_str,
            "status": "completed",
            "notes": ""
        })
        assert change_back.status_code == 200
        assert change_back.json()["status"] == "completed"

        # 6. Verify weekly summary distinctions
        summary_res = await ac.get("/api/habits/weekly-summary", headers=headers)
        assert summary_res.status_code == 200
        s_data = summary_res.json()

        assert s_data["total_completed"] >= 1
        assert s_data["total_partial"] >= 1
        assert s_data["total_skipped"] >= 1

        today_summary_day = [d for d in s_data["days"] if d["date"] == today_str][0]
        assert today_summary_day["completed_count"] == 1
        assert today_summary_day["partial_count"] == 1
        assert today_summary_day["skipped_count"] == 1
        # 5 default habits + 3 custom = 8 total routines.
        # Excludes 1 skipped -> 7 active routines.
        # Effective score = 1.0 (completed) + 0.5 (partial) = 1.5. 1.5 / 7.0 = 21.4%
        assert today_summary_day["total_count"] == 8
        assert today_summary_day["percentage"] == 21.4

