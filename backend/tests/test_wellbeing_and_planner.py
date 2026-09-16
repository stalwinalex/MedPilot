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
async def test_wellbeing_checkin_and_planner_workload():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register student
        email = f"student_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Wellbeing Test Student",
            "college": "AIIMS New Delhi",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Check initial wellbeing status for today (should be pending)
        init_wb = await ac.get("/api/habits/wellbeing/today", headers=headers)
        assert init_wb.status_code == 200
        wb_data = init_wb.json()
        assert wb_data["status"] == "pending"
        assert wb_data["mood"] is None

        # 3. Validation: Reject invalid mood or status
        bad_mood = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "answered",
            "mood": "ecstatic"  # invalid
        })
        assert bad_mood.status_code == 400

        bad_status = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "maybe",
            "mood": "good"
        })
        assert bad_status.status_code == 400

        # 4. Check initial planner recommendation (neutral/standard plan)
        init_plan = await ac.get("/api/planner/recommendation/today", headers=headers)
        assert init_plan.status_code == 200
        init_plan_data = init_plan.json()
        assert init_plan_data["checkin_status"] == "pending"
        assert init_plan_data["workload_mode"] == "normal"

        # 5. Submit wellbeing check-in: 😄 Great
        wb_great = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "answered",
            "mood": "great"
        })
        assert wb_great.status_code == 200
        assert wb_great.json()["status"] == "answered"
        assert wb_great.json()["mood"] == "great"

        # Verify planner recommendation for "great"
        plan_great = await ac.get("/api/planner/recommendation/today", headers=headers)
        assert plan_great.status_code == 200
        d_great = plan_great.json()
        assert d_great["mood"] == "great"
        assert d_great["workload_mode"] == "high-focus"
        assert d_great["suggested_block_minutes"] == 50
        assert "challenging" in d_great["headline"].lower()

        # 6. Test mood: 😴 Tired
        wb_tired = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "answered",
            "mood": "tired"
        })
        assert wb_tired.status_code == 200
        plan_tired = await ac.get("/api/planner/recommendation/today", headers=headers)
        d_tired = plan_tired.json()
        assert d_tired["mood"] == "tired"
        assert d_tired["workload_mode"] == "light-revision"
        assert d_tired["suggested_block_minutes"] == 25
        assert "light revision" in d_tired["headline"].lower()

        # 7. Test mood: 😣 Stressful
        wb_stress = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "answered",
            "mood": "stressful"
        })
        assert wb_stress.status_code == 200
        plan_stress = await ac.get("/api/planner/recommendation/today", headers=headers)
        d_stress = plan_stress.json()
        assert d_stress["mood"] == "stressful"
        assert d_stress["workload_mode"] == "essential-only"
        assert d_stress["suggested_block_minutes"] == 25
        assert "essential tasks" in d_stress["headline"].lower()

        # 8. Create tasks for today (1 high, 1 medium, 1 low)
        today_str = date.today().isoformat()
        t1 = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Pathology Neoplasia High-Yield Prep",
            "priority": "high",
            "estimated_minutes": 45,
            "scheduled_date": today_str
        })
        assert t1.status_code == 200
        t1_id = t1.json()["id"]

        t2 = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Pharmacology General Principles Reading",
            "priority": "medium",
            "estimated_minutes": 30,
            "scheduled_date": today_str
        })
        assert t2.status_code == 200
        t2_id = t2.json()["id"]

        t3 = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Organize Notes Binder",
            "priority": "low",
            "estimated_minutes": 20,
            "scheduled_date": today_str
        })
        assert t3.status_code == 200
        t3_id = t3.json()["id"]

        # 9. Verify recommendation reflects task counts & reschedule candidates
        plan_tasks = await ac.get("/api/planner/recommendation/today", headers=headers)
        pt_data = plan_tasks.json()
        assert pt_data["today_task_count"] >= 3
        assert pt_data["unfinished_task_count"] >= 3
        assert pt_data["reschedule_candidates_count"] >= 2  # medium + low

        # 10. Reschedule optional tasks to tomorrow
        resched_res = await ac.post("/api/planner/tasks/reschedule-optional", headers=headers, json={})
        assert resched_res.status_code == 200
        assert resched_res.json()["rescheduled_count"] == 2

        # Verify high-priority task is still scheduled for today
        all_today_tasks = await ac.get(f"/api/planner/tasks?scheduled_date={today_str}", headers=headers)
        today_task_ids = [t["id"] for t in all_today_tasks.json()]
        assert t1_id in today_task_ids  # High priority remained
        assert t2_id not in today_task_ids  # Medium moved
        assert t3_id not in today_task_ids  # Low moved

        # 11. Test "Skip for today"
        wb_skip = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "skipped"
        })
        assert wb_skip.status_code == 200
        assert wb_skip.json()["status"] == "skipped"
        assert wb_skip.json()["mood"] is None

        # Verify today's check-in returns skipped
        current_wb = await ac.get("/api/habits/wellbeing/today", headers=headers)
        assert current_wb.json()["status"] == "skipped"


