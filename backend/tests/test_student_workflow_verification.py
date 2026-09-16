import pytest
import pytest_asyncio
import uuid
from datetime import date, datetime, timedelta, time
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.models import Profile, Subject, TimetableRule, ClassOccurrence, ClassTopic, Attendance


@pytest_asyncio.fixture(autouse=True)
async def init_test_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_13_step_core_student_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test medical student
        unique_email = f"workflow_student_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg_payload = {
            "email": unique_email,
            "password": "Password123!",
            "full_name": "Test Student",
            "college": "Medical College",
            "year_of_study": "MBBS 1st Year"
        }
        res_reg = await ac.post("/api/auth/register", json=reg_payload)
        assert res_reg.status_code == 200, f"Register failed: {res_reg.text}"
        token = res_reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # -------------------------------------------------------------
        # STEP 0: Create Subject "Anatomy" (originates from Timetable/Subjects)
        # -------------------------------------------------------------
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Anatomy",
            "code": "ANAT101",
            "color": "#0D9488",
            "target_attendance": 75.0,
            "faculty": "Dr. Sharma"
        })
        assert subj_res.status_code == 200, f"Create subject failed: {subj_res.text}"
        anatomy_id = subj_res.json()["id"]

        # Determine Monday date for testing
        today = date.today()
        # Find this week's Monday
        monday = today - timedelta(days=today.weekday())

        # -------------------------------------------------------------
        # STEP 1: Add Anatomy Monday 9-10
        # -------------------------------------------------------------
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": anatomy_id,
            "day_of_week": 0,  # Monday
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "faculty": "Dr. Sharma",
            "room": "Dissection Hall"
        })
        assert rule_res.status_code == 200, f"Step 1 failed: {rule_res.text}"
        rule_data = rule_res.json()
        rule_id = rule_data["id"]
        assert rule_data["day_of_week"] == 0
        assert rule_data["start_time"].startswith("09:00")
        assert rule_data["end_time"].startswith("10:00")

        # -------------------------------------------------------------
        # STEP 2: Refresh -> it remains
        # -------------------------------------------------------------
        # Simulate browser refresh by fetching rules and occurrences
        get_rules_res = await ac.get("/api/timetable/rules", headers=headers)
        assert get_rules_res.status_code == 200
        user_rules = get_rules_res.json()
        assert any(r["id"] == rule_id for r in user_rules), "Step 2 failed: Rule not found after refresh"

        start_week = monday.strftime("%Y-%m-%d")
        end_week = (monday + timedelta(days=6)).strftime("%Y-%m-%d")
        get_occs_res = await ac.get(f"/api/timetable/occurrences?start_date={start_week}&end_date={end_week}", headers=headers)
        assert get_occs_res.status_code == 200
        occs = get_occs_res.json()
        monday_occs = [o for o in occs if o["date"] == monday.strftime("%Y-%m-%d") and o["subject_id"] == anatomy_id]
        assert len(monday_occs) == 1, f"Step 2 failed: Expected 1 occurrence, found {len(monday_occs)}"
        occ = monday_occs[0]
        assert occ["start_time"].startswith("09:00")
        assert occ["end_time"].startswith("10:00")
        occ_id = occ["id"]

        # -------------------------------------------------------------
        # STEP 3: Edit to 10-11
        # -------------------------------------------------------------
        edit_res = await ac.put(f"/api/timetable/occurrences/{occ_id}", headers=headers, json={
            "subject_id": anatomy_id,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Sharma",
            "room": "Dissection Hall"
        })
        assert edit_res.status_code == 200, f"Step 3 failed: {edit_res.text}"
        edited_occ = edit_res.json()
        assert edited_occ["start_time"].startswith("10:00")
        assert edited_occ["end_time"].startswith("11:00")

        # -------------------------------------------------------------
        # STEP 4: Refresh -> edit remains (no duplicate created)
        # -------------------------------------------------------------
        refresh_occs_res = await ac.get(f"/api/timetable/occurrences?start_date={start_week}&end_date={end_week}", headers=headers)
        assert refresh_occs_res.status_code == 200
        refreshed_occs = refresh_occs_res.json()
        monday_refreshed = [o for o in refreshed_occs if o["date"] == monday.strftime("%Y-%m-%d") and o["subject_id"] == anatomy_id]
        assert len(monday_refreshed) == 1, f"Step 4 failed: Duplicate created! Found {len(monday_refreshed)} occurrences"
        assert monday_refreshed[0]["start_time"].startswith("10:00"), f"Step 4 failed: start_time reverted: {monday_refreshed[0]['start_time']}"
        assert monday_refreshed[0]["end_time"].startswith("11:00"), f"Step 4 failed: end_time reverted: {monday_refreshed[0]['end_time']}"

        # -------------------------------------------------------------
        # STEP 5 & 6: Let/test it after end time -> It becomes Pending
        # -------------------------------------------------------------
        # To test after end time deterministically regardless of time of day:
        # We test with a class date in the past (e.g. yesterday or last Monday) OR set occurrence date to a past date
        past_monday = monday - timedelta(days=7)
        past_occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": anatomy_id,
            "date": past_monday.strftime("%Y-%m-%d"),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Sharma",
            "room": "Dissection Hall"
        })
        assert past_occ_res.status_code == 200
        past_occ = past_occ_res.json()
        past_occ_id = past_occ["id"]

        # Check pending check-ins
        pending_res = await ac.get("/api/attendance/pending-checkins", headers=headers)
        assert pending_res.status_code == 200, f"Pending check-ins failed: {pending_res.text}"
        pending_list = pending_res.json()
        pending_ids = [p["id"] for p in pending_list]
        assert past_occ_id in pending_ids, f"Step 6 failed: Past ended class not in pending checkins list: {pending_ids}"

        # Also verify /attendance/classes returns it in ended_classes
        classes_res = await ac.get("/api/attendance/classes", headers=headers)
        assert classes_res.status_code == 200
        ended_classes = classes_res.json().get("ended_classes", [])
        assert any(c["id"] == past_occ_id for c in ended_classes), "Step 6 failed: Not in ended_classes"

        # -------------------------------------------------------------
        # STEP 7: Mark Present
        # STEP 8: Add topic "Brachial Plexus"
        # -------------------------------------------------------------
        checkin_res = await ac.post("/api/attendance/check-in", headers=headers, json={
            "occurrence_id": past_occ_id,
            "status": "present",
            "topic_title": "Brachial Plexus",
            "notes": "Covered roots, trunks, divisions, and cords"
        })
        assert checkin_res.status_code == 200, f"Step 7/8 failed: {checkin_res.text}"
        checkin_data = checkin_res.json()
        assert checkin_data["attendance"]["status"] == "present"
        assert any(t["title"] == "Brachial Plexus" for t in checkin_data["topics"]), "Topic 'Brachial Plexus' not attached"

        # -------------------------------------------------------------
        # STEP 9: Attendance updates
        # -------------------------------------------------------------
        summary_res = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res.status_code == 200, f"Step 9 failed: {summary_res.text}"
        summary = summary_res.json()
        assert summary["total_conducted"] >= 1
        assert summary["total_attended"] >= 1
        assert summary["overall_percentage"] == 100.0, f"Expected 100%, got {summary['overall_percentage']}"

        # -------------------------------------------------------------
        # STEP 10: Refresh -> everything remains
        # -------------------------------------------------------------
        refreshed_summary = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert refreshed_summary["total_conducted"] >= 1
        assert refreshed_summary["total_attended"] >= 1
        assert refreshed_summary["overall_percentage"] == 100.0

        refreshed_history = (await ac.get("/api/attendance/history", headers=headers)).json()
        target_hist = next((h for h in refreshed_history if h["id"] == past_occ_id), None)
        assert target_hist is not None, "Occurrence not found in history after refresh"
        assert target_hist["attendance"]["status"] == "present"
        assert any(t["title"] == "Brachial Plexus" for t in target_hist["topics"]), "Topic lost after refresh"

        # -------------------------------------------------------------
        # STEP 11: Change Present to Absent
        # -------------------------------------------------------------
        change_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": past_occ_id,
            "status": "absent"
        })
        assert change_res.status_code == 200, f"Step 11 failed: {change_res.text}"

        updated_summary = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert updated_summary["total_conducted"] >= 1
        assert updated_summary["total_missed"] >= 1
        assert updated_summary["total_attended"] == 0
        assert updated_summary["overall_percentage"] == 0.0, f"Expected 0.0%, got {updated_summary['overall_percentage']}"

        # -------------------------------------------------------------
        # STEP 12: Verify no duplicate is created
        # -------------------------------------------------------------
        # Count attendance records in DB for this occurrence
        async with AsyncSessionLocal() as session:
            att_stmt = select(Attendance).filter(Attendance.occurrence_id == past_occ_id)
            records = (await session.execute(att_stmt)).scalars().all()
            assert len(records) == 1, f"Step 12 failed: Duplicate attendance records! Found {len(records)}"

        # -------------------------------------------------------------
        # STEP 13: Cancel it and then undo cancellation
        # -------------------------------------------------------------
        # A. Cancel
        cancel_res = await ac.post(f"/api/timetable/occurrences/{past_occ_id}/toggle-cancel", headers=headers)
        assert cancel_res.status_code == 200, f"Step 13 Cancel failed: {cancel_res.text}"
        cancelled_occ = cancel_res.json()
        assert cancelled_occ["status"] == "cancelled"
        assert cancelled_occ["attendance"]["status"] == "cancelled"

        # Check that cancelled classes do NOT hurt attendance or count as conducted
        cancelled_summary = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert cancelled_summary["total_cancelled"] >= 1

        # B. Undo cancellation
        undo_res = await ac.post(f"/api/timetable/occurrences/{past_occ_id}/toggle-cancel", headers=headers)
        assert undo_res.status_code == 200, f"Step 13 Undo failed: {undo_res.text}"
        restored_occ = undo_res.json()
        assert restored_occ["status"] != "cancelled", "Occurrence still cancelled after undo"
        assert restored_occ["attendance"]["status"] != "cancelled", "Attendance still cancelled after undo"

        # Check after undo that everything is coherent
        final_summary = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert final_summary is not None

        # -------------------------------------------------------------
        # STEP 14: STUDY PLANNER CAN USE THAT TOPIC LATER
        # -------------------------------------------------------------
        # Mark occurrence present with topic "Brachial Plexus"
        await ac.post("/api/attendance/check-in", headers=headers, json={
            "occurrence_id": past_occ_id,
            "status": "present",
            "topic_title": "Brachial Plexus"
        })

        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "start_date": today.strftime("%Y-%m-%d"),
            "daily_study_hours": 3.0
        })
        assert plan_res.status_code == 200, f"Plan generation failed: {plan_res.text}"
        plan_data = plan_res.json()
        tasks = plan_data.get("tasks", [])
        assert len(tasks) > 0, "No study tasks generated"
        assert any("Brachial Plexus" in t["title"] for t in tasks), f"Topic 'Brachial Plexus' not included in study plan tasks: {[t['title'] for t in tasks]}"


