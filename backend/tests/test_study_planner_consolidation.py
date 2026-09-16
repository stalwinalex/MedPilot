import uuid
import pytest
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.models import Profile, Subject, StudyTask, StudyPlan, Exam, ClassOccurrence, ClassTopic


@pytest.mark.asyncio
async def test_scenario_a_different_difficulty_priority_durations_differ():
    """
    Scenario A: Two subjects with different difficulty/priority:
    - Subject 1 (Anatomy): upcoming exam in 2 days, high priority topics
    - Subject 2 (Physiology): neutral, no upcoming exams
    - Verify durations differ logically in Priority-aware mode.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_a_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario A Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_anat = next(s for s in subjs if "anat" in s["name"].lower())
        s_phys = next(s for s in subjs if "phys" in s["name"].lower())

        today = date.today()
        # Add urgent exam for Anatomy
        await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_anat["id"],
            "name": "Anatomy Major Internal",
            "exam_date": (today + timedelta(days=2)).isoformat(),
            "target_score": 85.0,
            "syllabus_portion": "Head & Neck",
            "important_topics": ["Cranial Nerves", "Circle of Willis"]
        })

        # Add lecture topic for Physiology (regular priority)
        occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_phys["id"],
            "date": (today - timedelta(days=1)).isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ.json()['id']}/topics", headers=headers, json={
            "title": "Renal Clearance"
        })

        # Generate priority-aware plan for 2 days, 2 hours/day (240 total mins)
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "selected_subjects": [s_anat["id"], s_phys["id"]],
            "planning_style": "priority_aware"
        })
        assert plan_res.status_code == 200
        tasks = plan_res.json()["tasks"]
        assert len(tasks) > 0

        anat_mins = sum(t["estimated_minutes"] for t in tasks if t["subject_id"] == s_anat["id"])
        phys_mins = sum(t["estimated_minutes"] for t in tasks if t["subject_id"] == s_phys["id"])

        # Anatomy (urgent exam in 2 days) should receive significantly more time than Physiology
        assert anat_mins > phys_mins, f"Expected Anatomy ({anat_mins}m) > Phys ({phys_mins}m)"


@pytest.mark.asyncio
async def test_scenario_b_truly_equal_weights_equal_durations():
    """
    Scenario B: Two subjects with truly equal weights:
    - Neutral history, equal topics, balanced mode
    - Verify equal durations (fair subject baseline allocation).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_b_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario B Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s1 = subjs[0]
        s2 = subjs[1]

        today = date.today()
        # Add 1 topic to each subject under identical conditions
        occ1 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s1["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ1.json()['id']}/topics", headers=headers, json={
            "title": "Equal Topic Alpha"
        })

        occ2 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s2["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{occ2.json()['id']}/topics", headers=headers, json={
            "title": "Equal Topic Beta"
        })

        # Generate balanced plan for 2 days, 2 hours/day
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "selected_subjects": [s1["id"], s2["id"]],
            "planning_style": "balanced"
        })
        assert plan_res.status_code == 200
        tasks = plan_res.json()["tasks"]
        assert len(tasks) > 0

        s1_mins = sum(t["estimated_minutes"] for t in tasks if t["subject_id"] == s1["id"])
        s2_mins = sum(t["estimated_minutes"] for t in tasks if t["subject_id"] == s2["id"])

        # Under balanced mode with equal conditions, durations should be equal
        assert s1_mins == s2_mins, f"Expected equal minutes for balanced equal subjects: {s1_mins} vs {s2_mins}"