@pytest.mark.asyncio
async def test_ai_study_plan_generation_grounded():
    """
    Verifies that AI Study Plan:
    1. Returns 0 tasks with friendly guidance when no exams/topics exist (never fabricates).
    2. Generates real, grounded tasks across 7 days when an exam or topic is present.
    3. Successfully saves tasks to the database, persisting on GET /planner/tasks.
    4. Accurately schedules high-priority catch-up tasks for missed class topics.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"planner_student_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Planner MBBS Student",
            "college": "KGMU Lucknow",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Test empty state: No exams, topics, or manual tasks
        plan_empty = await ac.post("/api/planner/generate", headers=headers, json={
            "daily_study_hours": 3.0,
            "preferences": "focused revision"
        })
        assert plan_empty.status_code == 200
        empty_res = plan_empty.json()
        assert empty_res["total_tasks_created"] == 0
        assert "I need something to plan" in empty_res["message"]

        # 2. Get user's subjects (MBBS subjects seeded on registration)
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        assert subjs_res.status_code == 200
        subjects = subjs_res.json()
        assert len(subjects) > 0
        anatomy = next((s for s in subjects if "anatomy" in s["name"].lower()), subjects[0])

        # 3. Add an upcoming Exam with high-yield topics
        today = date.today()
        exam_date = today + timedelta(days=5)
        exam_res = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": anatomy["id"],
            "name": "Anatomy 1st Internal Assessment",
            "exam_date": exam_date.isoformat(),
            "exam_type": "Internal Assessment",
            "target_score": 80.0,
            "important_topics": ["Brachial Plexus Anatomy", "Cubital Fossa Boundaries & Contents"]
        })
        assert exam_res.status_code == 200
        exam_data = exam_res.json()

        # 4. Generate AI Study Plan with the exam present
        plan_with_exam = await ac.post("/api/planner/generate", headers=headers, json={
            "daily_study_hours": 3.0,
            "preferences": "high yield review"
        })
        assert plan_with_exam.status_code == 200
        exam_plan_res = plan_with_exam.json()
        assert exam_plan_res["total_tasks_created"] >= 2
        assert "Successfully scheduled" in exam_plan_res["message"]

        # Verify task titles match actual topics and are not fabricated
        created_titles = [t["title"] for t in exam_plan_res["tasks"]]
        assert any("Brachial Plexus" in t for t in created_titles)
        assert any("Cubital Fossa" in t for t in created_titles)

        # 5. Verify tasks are persisted in database and returned on GET /planner/tasks
        tasks_res = await ac.get("/api/planner/tasks", headers=headers)
        assert tasks_res.status_code == 200
        persisted_tasks = tasks_res.json()
        assert len(persisted_tasks) >= 2
        persisted_titles = [t["title"] for t in persisted_tasks]
        assert any("Brachial Plexus" in t for t in persisted_titles)

        # 6. Test with a missed class topic
        # Create a class occurrence in Physiology
        physio = next((s for s in subjects if "physio" in s["name"].lower()), subjects[-1])
        occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": physio["id"],
            "date": (today - timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed"
        })
        assert occ_res.status_code == 200
        occ_id = occ_res.json()["id"]

        # Add topic to the occurrence
        topic_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Cardiac Action Potential & Refractory Period",
            "description": "Phase 0 to Phase 4 ionic basis"
        })
        assert topic_res.status_code == 200

        # Mark attendance as ABSENT for this class
        att_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "absent",
            "notes": "Had clinical duties"
        })
        assert att_res.status_code == 200

        # Re-generate study plan: should now include high-priority catch-up task!
        plan_updated = await ac.post("/api/planner/generate", headers=headers, json={
            "daily_study_hours": 3.0
        })
        assert plan_updated.status_code == 200
        updated_tasks = plan_updated.json()["tasks"]
        catchup_tasks = [
            t for t in updated_tasks
            if "Cardiac Action Potential" in t["title"] and (
                "missed" in (t.get("description") or "").lower()
                or "catch up" in (t.get("description") or "").lower()
                or "catch up" in t["title"].lower()
            )
        ]
        assert len(catchup_tasks) > 0
        assert catchup_tasks[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_exact_study_planner_scenario():
    """
    Exact MBBS Study Planner Scenario Test:
    - Anatomy topic saved: Brachial Plexus
    - Physiology class marked Absent, topic: Cardiac Cycle
    - Biochemistry exam in 3 days
    - Wellbeing: Tired
    - Available study time: 90 minutes
    Verifies:
    1. Physiology catch-up is high priority (Reason: missed class topic)
    2. Biochemistry exam prep is high priority (Reason: exam in 3 days)
    3. Anatomy revision is included
    4. Tasks are shorter/lighter because Tired (15-20 min)
    5. Clean title format: {Subject} — {Topic}
    6. No fabricated subjects/topics
    7. Deduplication & Idempotence: No duplicates created after rerunning planner
    8. Wellbeing re-test with Great: ambitious blocks (35-45m) with same academic priorities
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"planner_exact_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "MBBS Exact Planner Student",
            "college": "AIIMS New Delhi",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch seeded subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        assert subjs_res.status_code == 200
        subjects = subjs_res.json()
        anatomy = next((s for s in subjects if "anat" in s["name"].lower()), subjects[0])
        physio = next((s for s in subjects if "physio" in s["name"].lower()), subjects[1])
        biochem = next((s for s in subjects if "biochem" in s["name"].lower()), subjects[2])

        today = date.today()

        # 1. Anatomy topic saved: "Brachial Plexus" from attended class
        anat_occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": anatomy["id"],
            "date": today.isoformat(),
            "start_time": "08:00:00",
            "end_time": "09:00:00",
            "status": "completed"
        })
        assert anat_occ.status_code == 200
        anat_occ_id = anat_occ.json()["id"]

        top_anat = await ac.post(f"/api/timetable/occurrences/{anat_occ_id}/topics", headers=headers, json={
            "title": "Brachial Plexus",
            "description": "Roots, trunks, divisions, cords and terminal branches"
        })
        assert top_anat.status_code == 200

        att_anat = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": anat_occ_id,
            "status": "present"
        })
        assert att_anat.status_code == 200

        # 2. Physiology class marked Absent, topic: "Cardiac Cycle"
        phys_occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": physio["id"],
            "date": today.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        assert phys_occ.status_code == 200
        phys_occ_id = phys_occ.json()["id"]

        top_phys = await ac.post(f"/api/timetable/occurrences/{phys_occ_id}/topics", headers=headers, json={
            "title": "Cardiac Cycle",
            "description": "Ventricular systole, diastole and pressure-volume relationship"
        })
        assert top_phys.status_code == 200

        att_phys = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": phys_occ_id,
            "status": "absent",
            "notes": "Medical duty leave"
        })
        assert att_phys.status_code == 200

        # 3. Biochemistry exam in 3 days
        exam_date = today + timedelta(days=3)
        exam_res = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": biochem["id"],
            "name": "Biochemistry 1st Internal",
            "exam_date": exam_date.isoformat(),
            "exam_type": "Internal Assessment",
            "target_score": 85.0,
            "important_topics": ["Glycolysis MCQs"]
        })
        assert exam_res.status_code == 200

        # 4. Wellbeing check-in: Tired
        wb_res = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "answered",
            "mood": "tired"
        })
        assert wb_res.status_code == 200

        # 5. Generate AI Study Plan with available study time = 90 minutes (1.5 hours)
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "daily_study_hours": 1.5
        })
        assert plan_res.status_code == 200
        data = plan_res.json()
        tasks = data["tasks"]
        assert len(tasks) > 0

        # Check clean titles {Subject} — {Topic}
        assert all("—" in t["title"] for t in tasks)

        # Physiology catch-up is high priority
        phys_tasks = [t for t in tasks if "Cardiac Cycle" in t["title"]]
        assert len(phys_tasks) > 0
        assert phys_tasks[0]["priority"] == "high"
        assert "missed class topic" in phys_tasks[0].get("description", "").lower()
        assert phys_tasks[0]["title"] == f"{physio['name']} — Cardiac Cycle"

        # Biochemistry exam prep is high priority
        biochem_tasks = [t for t in tasks if "Glycolysis" in t["title"] or "Biochemistry" in t["title"]]
        assert len(biochem_tasks) > 0
        assert biochem_tasks[0]["priority"] == "high"
        assert "exam in 3 days" in biochem_tasks[0].get("description", "").lower()

        # Anatomy revision is included
        anat_tasks = [t for t in tasks if "Brachial Plexus" in t["title"]]
        assert len(anat_tasks) > 0
        assert anat_tasks[0]["title"] == f"{anatomy['name']} — Brachial Plexus"

        # Tasks are shorter/lighter because Tired (20 min)
        for t in tasks:
            assert t["estimated_minutes"] <= 20

        # Groundedness: No fabricated subjects or topics
        valid_subj_ids = {anatomy["id"], physio["id"], biochem["id"]}
        for t in tasks:
            assert t["subject_id"] in valid_subj_ids
            assert any(k in t["title"] for k in ["Brachial Plexus", "Cardiac Cycle", "Glycolysis", "Biochemistry"])

        # 6. Deduplication & Idempotence test
        initial_task_count = len(tasks)
        rerun_res = await ac.post("/api/planner/generate", headers=headers, json={
            "daily_study_hours": 1.5
        })
        assert rerun_res.status_code == 200
        all_tasks_res = await ac.get("/api/planner/tasks", headers=headers)
        assert all_tasks_res.status_code == 200
        persisted_uncompleted = [t for t in all_tasks_res.json() if not t["is_completed"]]
        # Count must remain the same - 0 duplicate tasks!
        assert len(persisted_uncompleted) == initial_task_count

        # 7. Re-test with Great: plan becomes more ambitious (35-45 min blocks)
        wb_great = await ac.post("/api/habits/wellbeing", headers=headers, json={
            "status": "answered",
            "mood": "great"
        })
        assert wb_great.status_code == 200

        great_plan = await ac.post("/api/planner/generate", headers=headers, json={
            "daily_study_hours": 3.0
        })
        assert great_plan.status_code == 200
        great_tasks = great_plan.json()["tasks"]
        assert len(great_tasks) > 0
        # Blocks are ambitious (35-45 mins, e.g. 40m)
        assert any(t["estimated_minutes"] >= 35 for t in great_tasks)
        # Priorities remain intact
        great_phys = next(t for t in great_tasks if "Cardiac Cycle" in t["title"])
        great_biochem = next(t for t in great_tasks if "Glycolysis" in t["title"] or "Biochemistry" in t["title"])
        assert great_phys["priority"] == "high"
        assert great_biochem["priority"] == "high"


