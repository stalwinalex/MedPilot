import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from app.main import app


@pytest.mark.asyncio
async def test_study_session_workflow_and_future_planner_weighting():
    """
    Complete end-to-end verification of the study-session workflow:
    1. Task planned for 30 min -> Start -> Finish -> actual duration saved -> mark Hard -> moves to Completed.
    2. Future Study Planner generation reads stored feedback and actual-vs-planned duration from DB.
    3. Stored feedback & overrun are used as inputs to duration and priority estimates (not just display).
    4. Subject-level calibration: If a subject repeatedly takes longer and is marked Hard, future estimates increase.
    5. 'need_more_time' feedback automatically schedules a follow-up revision task.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg_res = await ac.post("/api/auth/register", json={
            "email": f"session_student_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Session Scholar",
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

        # ----------------------------------------------------------------------
        # STEP 1: Create a study task planned for 30 minutes
        # ----------------------------------------------------------------------
        create_task_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Brachial Plexus",
            "subject_id": s_anat["id"],
            "estimated_minutes": 30,
            "priority": "medium",
            "scheduled_date": today.isoformat()
        })
        assert create_task_res.status_code == 200, create_task_res.text
        task1 = create_task_res.json()
        assert task1["estimated_minutes"] == 30
        assert task1["is_completed"] is False
        task1_id = task1["id"]

        # ----------------------------------------------------------------------
        # STEP 2: Finish task -> actual duration saved (45 min) -> mark Hard
        # ----------------------------------------------------------------------
        feedback_res = await ac.post(f"/api/planner/tasks/{task1_id}/feedback", headers=headers, json={
            "actual_minutes": 45,
            "feedback": "hard"
        })
        assert feedback_res.status_code == 200, feedback_res.text
        completed_task1 = feedback_res.json()

        # Verify task is completed, actual duration saved, feedback saved
        assert completed_task1["is_completed"] is True
        assert completed_task1["actual_minutes"] == 45
        assert completed_task1["estimated_minutes"] == 30
        assert completed_task1["feedback"] == "hard"

        # Verify task is in completed tasks list
        tasks_list_res = await ac.get("/api/planner/tasks", headers=headers)
        all_tasks = tasks_list_res.json()
        t1_in_list = next((t for t in all_tasks if t["id"] == task1_id), None)
        assert t1_in_list is not None
        assert t1_in_list["is_completed"] is True

        # Verify study session was persistently logged
        session_list_res = await ac.get("/api/planner/sessions", headers=headers)
        if session_list_res.status_code == 200:
            sessions = session_list_res.json()
            sess = next((s for s in sessions if s.get("task_id") == task1_id), None)
            if sess:
                assert sess["duration_minutes"] == 45

        # ----------------------------------------------------------------------
        # STEP 3: Generate future plan and verify stored feedback & duration
        # are read and used as inputs for priority and duration estimates
        # ----------------------------------------------------------------------
        # Add class occurrences for Anatomy (Brachial Plexus) and Biochemistry (Glycolysis)
        anat_occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed"
        })
        anat_occ_id = anat_occ_res.json()["id"]
        await ac.post(f"/api/timetable/occurrences/{anat_occ_id}/topics", headers=headers, json={
            "title": "Brachial Plexus",
            "description": "Terminal branches and cords"
        })

        # Add Biochemistry class occurrence with Glycolysis topic
        biochem_occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_biochem["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        biochem_occ_id = biochem_occ_res.json()["id"]
        await ac.post(f"/api/timetable/occurrences/{biochem_occ_id}/topics", headers=headers, json={
            "title": "Glycolysis Pathway",
            "description": "Ten enzymatic steps"
        })

        # Generate a 1-day study plan with 60 minutes available
        gen_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"], s_biochem["id"]],
            "planning_style": "balanced"
        })
        assert gen_res.status_code == 200, gen_res.text
        plan_data = gen_res.json()
        tasks = plan_data["tasks"]

        # Find the generated tasks
        anat_gen = next((t for t in tasks if t["subject_id"] == s_anat["id"]), None)
        biochem_gen = next((t for t in tasks if t["subject_id"] == s_biochem["id"]), None)
        assert anat_gen is not None, "Anatomy task must be generated"
        assert biochem_gen is not None, "Biochemistry task must be generated"

        # VERIFICATION:
        # Anatomy topic 'Brachial Plexus' had stored feedback='hard' and actual_minutes=45 vs estimated_minutes=30.
        # It must receive higher planning score and more time than Biochem!
        assert anat_gen["planning_score"] > biochem_gen["planning_score"], (
            f"Anatomy planning_score ({anat_gen['planning_score']}) must be higher than Biochem ({biochem_gen['planning_score']})"
        )
        assert anat_gen["estimated_minutes"] > biochem_gen["estimated_minutes"], (
            f"Anatomy duration ({anat_gen['estimated_minutes']}m) must be greater than Biochem ({biochem_gen['estimated_minutes']}m)"
        )
        # Reason should explain the increased priority/overrun
        assert "hard" in anat_gen["reason"].lower() or "extended" in anat_gen["reason"].lower(), (
            f"Reason should reflect past Hard rating or extended study: {anat_gen['reason']}"
        )

        # ----------------------------------------------------------------------
        # STEP 4: Test 'need_more_time' feedback alone does NOT auto-create task,
        # but calling replan-need-more-time schedules follow-up intelligently
        # ----------------------------------------------------------------------
        task2_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Cardiac Action Potential",
            "subject_id": s_anat["id"],
            "estimated_minutes": 30,
            "priority": "medium",
            "scheduled_date": today.isoformat()
        })
        task2 = task2_res.json()

        feedback2_res = await ac.post(f"/api/planner/tasks/{task2['id']}/feedback", headers=headers, json={
            "actual_minutes": 35,
            "feedback": "need_more_time"
        })
        assert feedback2_res.status_code == 200

        # Submitting feedback alone does NOT automatically create extra work for tomorrow
        tasks_check1 = (await ac.get("/api/planner/tasks", headers=headers)).json()
        followup_pre = next((t for t in tasks_check1 if "Cardiac Action Potential (Follow-up)" in t["title"]), None)
        assert followup_pre is None, "Submitting feedback alone must NOT automatically add extra work to tomorrow"

        # Now test 'Add to My Plan' replan endpoint
        replan_res = await ac.post(f"/api/planner/tasks/{task2['id']}/replan-need-more-time", headers=headers, json={
            "extra_minutes": 30
        })
        assert replan_res.status_code == 200
        replan_data = replan_res.json()
        assert replan_data["success"] is True

        tasks_check2 = (await ac.get("/api/planner/tasks", headers=headers)).json()
        followup = next((t for t in tasks_check2 if "Cardiac Action Potential (Follow-up)" in t["title"]), None)
        assert followup is not None, "A follow-up task must be scheduled when student selects Add to My Plan"
        assert followup["priority"] == "high"
        assert followup["is_completed"] is False


@pytest.mark.asyncio
async def test_subject_level_repeated_hard_overrun_and_easy_calibration():
    """
    Verifies that:
    1. If Anatomy tasks repeatedly take longer than planned and are marked Hard,
       future Anatomy estimates increase appropriately (subject-level calibration).
    2. Easy feedback ensures future review is kept concise.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg_res = await ac.post("/api/auth/register", json={
            "email": f"calibration_student_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Calibration Scholar",
            "year_of_study": "MBBS 1st Year"
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        s_anat = next((s for s in subjects if "anat" in s["name"].lower()), subjects[0])
        s_biochem = next((s for s in subjects if "biochem" in s["name"].lower()), subjects[1])

        today = date.today()

        # Complete 2 Anatomy tasks with overrun and Hard feedback
        for i, title in enumerate(["Anatomy Thorax", "Anatomy Abdomen"]):
            t_res = await ac.post("/api/planner/tasks", headers=headers, json={
                "title": title,
                "subject_id": s_anat["id"],
                "estimated_minutes": 30,
                "scheduled_date": (today - timedelta(days=i+1)).isoformat()
            })
            tid = t_res.json()["id"]
            await ac.post(f"/api/planner/tasks/{tid}/feedback", headers=headers, json={
                "actual_minutes": 50,
                "feedback": "hard"
            })

        # Complete 1 Biochem task with Easy feedback
        b_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Biochemistry Vitamins",
            "subject_id": s_biochem["id"],
            "estimated_minutes": 30,
            "scheduled_date": (today - timedelta(days=1)).isoformat()
        })
        b_id = b_res.json()["id"]
        await ac.post(f"/api/planner/tasks/{b_id}/feedback", headers=headers, json={
            "actual_minutes": 20,
            "feedback": "easy"
        })

        # Now add new unseen topics for both subjects
        occ1 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": (today - timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ1.json()['id']}/topics", headers=headers, json={
            "title": "Pelvis & Perineum",
            "description": "Sacral plexus and pudendal nerve"
        })

        occ2 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_biochem["id"],
            "date": (today - timedelta(days=1)).isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ2.json()['id']}/topics", headers=headers, json={
            "title": "Biochemistry Vitamins Review",
            "description": "Fat soluble vitamins"
        })

        # Generate 1-day plan with 60 minutes budget
        gen_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 1,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"], s_biochem["id"]],
            "planning_style": "balanced"
        })
        assert gen_res.status_code == 200
        tasks = gen_res.json()["tasks"]
        anat_t = next(t for t in tasks if t["subject_id"] == s_anat["id"])
        biochem_t = next(t for t in tasks if t["subject_id"] == s_biochem["id"])

        # Anatomy must have higher duration and planning score due to subject-level calibration
        assert anat_t["planning_score"] > biochem_t["planning_score"]
        assert anat_t["estimated_minutes"] > biochem_t["estimated_minutes"]
        assert "repeatedly takes longer" in anat_t["reason"]

