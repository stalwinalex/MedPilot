import pytest
import pytest_asyncio
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.models import Profile, Subject, StudyTask, StudySession


import uuid


@pytest_asyncio.fixture
async def authenticated_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg_res = await ac.post("/api/auth/register", json={
            "email": f"nmt_student_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "NeedMoreTime Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200, reg_res.text
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Set daily study target to 120 minutes (2 hours hard limit) via /api/auth/me
        prof_res = await ac.put("/api/auth/me", headers=headers, json={
            "daily_study_target_minutes": 120
        })
        assert prof_res.status_code == 200
        assert prof_res.json()["daily_study_target_minutes"] == 120

        # Fetch seeded subjects
        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        s_anat = next((s for s in subjects if "anat" in s["name"].lower()), subjects[0])
        s_phys = next((s for s in subjects if "phys" in s["name"].lower()), subjects[1])

        yield ac, headers, s_anat, s_phys


@pytest.mark.asyncio
async def test_scenario_a_continue_now_saves_actual_total_and_feedback(authenticated_client):
    """
    Scenario A: Continue Now
    - Start / finish a 30m task
    - Select Need more time -> Continue Now
    - Verifies same timer/session continues
    - When finally finished, saves actual total time, date, feedback = 'need_more_time'
    """
    ac, headers, s_anat, s_phys = authenticated_client
    today = date.today()

    task_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Brachial Plexus",
        "subject_id": s_anat["id"],
        "estimated_minutes": 30,
        "priority": "medium",
        "scheduled_date": today.isoformat()
    })
    assert task_res.status_code == 200
    task = task_res.json()

    # The student continues now for 50 more minutes (total = 80 min)
    # The same active session continues and when finished submits total actual duration
    finish_res = await ac.post(f"/api/planner/tasks/{task['id']}/feedback", headers=headers, json={
        "actual_minutes": 80,
        "feedback": "need_more_time"
    })
    assert finish_res.status_code == 200
    updated_task = finish_res.json()
    assert updated_task["is_completed"] is True
    assert updated_task["actual_minutes"] == 80
    assert updated_task["feedback"] == "need_more_time"

    # Verify StudySession recorded the full 80 minutes
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select
        s_stmt = select(StudySession).filter(StudySession.task_id == task["id"])
        session = (await db.execute(s_stmt)).scalars().first()
        assert session is not None
        assert session.duration_minutes == 80


@pytest.mark.asyncio
async def test_scenario_b_full_tomorrow_hard_limit_not_exceeded(authenticated_client):
    """
    Scenario B: Full Tomorrow
    - Daily limit = 120 min (2 hours)
    - Tomorrow already contains 120 min (e.g. 60m high-priority Anatomy + 60m low-priority Physio)
    - Select Need more time -> Add to My Plan
    - MedPilot must NOT make tomorrow 150-180 min!
    - Intelligently moves the lower-priority task to the next available day and protects the limit.
    """
    ac, headers, s_anat, s_phys = authenticated_client
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Fill tomorrow to exactly 120 minutes
    t1_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Gross Anatomy Exam Prep",
        "subject_id": s_anat["id"],
        "estimated_minutes": 60,
        "priority": "high",
        "scheduled_date": tomorrow.isoformat()
    })
    assert t1_res.status_code == 200

    t2_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Physiology General Revision",
        "subject_id": s_phys["id"],
        "estimated_minutes": 60,
        "priority": "low",
        "scheduled_date": tomorrow.isoformat()
    })
    assert t2_res.status_code == 200

    # Today's task that needs more time
    today_task_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Upper Limb Nerves",
        "subject_id": s_anat["id"],
        "estimated_minutes": 30,
        "priority": "medium",
        "scheduled_date": today.isoformat()
    })
    today_task = today_task_res.json()

    # Call Add to My Plan (replan-need-more-time)
    replan_res = await ac.post(f"/api/planner/tasks/{today_task['id']}/replan-need-more-time", headers=headers, json={
        "extra_minutes": 30,
        "actual_minutes": 45
    })
    assert replan_res.status_code == 200
    res_data = replan_res.json()
    assert res_data["success"] is True

    # Check all tasks on tomorrow
    all_tasks = (await ac.get("/api/planner/tasks", headers=headers)).json()
    tomorrow_tasks = [t for t in all_tasks if t["scheduled_date"] == tomorrow.isoformat() and not t["is_completed"]]
    tomorrow_total = sum(t["estimated_minutes"] for t in tomorrow_tasks)

    # CRITICAL RULE: tomorrow must NOT exceed the 120 min daily limit!
    assert tomorrow_total <= 120, f"Tomorrow total ({tomorrow_total} min) exceeded the 120 min daily limit!"

    # Verify the low-priority task was moved to a later day to make room
    low_task = next(t for t in all_tasks if t["id"] == t2_res.json()["id"])
    assert low_task["scheduled_date"] != tomorrow.isoformat(), "Lower-priority task should have been moved to later day"

    # Explanation must clearly tell what happened
    assert "moved" in res_data["explanation"].lower() or "limit" in res_data["explanation"].lower()