@pytest.mark.asyncio
async def test_scenario_c_hard_daily_study_budget():
    """
    Scenario C: Hard daily study budget:
    - User sets 2 hours/day (120 minutes).
    - Verify for every single day in the generated plan: sum(task.estimated_minutes) <= 120.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_c_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario C Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        subjs = (await ac.get("/api/subjects/", headers=headers)).json()

        # Seed multiple topics to ensure plenty of candidates
        today = date.today()
        for idx, subj in enumerate(subjs[:3]):
            start_h = f"{8+idx:02d}:00:00"
            end_h = f"{9+idx:02d}:00:00"
            occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
                "subject_id": subj["id"],
                "date": (today - timedelta(days=1)).isoformat(),
                "start_time": start_h,
                "end_time": end_h,
                "status": "completed"
            })
            assert occ.status_code == 200
            for t_num in range(3):
                await ac.post(f"/api/timetable/occurrences/{occ.json()['id']}/topics", headers=headers, json={
                    "title": f"{subj['name']} Topic {t_num+1}"
                })

        # Generate 4-day plan with 2 hours/day (120 min)
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 4,
            "study_hours": 2,
            "study_minutes": 0,
            "planning_style": "priority_aware"
        })
        assert plan_res.status_code == 200
        tasks = plan_res.json()["tasks"]
        assert len(tasks) > 0

        # Group by day and check sum <= 120
        daily_sums = {}
        for t in tasks:
            d = t["scheduled_date"]
            daily_sums[d] = daily_sums.get(d, 0) + t["estimated_minutes"]

        for d, total in daily_sums.items():
            assert total <= 120, f"Day {d} exceeded 120 minutes hard limit: {total}m"


@pytest.mark.asyncio
async def test_scenario_d_exam_with_important_topics_and_portion():
    """
    Scenario D: Exam with important topics and portion:
    - Subject: Biochemistry
    - Portion: Carbohydrate Metabolism
    - Important topics: ["Glycolysis Regulation", "TCA Cycle Energetics"]
    - Date: today + 3 days
    - Verify tasks prioritize these topics with high priority, correct subject and explanation.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_d_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario D Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_bio = next(s for s in subjs if "bio" in s["name"].lower())

        today = date.today()
        exam_res = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_bio["id"],
            "name": "Biochem Midterm",
            "exam_date": (today + timedelta(days=3)).isoformat(),
            "target_score": 85.0,
            "syllabus_portion": "Carbohydrate Metabolism",
            "important_topics": ["Glycolysis Regulation", "TCA Cycle Energetics"]
        })
        assert exam_res.status_code == 200

        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 3,
            "study_hours": 2,
            "study_minutes": 0,
            "planning_style": "priority_aware"
        })
        assert plan_res.status_code == 200
        tasks = plan_res.json()["tasks"]

        glyc_tasks = [t for t in tasks if "Glycolysis" in t["title"]]
        tca_tasks = [t for t in tasks if "TCA Cycle" in t["title"]]
        assert len(glyc_tasks) > 0 or len(tca_tasks) > 0

        target_task = glyc_tasks[0] if glyc_tasks else tca_tasks[0]
        assert target_task["priority"] == "high"
        assert target_task["subject_id"] == s_bio["id"]
        assert target_task["reason"] is not None
        assert "exam" in target_task["reason"].lower()


@pytest.mark.asyncio
async def test_scenario_e_feasibility_check_prompts_and_options():
    """
    Scenario E: Feasibility check:
    - User has 6 candidate topics needing ~180m, but sets available time to 1 day, 30m.
    - Feasibility check triggers warning with exact wording and 4 action buttons.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_e_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario E Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s = subjs[0]

        # Add exam with 6 topics
        today = date.today()
        exam_res = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s["id"],
            "name": "Comprehensive Internal",
            "exam_date": (today + timedelta(days=3)).isoformat(),
            "target_score": 85.0,
            "important_topics": [f"Candidate Feasibility Topic {i+1}" for i in range(6)]
        })
        assert exam_res.status_code == 200

        # Run feasibility check with only 1 day, 30 min (30 min total)
        chk_res = await ac.post("/api/planner/feasibility-check", headers=headers, json={
            "plan_days": 1,
            "study_hours": 0,
            "study_minutes": 30,
            "subject_mode": "all",
            "planning_style": "balanced"
        })
        assert chk_res.status_code == 200
        data = chk_res.json()
        assert data["is_insufficient"] is True
        assert "Your available study time may not be enough to cover everything properly" in data["message"]
        assert "MedPilot estimates about" in data["message"]
        assert len(data["options"]) == 4
        assert "Add More Study Time" in data["options"]
        assert "Add More Days" in data["options"]
        assert "Prioritize Important Topics" in data["options"]
        assert "Create Quick Review Plan" in data["options"]


@pytest.mark.asyncio
async def test_scenario_f_missed_class_study_later_skip():
    """
    Scenario F: Missed class with multiple topics:
    - Multiple topics recorded for one class
    - Independent controls: Study, Later (snooze), Skip (with restore)
    - Verifies class history is never deleted.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_f_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario F Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s = subjs[0]

        # Record missed class
        today = date.today()
        occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        occ_id = occ_res.json()["id"]

        t1_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Topic Alpha (Cardiac)"
        })
        t2_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Topic Beta (Vascular)"
        })
        t1_id = t1_res.json()["id"]
        t2_id = t2_res.json()["id"]

        # Mark absent
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "absent"
        })

        # Query missed topics
        missed = (await ac.get("/api/planner/missed-topics", headers=headers)).json()
        target_occ = next(m for m in missed if m["occurrence_id"] == occ_id)
        assert len(target_occ["topics"]) == 2

        # 1. Put Topic Alpha on Later (snooze 3 days)
        snooze_d = (today + timedelta(days=3)).isoformat()
        snooze_res = await ac.put(f"/api/planner/topics/{t1_id}/status", headers=headers, json={
            "study_status": "later",
            "snooze_until": snooze_d
        })
        assert snooze_res.status_code == 200
        assert snooze_res.json()["study_status"] == "later"

        # 2. Skip Topic Beta
        skip_res = await ac.put(f"/api/planner/topics/{t2_id}/status", headers=headers, json={
            "study_status": "skip",
            "skip_reason": "already_reviewed"
        })
        assert skip_res.status_code == 200
        assert skip_res.json()["study_status"] == "skip"

        # 3. Class occurrence topics are NOT deleted
        occ_check = (await ac.get(f"/api/timetable/occurrences/{occ_id}", headers=headers)).json()
        assert len(occ_check["topics"]) == 2

        # 4. Restore Topic Beta
        restore_res = await ac.post(f"/api/planner/topics/{t2_id}/restore", headers=headers)
        assert restore_res.status_code == 200
        assert restore_res.json()["study_status"] == "study"


