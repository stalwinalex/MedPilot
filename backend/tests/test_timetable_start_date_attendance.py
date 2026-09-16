import uuid
import pytest
from datetime import date, time, timedelta, datetime
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_timetable_start_date_prevents_past_occurrences_and_attendance():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Dr. Sarah StartDate",
            "college": "AIIMS New Delhi",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Add Subject: Pathology
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Pathology",
            "code": "PATH",
            "color": "#0D9488",
            "target_attendance": 75.0,
            "faculty": "Dr. Gupta"
        })
        assert subj_res.status_code == 200
        path_subj = subj_res.json()

        # 2. Add Mon-Fri batch timetable created TODAY
        today = date.today()
        # Ensure effective_from defaults to today
        batch_res = await ac.post("/api/timetable/rules/batch", headers=headers, json={
            "day_of_week": 0,  # Monday
            "apply_to_days": [1, 2, 3, 4],  # Tue, Wed, Thu, Fri
            "effective_from": today.isoformat(),
            "slots": [
                {
                    "subject_id": path_subj["id"],
                    "start_time": "09:00:00",
                    "end_time": "10:00:00",
                    "faculty": "Dr. Gupta",
                    "room": "LT-1"
                }
            ]
        })
        assert batch_res.status_code == 200
        rules = batch_res.json()
        assert len(rules) == 5
        for r in rules:
            assert r["effective_from"] == today.isoformat()

        # 3. Query occurrences for the entire current week (Monday to Sunday)
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={monday.isoformat()}&end_date={sunday.isoformat()}", headers=headers)
        assert occs_res.status_code == 200
        occs = occs_res.json()

        # Crucial Requirement: NO occurrences may exist before today!
        for occ in occs:
            occ_date = date.fromisoformat(occ["date"])
            assert occ_date >= today, f"Found occurrence on {occ_date} which is before today {today}!"

        # 4. Check Attendance summary and pending count
        att_classes_res = await ac.get("/api/attendance/classes", headers=headers)
        assert att_classes_res.status_code == 200
        att_classes = att_classes_res.json()

        # Any class ending in the past must only be on or after today
        for c in att_classes.get("ended_classes", []):
            c_date = date.fromisoformat(c["date"])
            assert c_date >= today, f"Ended attendance class on {c_date} predates today {today}!"

        # Pending check-ins should NOT include any unstarted past days
        for p in att_classes.get("pending_classes", []):
            p_date = date.fromisoformat(p["date"])
            assert p_date >= today, f"Pending attendance on {p_date} predates today {today}!"


@pytest.mark.asyncio
async def test_mid_semester_earlier_start_date_and_settings():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Mid-Semester Student",
            "college": "MMC Chennai",
            "year_of_study": "MBBS 3rd Year"
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check default settings
        settings_res = await ac.get("/api/timetable/settings", headers=headers)
        assert settings_res.status_code == 200
        assert settings_res.json()["timetable_start_date"] is None

        # Add Subject
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Microbiology",
            "code": "MICRO",
            "color": "#6366F1"
        })
        micro = subj_res.json()

        # Update timetable settings to 14 days ago (intentional mid-semester backfill)
        past_date = date.today() - timedelta(days=14)
        patch_res = await ac.patch("/api/timetable/settings", headers=headers, json={
            "timetable_start_date": past_date.isoformat()
        })
        assert patch_res.status_code == 200
        assert patch_res.json()["timetable_start_date"] == past_date.isoformat()

        # Create recurring rule with effective_from = past_date
        today = date.today()
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": micro["id"],
            "day_of_week": today.weekday(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "effective_from": past_date.isoformat()
        })
        assert rule_res.status_code == 200
        assert rule_res.json()["effective_from"] == past_date.isoformat()

        # Verify historical occurrences were created back to past_date
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={past_date.isoformat()}&end_date={today.isoformat()}", headers=headers)
        assert occs_res.status_code == 200
        historical_occs = occs_res.json()
        assert len(historical_occs) >= 2, "Expected historical occurrences to be created when student sets mid-semester start date"