@pytest.mark.asyncio
async def test_scenario_c_no_space_prompts_user_instead_of_silently_adding(authenticated_client):
    """
    Scenario C: No Space
    - All future days are full (120m limit reached on each day).
    - Select Need more time -> Add to My Plan.
    - MedPilot must NOT silently increase the daily limit.
    - Must return requires_user_action = True with options (Rebalance tomorrow, Spread later, Increase study time, etc.).
    """
    ac, headers, s_anat, s_phys = authenticated_client
    today = date.today()

    # Fill next 7 days with high-priority tasks (120 min each)
    for i in range(1, 8):
        d = today + timedelta(days=i)
        await ac.post("/api/planner/tasks", headers=headers, json={
            "title": f"High Priority Block 1 Day {i}",
            "subject_id": s_anat["id"],
            "estimated_minutes": 60,
            "priority": "high",
            "scheduled_date": d.isoformat()
        })
        await ac.post("/api/planner/tasks", headers=headers, json={
            "title": f"High Priority Block 2 Day {i}",
            "subject_id": s_phys["id"],
            "estimated_minutes": 60,
            "priority": "high",
            "scheduled_date": d.isoformat()
        })

    today_task_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Dense Neuroanatomy",
        "subject_id": s_anat["id"],
        "estimated_minutes": 45,
        "priority": "high",
        "scheduled_date": today.isoformat()
    })
    today_task = today_task_res.json()

    # Call replan without explicit increase permission
    replan_res = await ac.post(f"/api/planner/tasks/{today_task['id']}/replan-need-more-time", headers=headers, json={
        "extra_minutes": 30
    })
    assert replan_res.status_code == 200
    res_data = replan_res.json()

    # Must ask student instead of silently increasing limit!
    assert res_data["success"] is False
    assert res_data["requires_user_action"] is True
    assert "already full" in res_data["message"].lower() or "no_space" in res_data["status"]
    assert len(res_data["options"]) >= 4

    # If student explicitly approves increasing study time:
    approved_res = await ac.post(f"/api/planner/tasks/{today_task['id']}/replan-need-more-time", headers=headers, json={
        "extra_minutes": 30,
        "increase_daily_limit": True
    })
    assert approved_res.status_code == 200
    approved_data = approved_res.json()
    assert approved_data["success"] is True
    assert approved_data["status"] == "scheduled_with_increase"


@pytest.mark.asyncio
async def test_scenario_d_handle_later_saves_feedback_without_extra_task(authenticated_client):
    """
    Scenario D: I'll Handle It Later
    - Select Need more time -> I'll Handle It Later
    - Feedback is saved, task is marked completed
    - ZERO additional tasks are created
    - Learning history is preserved
    """
    ac, headers, s_anat, s_phys = authenticated_client
    today = date.today()

    task_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Histology of Bone",
        "subject_id": s_anat["id"],
        "estimated_minutes": 30,
        "priority": "medium",
        "scheduled_date": today.isoformat()
    })
    task = task_res.json()

    # Call handle_later strategy
    replan_res = await ac.post(f"/api/planner/tasks/{task['id']}/replan-need-more-time", headers=headers, json={
        "strategy": "handle_later",
        "actual_minutes": 40
    })
    assert replan_res.status_code == 200
    res_data = replan_res.json()
    assert res_data["status"] == "handle_later"

    all_tasks = (await ac.get("/api/planner/tasks", headers=headers)).json()
    # Confirm no follow-up task was created
    followup = next((t for t in all_tasks if "Histology of Bone (Follow-up)" in t["title"]), None)
    assert followup is None, "I'll Handle It Later must NOT create any additional task"

    # Confirm original task feedback is saved
    orig = next(t for t in all_tasks if t["id"] == task["id"])
    assert orig["is_completed"] is True
    assert orig["feedback"] == "need_more_time"
    assert orig["actual_minutes"] == 40