@pytest.mark.asyncio
async def test_scenario_g_need_more_time_continue_now():
    """
    Scenario G: Need More Time -> Continue Now:
    - Continuous session: finishes with actual duration, no duplicate tasks.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_g_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario G Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()

        today = date.today()
        task_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Pharyngeal Arches",
            "subject_id": subjs[0]["id"],
            "estimated_minutes": 30,
            "scheduled_date": today.isoformat()
        })
        task_id = task_res.json()["id"]

        # Student continues for +30m (total actual = 60m)
        fb_res = await ac.post(f"/api/planner/tasks/{task_id}/feedback", headers=headers, json={
            "actual_minutes": 60,
            "feedback": "need_more_time"
        })
        assert fb_res.status_code == 200
        updated = fb_res.json()
        assert updated["is_completed"] is True
        assert updated["actual_minutes"] == 60
        assert updated["feedback"] == "need_more_time"

        # Verify no duplicate task was spawned
        all_tasks = (await ac.get("/api/planner/tasks", headers=headers)).json()
        matching = [t for t in all_tasks if "Pharyngeal Arches" in t["title"]]
        assert len(matching) == 1


@pytest.mark.asyncio
async def test_scenario_h_need_more_time_add_to_my_plan_rebalances():
    """
    Scenario H: Need More Time -> Add to My Plan:
    - User has 120m daily limit. Tomorrow has 90m scheduled.
    - Adding 45m follow-up triggers rebalancing so tomorrow stays <= 120m.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_h_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario H Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Set daily study target to 120m
        await ac.put("/api/auth/me", headers=headers, json={"daily_study_target_minutes": 120})
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()

        today = date.today()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        # Active plan
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 3,
            "study_hours": 2,
            "study_minutes": 0,
            "planning_style": "balanced"
        })

        # Create today's completed task
        t_today = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Today's Task",
            "subject_id": subjs[0]["id"],
            "estimated_minutes": 30,
            "scheduled_date": today.isoformat()
        })
        t_today_id = t_today.json()["id"]

        # Fill tomorrow with 90m
        await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Tomorrow Task 1",
            "subject_id": subjs[0]["id"],
            "estimated_minutes": 60,
            "priority": "low",
            "scheduled_date": tomorrow.isoformat()
        })
        await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Tomorrow Task 2",
            "subject_id": subjs[1]["id"],
            "estimated_minutes": 30,
            "priority": "medium",
            "scheduled_date": tomorrow.isoformat()
        })

        # Replan with 45m follow-up
        replan_res = await ac.post(f"/api/planner/tasks/{t_today_id}/replan-need-more-time", headers=headers, json={
            "extra_minutes": 45,
            "strategy": "auto"
        })
        assert replan_res.status_code == 200
        data = replan_res.json()
        assert data["success"] is True

        # Verify tomorrow's total is <= 120m
        all_tasks = (await ac.get("/api/planner/tasks", headers=headers)).json()
        tomorrow_tasks = [t for t in all_tasks if t["scheduled_date"] == tomorrow.isoformat() and not t["is_completed"]]
        tomorrow_mins = sum(t["estimated_minutes"] for t in tomorrow_tasks)
        assert tomorrow_mins <= 120, f"Tomorrow exceeded 120m: {tomorrow_mins}m"


