import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from app.main import app


@pytest.mark.asyncio
async def test_explainable_weighting_and_topic_controls():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        # Register test student
        reg_res = await ac.post("/api/auth/register", json={
            "email": f"test_controls_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Student Controls",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200, reg_res.text
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch subjects
        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        assert len(subjects) >= 2

        s_anat = next((s for s in subjects if "anat" in s["name"].lower()), subjects[0])
        s_biochem = next((s for s in subjects if "biochem" in s["name"].lower()), subjects[1])

        today = date.today()

        # ======================================================================
        # TEST 1: Two subjects with DIFFERENT priorities -> verify time allocation differs
        # ======================================================================
        # Anatomy has an urgent exam tomorrow (high priority/weight)
        await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_anat["id"],
            "name": "Anatomy Pre-Prof",
            "exam_date": (today + timedelta(days=1)).isoformat(),
            "target_score": 85.0,
            "important_topics": ["Brachial Plexus"]
        })
        # Biochemistry has only routine revision (no exam)
        await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_biochem["id"],
            "date": (today - timedelta(days=4)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed"
        })

        # Generate 1-day plan with 2 subjects, total available time = 60 minutes
        res_diff = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"], s_biochem["id"]],
            "planning_style": "balanced"
        })
        assert res_diff.status_code == 200
        data_diff = res_diff.json()
        tasks_diff = data_diff["tasks"]

        # Ensure we have tasks for both subjects
        anat_tasks = [t for t in tasks_diff if t["subject_id"] == s_anat["id"]]
        biochem_tasks = [t for t in tasks_diff if t["subject_id"] == s_biochem["id"]]
        assert len(anat_tasks) >= 1
        assert len(biochem_tasks) >= 1

        anat_mins = sum(t["estimated_minutes"] for t in anat_tasks)
        biochem_mins = sum(t["estimated_minutes"] for t in biochem_tasks)

        # Durations MUST differ because weights differ (Anatomy with exam tomorrow > routine Biochem)
        assert anat_mins != biochem_mins, f"Expected unequal minutes, but got Anat={anat_mins}m, Biochem={biochem_mins}m"
        assert anat_mins > biochem_mins, f"Anatomy with urgent exam ({anat_mins}m) must get more time than routine Biochem ({biochem_mins}m)"
        assert (anat_mins + biochem_mins) == 60

        # Verify planning_score is retained for transparency
        for t in tasks_diff:
            assert t.get("planning_score") is not None
            assert t["planning_score"] > 0

        # ======================================================================
        # TEST 2: Two subjects with TRULY EQUAL weights -> equal allocation is acceptable
        # ======================================================================
        # Register a fresh student with identical subjects
        reg2 = await ac.post("/api/auth/register", json={
            "email": f"test_equal_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Equal",
            "year_of_study": "MBBS 2nd Year"
        })
        token2 = reg2.json()["access_token"]
        h2 = {"Authorization": f"Bearer {token2}"}

        # Create two custom subjects with identical parameters
        s1_res = await ac.post("/api/subjects/", headers=h2, json={
            "name": "Subject Alpha",
            "code": "ALPHA",
            "color": "#72C9BE",
            "target_attendance": 75.0
        })
        s2_res = await ac.post("/api/subjects/", headers=h2, json={
            "name": "Subject Beta",
            "code": "BETA",
            "color": "#72C9BE",
            "target_attendance": 75.0
        })
        s1_id = s1_res.json()["id"]
        s2_id = s2_res.json()["id"]

        # Both have an exam on the exact same date (in 5 days)
        await ac.post("/api/exams/", headers=h2, json={
            "subject_id": s1_id,
            "name": "Alpha Exam",
            "exam_date": (today + timedelta(days=5)).isoformat(),
            "target_score": 80.0
        })
        await ac.post("/api/exams/", headers=h2, json={
            "subject_id": s2_id,
            "name": "Beta Exam",
            "exam_date": (today + timedelta(days=5)).isoformat(),
            "target_score": 80.0
        })

        # Generate 1-day plan with 60 minutes total
        res_eq = await ac.post("/api/planner/generate", headers=h2, json={
            "plan_days": 1,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s1_id, s2_id],
            "planning_style": "balanced"
        })
        assert res_eq.status_code == 200
        tasks_eq = res_eq.json()["tasks"]
        t1 = next(t for t in tasks_eq if t["subject_id"] == s1_id)
        t2 = next(t for t in tasks_eq if t["subject_id"] == s2_id)
        # Genuinely equal weights -> equal 30m / 30m allocation is acceptable and expected
        assert t1["estimated_minutes"] == t2["estimated_minutes"] == 30

        # ======================================================================
        # TEST 3: Missed class with date + multiple topics -> verify date & topics appear
        # ======================================================================
        # Add a missed class on 10 Sept (or 2 days ago) with 3 independent topics
        missed_date = today - timedelta(days=2)
        occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": missed_date.isoformat(),
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "status": "completed"
        })
        occ_id = occ_res.json()["id"]

        # Add 3 topics to this missed class
        top1_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Cardiac Cycle",
            "description": "Ventricular phases"
        })
        top2_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Heart Sounds",
            "description": "S1 and S2 splitting"
        })
        top3_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "ECG Basics",
            "description": "Waves and intervals"
        })
        t1_id = top1_res.json()["id"]
        t2_id = top2_res.json()["id"]
        t3_id = top3_res.json()["id"]

        # Mark absent
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "absent"
        })

        # Check GET /api/planner/missed-topics
        mt_res = await ac.get("/api/planner/missed-topics", headers=headers)
        assert mt_res.status_code == 200
        missed_list = mt_res.json()
        assert len(missed_list) >= 1
        curr_missed = next((m for m in missed_list if m["occurrence_id"] == occ_id), None)
        assert curr_missed is not None
        assert len(curr_missed["topics"]) == 3
        topic_titles = [t["title"] for t in curr_missed["topics"]]
        assert "Cardiac Cycle" in topic_titles
        assert "Heart Sounds" in topic_titles
        assert "ECG Basics" in topic_titles

        # ======================================================================
        # TEST 4: Mark one topic Later -> verify it is not scheduled until snooze expires
        # ======================================================================
        # Snooze "Heart Sounds" until 3 days from now
        snooze_res = await ac.put(f"/api/planner/topics/{t2_id}/status", headers=headers, json={
            "study_status": "later",
            "snooze_days": 3
        })
        assert snooze_res.status_code == 200
        assert snooze_res.json()["study_status"] == "later"
        assert snooze_res.json()["snooze_until"] is not None

        # ======================================================================
        # TEST 5: Mark one topic Skip -> verify it disappears from automatic planning but remains in history
        # ======================================================================
        skip_res = await ac.put(f"/api/planner/topics/{t3_id}/status", headers=headers, json={
            "study_status": "skip",
            "skip_reason": "already_know"
        })
        assert skip_res.status_code == 200
        assert skip_res.json()["study_status"] == "skip"
        assert skip_res.json()["skip_reason"] == "already_know"

        # Verify in history: occurrence still has all 3 topics!
        occ_check = await ac.get(f"/api/timetable/occurrences/{occ_id}", headers=headers)
        assert occ_check.status_code == 200
        assert len(occ_check.json()["topics"]) == 3

        # Generate plan today: Only "Cardiac Cycle" should be included, NOT "Heart Sounds" (Later) or "ECG Basics" (Skip)
        plan_res3 = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"]],
            "planning_style": "priority_aware"
        })
        assert plan_res3.status_code == 200
        tasks3 = plan_res3.json()["tasks"]
        task3_titles = [t["title"] for t in tasks3]

        # Verify Cardiac Cycle is included
        assert any("Cardiac Cycle" in title for title in task3_titles)
        # Verify Heart Sounds is NOT scheduled (snoozed)
        assert not any("Heart Sounds" in title for title in task3_titles)
        # Verify ECG Basics is NOT scheduled (skipped)
        assert not any("ECG Basics" in title for title in task3_titles)

        # Verify task has missed_class_date and compact reason showing class date
        cardiac_task = next(t for t in tasks3 if "Cardiac Cycle" in t["title"])
        assert cardiac_task.get("missed_class_date") is not None
        assert "missed class" in cardiac_task["reason"].lower()
        assert "cardiac cycle" in cardiac_task["reason"].lower()

        # ======================================================================
        # TEST 6: Restore skipped topic -> verify it can be scheduled again
        # ======================================================================
        restore_res = await ac.post(f"/api/planner/topics/{t3_id}/restore", headers=headers)
        assert restore_res.status_code == 200
        assert restore_res.json()["study_status"] == "study"
        assert restore_res.json()["snooze_until"] is None

        # Also restore t2
        await ac.post(f"/api/planner/topics/{t2_id}/restore", headers=headers)

        # Re-generate plan: now restored topics can be scheduled!
        plan_res4 = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"]],
            "planning_style": "priority_aware"
        })
        assert plan_res4.status_code == 200
        task4_titles = [t["title"] for t in plan_res4.json()["tasks"]]
        # Now ECG Basics or Heart Sounds are eligible and scheduled
        assert any("ECG Basics" in title or "Heart Sounds" in title for title in task4_titles)