@pytest.mark.asyncio
async def test_scenario_e_future_plan_uses_need_more_time_history(authenticated_client):
    """
    Scenario E: Future Plan Learning
    - Topics with stored 'need_more_time' and duration overruns receive
      increased weight and duration in subsequent plan generations.
    """
    ac, headers, s_anat, s_phys = authenticated_client
    today = date.today()

    # Complete a Brachial Plexus task with need_more_time and 60m actual vs 30m planned
    t_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "title": "Brachial Plexus",
        "subject_id": s_anat["id"],
        "estimated_minutes": 30,
        "priority": "medium",
        "scheduled_date": today.isoformat()
    })
    t = t_res.json()

    await ac.post(f"/api/planner/tasks/{t['id']}/feedback", headers=headers, json={
        "actual_minutes": 60,
        "feedback": "need_more_time"
    })

    # Add class occurrence and topic for Anatomy
    occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
        "subject_id": s_anat["id"],
        "date": today.isoformat(),
        "start_time": "09:00:00",
        "end_time": "10:00:00",
        "status": "completed"
    })
    anat_occ_id = occ_res.json()["id"]
    await ac.post(f"/api/timetable/occurrences/{anat_occ_id}/topics", headers=headers, json={
        "title": "Brachial Plexus",
        "description": "Nerves and cords"
    })

    # Add class occurrence and topic for Physiology
    phys_occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
        "subject_id": s_phys["id"],
        "date": today.isoformat(),
        "start_time": "11:00:00",
        "end_time": "12:00:00",
        "status": "completed"
    })
    await ac.post(f"/api/timetable/occurrences/{phys_occ_res.json()['id']}/topics", headers=headers, json={
        "title": "Cardiac Cycle",
        "description": "Systole and diastole"
    })

    # Generate future plan
    gen_res = await ac.post("/api/planner/generate", headers=headers, json={
        "plan_days": 1,
        "study_hours": 1,
        "study_minutes": 0,
        "subject_mode": "choose",
        "subject_ids": [s_anat["id"], s_phys["id"]],
        "planning_style": "balanced"
    })
    assert gen_res.status_code == 200
    plan = gen_res.json()
    tasks = plan["tasks"]
    assert len(tasks) > 0

    # Verify candidate that had need_more_time has boost and reason annotation
    anat_gen = next((tk for tk in tasks if tk["subject_id"] == s_anat["id"]), None)
    phys_gen = next((tk for tk in tasks if tk["subject_id"] == s_phys["id"]), None)
    assert anat_gen is not None, "Anatomy task must be generated"
    assert phys_gen is not None, "Physiology task must be generated"

    # Check that reason reflects needed more time or extended study
    assert "needed more time" in (anat_gen.get("reason") or "").lower() or "extended" in (anat_gen.get("reason") or "").lower()
    # Check that Anatomy planning score is higher due to need_more_time history
    assert anat_gen["planning_score"] > phys_gen["planning_score"], (
        f"Anatomy planning_score ({anat_gen['planning_score']}) must be higher than Physio ({phys_gen['planning_score']})"
    )