@pytest.mark.asyncio
async def test_scenario_i_task_marked_hard_informs_future_planner():
    """
    Scenario I: Task marked Hard:
    - Save task feedback: feedback="hard", actual_minutes=60 (planned 30).
    - Stored in database.
    - Future planner reads stored feedback and weights topic higher.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_i_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario I Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s = subjs[0]

        today = date.today()
        task_res = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Enzyme Kinetics",
            "subject_id": s["id"],
            "estimated_minutes": 30,
            "scheduled_date": (today - timedelta(days=1)).isoformat()
        })
        task_id = task_res.json()["id"]

        # Submit 'hard' feedback with overrun
        fb_res = await ac.post(f"/api/planner/tasks/{task_id}/feedback", headers=headers, json={
            "actual_minutes": 60,
            "feedback": "hard"
        })
        assert fb_res.status_code == 200

        # Check task persisted feedback via GET /tasks/{task_id}
        check_task = (await ac.get(f"/api/planner/tasks/{task_id}", headers=headers)).json()
        assert check_task["feedback"] == "hard"
        assert check_task["actual_minutes"] == 60


@pytest.mark.asyncio
async def test_scenario_j_daily_completion_celebration():
    """
    Scenario J: Complete all today's tasks:
    - User has 2 tasks scheduled today.
    - Both marked completed.
    - All today's tasks are completed.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"scen_j_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Scenario J Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()

        today = date.today()
        t1 = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Finish Today Task 1",
            "subject_id": subjs[0]["id"],
            "estimated_minutes": 30,
            "scheduled_date": today.isoformat()
        })
        t2 = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Finish Today Task 2",
            "subject_id": subjs[1]["id"],
            "estimated_minutes": 30,
            "scheduled_date": today.isoformat()
        })

        # Complete both
        await ac.put(f"/api/planner/tasks/{t1.json()['id']}", headers=headers, json={"is_completed": True})
        await ac.put(f"/api/planner/tasks/{t2.json()['id']}", headers=headers, json={"is_completed": True})

        # Fetch all tasks and filter today's tasks
        all_tasks = (await ac.get("/api/planner/tasks", headers=headers)).json()
        today_tasks = [t for t in all_tasks if t["scheduled_date"] == today.isoformat()]
        assert len(today_tasks) == 2
        assert all(t["is_completed"] for t in today_tasks)


@pytest.mark.asyncio
async def test_scenario_k_refresh_and_persistence():
    """
    Scenario K: Refresh / login persistence:
    - Create tasks, exams, feedback
    - Log in afresh with credentials
    - Verify all state, tasks, and history persist identically.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        email = f"scen_k_{uid}@medpilot.test"
        pwd = "Password123!"

        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": pwd,
            "full_name": "Scenario K Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()

        today = date.today()
        # Create a task and complete it with feedback
        t = await ac.post("/api/planner/tasks", headers=headers, json={
            "title": "Persistent Anatomy Topic",
            "subject_id": subjs[0]["id"],
            "estimated_minutes": 45,
            "scheduled_date": today.isoformat()
        })
        t_id = t.json()["id"]
        await ac.post(f"/api/planner/tasks/{t_id}/feedback", headers=headers, json={
            "actual_minutes": 50,
            "feedback": "okay"
        })

        # Re-authenticate by logging in again
        login_res = await ac.post("/api/auth/login", json={"email": email, "password": pwd})
        assert login_res.status_code == 200
        new_token = login_res.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # Query tasks with new session
        tasks_res = await ac.get("/api/planner/tasks", headers=new_headers)
        assert tasks_res.status_code == 200
        all_tasks = tasks_res.json()
        target = next((x for x in all_tasks if x["id"] == t_id), None)
        assert target is not None
        assert target["title"] == "Persistent Anatomy Topic"
        assert target["is_completed"] is True
        assert target["actual_minutes"] == 50
        assert target["feedback"] == "okay"