@pytest.mark.asyncio
async def test_mid_semester_new_recurring_rule_does_not_backfill():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Mid-Semester Add Rule",
            "college": "GMC Mumbai",
            "year_of_study": "MBBS 1st Year"
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Start date of timetable was 30 days ago
        old_start = date.today() - timedelta(days=30)
        await ac.patch("/api/timetable/settings", headers=headers, json={
            "timetable_start_date": old_start.isoformat()
        })

        # Add Subject
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Biochemistry",
            "code": "BIO",
            "color": "#EC4899"
        })
        bio = subj_res.json()

        # Add a NEW recurring rule added TODAY (effective_from: today)
        today = date.today()
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": bio["id"],
            "day_of_week": today.weekday(),
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "effective_from": today.isoformat()
        })
        assert rule_res.status_code == 200
        assert rule_res.json()["effective_from"] == today.isoformat()

        # Check occurrences for the past 30 days
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={old_start.isoformat()}&end_date={today.isoformat()}", headers=headers)
        assert occs_res.status_code == 200
        all_occs = occs_res.json()
        # None of the new rule's occurrences should exist before today
        rule_id = rule_res.json()["id"]
        for o in all_occs:
            if o.get("rule_id") == rule_id:
                assert date.fromisoformat(o["date"]) >= today, "New rule backfilled into earlier weeks!"


@pytest.mark.asyncio
async def test_legitimate_student_attendance_is_preserved_during_cleanup():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Attendance Preserved",
            "college": "CMC Vellore",
            "year_of_study": "MBBS 2nd Year"
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Forensic Medicine",
            "code": "FMT",
            "color": "#8B5CF6"
        })
        fmt_subj = subj_res.json()

        # Add an extra class 5 days ago and mark attendance as 'present'
        past_5d = date.today() - timedelta(days=5)
        extra_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": fmt_subj["id"],
            "date": past_5d.isoformat(),
            "start_time": "08:00:00",
            "end_time": "09:00:00",
            "faculty": "Dr. Murugan"
        })
        assert extra_res.status_code == 200
        extra_occ = extra_res.json()

        # Mark attendance
        mark_res = await ac.post("/api/attendance/check-in", headers=headers, json={
            "occurrence_id": extra_occ["id"],
            "status": "present",
            "topics": ["Ballistics"]
        })
        assert mark_res.status_code == 200

        # Now set timetable start date to TODAY (later than past_5d)
        today = date.today()
        await ac.patch("/api/timetable/settings", headers=headers, json={
            "timetable_start_date": today.isoformat()
        })

        # Query occurrences for past_5d to verify the student-marked extra class is PRESERVED
        check_res = await ac.get(f"/api/timetable/occurrences?start_date={past_5d.isoformat()}&end_date={today.isoformat()}", headers=headers)
        assert check_res.status_code == 200
        found = [o for o in check_res.json() if o["id"] == extra_occ["id"]]
        assert len(found) == 1, "Legitimate student attendance was deleted during cleanup!"
        assert found[0]["attendance"]["status"] == "present"


@pytest.mark.asyncio
async def test_timetable_import_respects_schedule_starts_from():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Import Student",
            "college": "JIPMER",
            "year_of_study": "MBBS 2nd Year"
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        today = date.today()
        confirm_res = await ac.post("/api/timetable/import/confirm", headers=headers, json={
            "duplicate_mode": "skip",
            "schedule_starts_from": today.isoformat(),
            "items": [
                {
                    "day_of_week": 0,  # Monday
                    "day_name": "Monday",
                    "start_time": "08:00",
                    "end_time": "09:00",
                    "subject_name": "Anatomy",
                    "faculty": "Dr. Rao",
                    "room": "Dissection Hall"
                },
                {
                    "day_of_week": 2,  # Wednesday
                    "day_name": "Wednesday",
                    "start_time": "10:00",
                    "end_time": "11:00",
                    "subject_name": "Physiology",
                    "faculty": "Dr. Sharma",
                    "room": "LH-1"
                }
            ]
        })
        assert confirm_res.status_code == 200
        assert confirm_res.json()["imported_count"] == 2

        # Check profile settings was updated to schedule_starts_from
        settings_res = await ac.get("/api/timetable/settings", headers=headers)
        assert settings_res.status_code == 200
        assert settings_res.json()["timetable_start_date"] == today.isoformat()

        # Query occurrences for the entire week
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={monday.isoformat()}&end_date={sunday.isoformat()}", headers=headers)
        assert occs_res.status_code == 200
        for o in occs_res.json():
            assert date.fromisoformat(o["date"]) >= today, f"Occurrence {o['date']} predates import start date {today}"