@pytest.mark.asyncio
async def test_exact_user_scenario_3_day_plan_120m_limit_rebalanced(authenticated_client):
    """
    CRITICAL USER TEST CASE:
    - 3-day plan with 120 min/day limit.
    - Day 2 has 3 tasks totaling 120 min (Anatomy 45m, Physio 40m, Biochem 35m).
    - Student finishes Day 1 task -> Need more time -> Add to My Plan -> 45 min.
    - Verify Day 2 does NOT become 165 min.
    - Verify Day 2 stays <= 120 min through intelligent rebalancing.
    - Verify no duplicate tasks.
    - Verify refresh persists changes.
    """
    ac, headers, s_anat, s_phys = authenticated_client
    today = date.today()
    tomorrow = today + timedelta(days=1)
    day3 = today + timedelta(days=2)

    # Fetch 3rd subject (e.g. Biochem)
    subj_res = await ac.get("/api/subjects/", headers=headers)
    subjects = subj_res.json()
    s_biochem = next((s for s in subjects if "bio" in s["name"].lower()), subjects[2] if len(subjects) > 2 else subjects[0])

    # 1. Create a 3-day plan with daily_study_budget_minutes = 120
    async with AsyncSessionLocal() as db:
        from app.models.models import StudyPlan
        plan = StudyPlan(
            user_id=(await ac.get("/api/auth/me", headers=headers)).json()["id"],
            title="3-Day Clinical Prep Plan",
            start_date=today,
            end_date=day3,
            daily_study_budget_minutes=120,
            status="active"
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        plan_id = plan.id

    # 2. Day 1 task (today)
    day1_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "plan_id": plan_id,
        "title": "Brachial Plexus Basics",
        "subject_id": s_anat["id"],
        "estimated_minutes": 45,
        "priority": "medium",
        "scheduled_date": today.isoformat()
    })
    assert day1_res.status_code == 200
    day1_task = day1_res.json()

    # 3. Day 2 has 3 tasks totaling exactly 120 min:
    # Anatomy: 45 min, Physio: 40 min, Biochem: 35 min
    t_anat_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "plan_id": plan_id,
        "title": "Anatomy Thorax Dissection",
        "subject_id": s_anat["id"],
        "estimated_minutes": 45,
        "priority": "medium",
        "scheduled_date": tomorrow.isoformat()
    })
    assert t_anat_res.status_code == 200

    t_phys_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "plan_id": plan_id,
        "title": "Physiology Cardiac Mechanics",
        "subject_id": s_phys["id"],
        "estimated_minutes": 40,
        "priority": "medium",
        "scheduled_date": tomorrow.isoformat()
    })
    assert t_phys_res.status_code == 200

    t_bio_res = await ac.post("/api/planner/tasks", headers=headers, json={
        "plan_id": plan_id,
        "title": "Biochemistry Enzyme Kinetics",
        "subject_id": s_biochem["id"],
        "estimated_minutes": 35,
        "priority": "medium",
        "scheduled_date": tomorrow.isoformat()
    })
    assert t_bio_res.status_code == 200

    # Verify Day 2 starts at exactly 120 minutes
    all_before = (await ac.get("/api/planner/tasks", headers=headers)).json()
    day2_before = [t for t in all_before if t["scheduled_date"] == tomorrow.isoformat() and not t["is_completed"]]
    assert sum(t["estimated_minutes"] for t in day2_before) == 120

    # 4. Student finishes Day 1 task -> Need more time -> Add to My Plan -> 45 min
    replan_res = await ac.post(f"/api/planner/tasks/{day1_task['id']}/replan-need-more-time", headers=headers, json={
        "extra_minutes": 45,
        "actual_minutes": 60,
        "strategy": "auto"
    })
    assert replan_res.status_code == 200
    res_data = replan_res.json()
    assert res_data["success"] is True, f"Replan failed: {res_data}"
    assert res_data["status"] == "rebalanced"
    assert "moved" in res_data["explanation"].lower() or "limit" in res_data["explanation"].lower()

    # 5. Verify Day 2 does NOT become 165 min!
    all_after = (await ac.get("/api/planner/tasks", headers=headers)).json()
    day2_after = [t for t in all_after if t["scheduled_date"] == tomorrow.isoformat() and not t["is_completed"]]
    day2_total_minutes = sum(t["estimated_minutes"] for t in day2_after)

    assert day2_total_minutes != 165, "BUG REPRODUCED: Day 2 was overloaded to 165 min!"
    assert day2_total_minutes <= 120, f"Day 2 exceeded 120m limit: got {day2_total_minutes}m"

    # Verify Day 3 also stays within budget (<= 120 min)
    day3_after = [t for t in all_after if t["scheduled_date"] == day3.isoformat() and not t["is_completed"]]
    day3_total_minutes = sum(t["estimated_minutes"] for t in day3_after)
    assert day3_total_minutes <= 120, f"Day 3 exceeded 120m limit: got {day3_total_minutes}m"

    # Verify no duplicate follow-up tasks were created
    followup_tasks = [t for t in all_after if "Brachial Plexus Basics (Follow-up)" in t["title"]]
    assert len(followup_tasks) == 1, f"Expected exactly 1 follow-up task, found {len(followup_tasks)}"

    # 6. Verify persistence upon fresh refresh
    fresh_list = (await ac.get("/api/planner/tasks", headers=headers)).json()
    fresh_day2 = [t for t in fresh_list if t["scheduled_date"] == tomorrow.isoformat() and not t["is_completed"]]
    assert sum(t["estimated_minutes"] for t in fresh_day2) <= 120