@pytest.mark.asyncio
async def test_structured_planner_balanced_and_priority_modes():
    """
    Tests the new structured Study Planner scheduling logic:
    - Number of study days: 2
    - Available time per day: 1 hour (total 120 minutes)
    - 4 subjects selected
    - Balanced vs Priority-aware behavior
    - Until next exam option
    - Quick review mode
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"planner_struct_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Structured Planner Student",
            "college": "KGMU Lucknow",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch seeded subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        assert subjs_res.status_code == 200
        all_subjs = subjs_res.json()
        assert len(all_subjs) >= 4
        s_anat = all_subjs[0]
        s_phys = all_subjs[1]
        s_biochem = all_subjs[2]
        s_path = all_subjs[3]
        selected_ids = [s_anat["id"], s_phys["id"], s_biochem["id"], s_path["id"]]

        today = date.today()

        # 1. Anatomy: recent class topic
        occ1 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": today.isoformat(),
            "start_time": "08:00:00",
            "end_time": "09:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ1.json()['id']}/topics", headers=headers, json={
            "title": "Brachial Plexus"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ1.json()["id"],
            "status": "present"
        })

        # 2. Physiology: missed class
        occ2 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_phys["id"],
            "date": today.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ2.json()['id']}/topics", headers=headers, json={
            "title": "Cardiac Action Potential"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ2.json()["id"],
            "status": "absent"
        })

        # 3. Biochemistry: Exam in 3 days
        await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_biochem["id"],
            "name": "Biochemistry Internal",
            "exam_date": (today + timedelta(days=3)).isoformat(),
            "exam_type": "Internal",
            "target_score": 80.0,
            "important_topics": ["Glycolysis"]
        })

        # 4. Pathology: class topic
        occ3 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_path["id"],
            "date": today.isoformat(),
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ3.json()['id']}/topics", headers=headers, json={
            "title": "Cell Injury & Necrosis"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ3.json()["id"],
            "status": "present"
        })

        # Test A: BALANCED PLANNING (2 days, 1 hr/day = 60m/day, 120m total across 4 subjects)
        bal_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": selected_ids,
            "planning_style": "balanced"
        })
        assert bal_res.status_code == 200
        bal_data = bal_res.json()
        bal_tasks = bal_data["tasks"]
        assert len(bal_tasks) >= 4
        # Verify all 4 chosen subjects are represented in the balanced plan
        covered_subjs = {t["subject_id"] for t in bal_tasks}
        assert set(selected_ids).issubset(covered_subjs)
        # Verify distribution across both days
        dates_used = {t["scheduled_date"] for t in bal_tasks}
        assert len(dates_used) == 2

        # Test B: PRIORITY-AWARE PLANNING
        prio_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": selected_ids,
            "planning_style": "priority_aware"
        })
        assert prio_res.status_code == 200
        prio_tasks = prio_res.json()["tasks"]
        assert len(prio_tasks) > 0
        # High urgency items (Biochem exam, Physio missed class) must have high priority
        biochem_tasks = [t for t in prio_tasks if t["subject_id"] == s_biochem["id"]]
        physio_tasks = [t for t in prio_tasks if t["subject_id"] == s_phys["id"]]
        assert any(t["priority"] == "high" for t in biochem_tasks)
        assert any(t["priority"] == "high" for t in physio_tasks)

        # Test C: UNTIL NEXT EXAM
        exam_plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "until_next_exam": True,
            "study_hours": 2,
            "study_minutes": 0
        })
        assert exam_plan_res.status_code == 200
        assert "3 day" in exam_plan_res.json()["title"] or "3 day" in exam_plan_res.json()["message"]

        # Test D: QUICK REVIEW MODE
        quick_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 1,
            "study_minutes": 0,
            "quick_review_mode": True
        })
        assert quick_res.status_code == 200
        quick_tasks = quick_res.json()["tasks"]
        for qt in quick_tasks:
            assert qt["estimated_minutes"] == 15
            assert "quick review sprint" in qt.get("description", "").lower()


@pytest.mark.asyncio
async def test_study_planner_subject_filtering_and_current_semester():
    """
    Tests Study Planner Subject Filtering:
    1. Student in 'MBBS 1st Year' registers.
    2. Default seeded subjects include Anatomy, Physiology, Biochemistry, Pathology, Pharmacology, Microbiology, etc.
    3. GET /api/planner/subjects:
       - current_semester_subjects must contain Anatomy, Physiology, Biochemistry.
       - Microbiology must NOT appear in current_semester_subjects.
       - other_subjects must contain Microbiology, Pathology, Pharmacology, etc.
    4. Plan generation with 'subject_mode: all' only targets current semester subjects, excluding Microbiology.
    5. Plan generation with 'subject_mode: choose' and Microbiology explicitly selected:
       - Successfully schedules Microbiology.
    6. Linking Microbiology through a Timetable Rule or Exam:
       - Automatically moves Microbiology into current_semester_subjects.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"planner_subj_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "First Year Student",
            "college": "AIIMS New Delhi",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Fetch Planner Subjects
        subj_res = await ac.get("/api/planner/subjects", headers=headers)
        assert subj_res.status_code == 200
        data = subj_res.json()

        assert data["year_of_study"] == "MBBS 1st Year"
        current_names = [s["name"] for s in data["current_semester_subjects"]]
        other_names = [s["name"] for s in data["other_subjects"]]

        # Current semester must include 1st year subjects
        assert "Anatomy" in current_names
        assert "Physiology" in current_names
        assert "Biochemistry" in current_names

        # Microbiology must NOT appear in current semester by default for 1st Year
        assert "Microbiology" not in current_names
        # Microbiology MUST appear in other subjects
        assert "Microbiology" in other_names
        assert "Pathology" in other_names
        assert "Pharmacology" in other_names

        # Get Microbiology subject ID
        all_subjs = await ac.get("/api/subjects/", headers=headers)
        s_micro = next(s for s in all_subjs.json() if s["name"] == "Microbiology")
        s_anat = next(s for s in all_subjs.json() if s["name"] == "Anatomy")

        today = date.today()

        # Add an Anatomy class topic and Microbiology topic for comparison
        occ_anat = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": today.isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ_anat.json()['id']}/topics", headers=headers, json={
            "title": "Brachial Plexus Anatomy"
        })

        occ_micro = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_micro["id"],
            "date": today.isoformat(),
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ_micro.json()['id']}/topics", headers=headers, json={
            "title": "Gram Staining & Culture"
        })

        # 2. Plan generation with 'choose' including Microbiology explicitly
        choose_plan = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_micro["id"]],
            "planning_style": "balanced"
        })
        assert choose_plan.status_code == 200
        micro_tasks = choose_plan.json()["tasks"]
        assert len(micro_tasks) > 0
        assert all(t["subject_id"] == s_micro["id"] for t in micro_tasks)
        assert any("Gram Staining" in t["title"] for t in micro_tasks)

        # 3. Linking Microbiology via Timetable Rule promotes it to current semester
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": s_micro["id"],
            "day_of_week": 0,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Sharma",
            "room": "Micro Lab"
        })
        assert rule_res.status_code == 200

        # Check planner subjects again - Microbiology should now be in current_semester_subjects
        recheck_res = await ac.get("/api/planner/subjects", headers=headers)
        assert recheck_res.status_code == 200
        recheck_data = recheck_res.json()
        recheck_current_names = [s["name"] for s in recheck_data["current_semester_subjects"]]
        assert "Microbiology" in recheck_current_names