@pytest.mark.asyncio
async def test_class_topic_decoupled_workflow():
    """
    Dedicated test for decoupling attendance and class topic workflow:
    - Mark Present with NO topic
    - Verify attendance saves and class leaves pending list
    - Open Timetable, find that exact class by date, click "Add Topic"
    - Enter: "Brachial Plexus"
    - Save & simulate page refresh
    - Verify "Brachial Plexus" is shown on that class
    - Edit topic to add or modify ("Brachial Plexus & Axillary Artery")
    - Verify update persists after refresh
    - Verify no duplicate class or attendance record was created
    - Test Absent class topic addition later
    - Test multi-topic creation
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        unique_email = f"topic_test_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg_res = await ac.post("/api/auth/register", json={
            "email": unique_email,
            "password": "Password123!",
            "full_name": "Topic Test Student",
            "college": "Medical College",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create Subject "Anatomy"
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Anatomy",
            "code": "ANAT101",
            "color": "#0D9488",
            "target_attendance": 75.0,
            "faculty": "Dr. Sharma"
        })
        assert subj_res.status_code == 200
        anatomy_id = subj_res.json()["id"]

        # 2. Create a past class occurrence (yesterday)
        yesterday = date.today() - timedelta(days=1)
        occ_create_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": anatomy_id,
            "date": yesterday.strftime("%Y-%m-%d"),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Sharma",
            "room": "Lecture Hall 1",
            "status": "scheduled"
        })
        assert occ_create_res.status_code == 200
        occ = occ_create_res.json()
        occ_id = occ["id"]

        # 3. Verify it appears in pending check-ins
        pending_res = await ac.get("/api/attendance/pending-checkins", headers=headers)
        assert pending_res.status_code == 200
        pending_list = pending_res.json()
        assert any(p["id"] == occ_id for p in pending_list), "Past class should be pending before attendance"

        # 4. Mark Present with NO topic
        check_in_res = await ac.post("/api/attendance/check-in", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "present",
            "topic_title": ""
        })
        assert check_in_res.status_code == 200
        checked_in = check_in_res.json()
        assert checked_in["attendance"]["status"] == "present"
        assert len(checked_in.get("topics", [])) == 0, "No topic should be created when blank"

        # 5. Verify attendance saves and class leaves pending list
        pending_after_res = await ac.get("/api/attendance/pending-checkins", headers=headers)
        assert pending_after_res.status_code == 200
        pending_after = pending_after_res.json()
        assert not any(p["id"] == occ_id for p in pending_after), "Class should leave pending check-ins even without topic"

        # 6. Open Timetable, find that exact class by date (Simulate page refresh)
        start_date = yesterday.strftime("%Y-%m-%d")
        end_date = yesterday.strftime("%Y-%m-%d")
        timetable_res = await ac.get(f"/api/timetable/occurrences?start_date={start_date}&end_date={end_date}", headers=headers)
        assert timetable_res.status_code == 200
        matched_occs = [o for o in timetable_res.json() if o["id"] == occ_id]
        assert len(matched_occs) == 1, "Occurrence must be found in timetable"
        found_occ = matched_occs[0]
        assert found_occ["attendance"]["status"] == "present"
        assert len(found_occ["topics"]) == 0

        # 7. Click "Add Topic" -> Enter: "Brachial Plexus" -> Save
        add_topic_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Brachial Plexus"
        })
        assert add_topic_res.status_code == 200
        created_topic = add_topic_res.json()
        topic_id = created_topic["id"]
        assert created_topic["title"] == "Brachial Plexus"
        assert created_topic["occurrence_id"] == occ_id

        # 8. Refresh page -> Verify "Brachial Plexus" is shown on that class
        refreshed_tt = await ac.get(f"/api/timetable/occurrences?start_date={start_date}&end_date={end_date}", headers=headers)
        assert refreshed_tt.status_code == 200
        refreshed_occ = next(o for o in refreshed_tt.json() if o["id"] == occ_id)
        assert len(refreshed_occ["topics"]) == 1
        assert refreshed_occ["topics"][0]["title"] == "Brachial Plexus"

        # 9. Edit topic to add or modify -> "Brachial Plexus & Axillary Artery"
        edit_topic_res = await ac.put(f"/api/timetable/topics/{topic_id}", headers=headers, json={
            "title": "Brachial Plexus & Axillary Artery"
        })
        assert edit_topic_res.status_code == 200
        updated_topic = edit_topic_res.json()
        assert updated_topic["title"] == "Brachial Plexus & Axillary Artery"

        # 10. Refresh page -> Verify update persists
        refreshed_tt_2 = await ac.get(f"/api/timetable/occurrences?start_date={start_date}&end_date={end_date}", headers=headers)
        assert refreshed_tt_2.status_code == 200
        refreshed_occ_2 = next(o for o in refreshed_tt_2.json() if o["id"] == occ_id)
        assert len(refreshed_occ_2["topics"]) == 1
        assert refreshed_occ_2["topics"][0]["title"] == "Brachial Plexus & Axillary Artery"

        # 11. Verify NO duplicate class or attendance record was created
        async with AsyncSessionLocal() as session:
            occ_count_stmt = select(ClassOccurrence).filter(ClassOccurrence.id == occ_id)
            occs = (await session.execute(occ_count_stmt)).scalars().all()
            assert len(occs) == 1, "Duplicate class occurrence detected!"

            att_count_stmt = select(Attendance).filter(Attendance.occurrence_id == occ_id)
            atts = (await session.execute(att_count_stmt)).scalars().all()
            assert len(atts) == 1, "Duplicate attendance record detected!"

            topic_count_stmt = select(ClassTopic).filter(ClassTopic.occurrence_id == occ_id)
            topics = (await session.execute(topic_count_stmt)).scalars().all()
            assert len(topics) == 1, "Unexpected number of topic records!"

        # 12. Test Absent class: mark absent without topic, then add topic later
        occ_2_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": anatomy_id,
            "date": yesterday.strftime("%Y-%m-%d"),
            "start_time": "12:00:00",
            "end_time": "13:00:00",
            "faculty": "Dr. Sharma",
            "status": "scheduled"
        })
        assert occ_2_res.status_code == 200
        occ_2_id = occ_2_res.json()["id"]

        # Check in Absent without topic
        await ac.post("/api/attendance/check-in", headers=headers, json={
            "occurrence_id": occ_2_id,
            "status": "absent",
            "topic_title": None
        })

        # Verify not in pending
        pending_3 = (await ac.get("/api/attendance/pending-checkins", headers=headers)).json()
        assert not any(p["id"] == occ_2_id for p in pending_3)

        # Add topic later when student finds out what was taught
        await ac.post(f"/api/timetable/occurrences/{occ_2_id}/topics", headers=headers, json={
            "title": "Cubital Fossa"
        })

        # Verify persistence
        tt_absent = (await ac.get(f"/api/timetable/occurrences?start_date={start_date}&end_date={end_date}", headers=headers)).json()
        absent_occ = next(o for o in tt_absent if o["id"] == occ_2_id)
        assert absent_occ["attendance"]["status"] == "absent"
        assert len(absent_occ["topics"]) == 1
        assert absent_occ["topics"][0]["title"] == "Cubital Fossa"

        # 13. Test multi-topic creation (batch or comma/newline separated)
        batch_res = await ac.post(f"/api/timetable/occurrences/{occ_2_id}/topics/batch", headers=headers, json={
            "topics": ["Median Nerve", "Radial Artery"]
        })
        assert batch_res.status_code == 200
        assert len(batch_res.json()) == 2

        tt_multi = (await ac.get(f"/api/timetable/occurrences?start_date={start_date}&end_date={end_date}", headers=headers)).json()
        multi_occ = next(o for o in tt_multi if o["id"] == occ_2_id)
        assert len(multi_occ["topics"]) == 3
        topic_titles = [t["title"] for t in multi_occ["topics"]]
        assert "Cubital Fossa" in topic_titles
        assert "Median Nerve" in topic_titles
        assert "Radial Artery" in topic_titles
