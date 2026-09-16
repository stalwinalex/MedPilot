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
async def test_intelligent_time_allocation_and_feedback_adaptation():
    """
    Controlled Verification of Intelligent Time Allocation:
    1. Setup:
       - Topic 1: Difficult / High Priority (Anatomy - Brachial Plexus)
       - Topic 2: Missed-class catch-up (Physiology - Cardiac Cycle)
       - Topic 3: Approaching Exam (Biochemistry - Glycolysis, Exam in 3d)
       - Topic 4: Easy / Already Revised (Pathology - Cell Injury)
    2. Available time = 120 minutes (1 day, 2 hours).
    3. Generate plan:
       - Verify durations are DIFFERENT (e.g. not uniform 30m each).
       - Verify difficult / urgent topics receive MORE time than easy topics.
       - Verify total duration equals available study time (120 min).
       - Verify human-readable reason tags are attached.
    4. Feedback adaptation:
       - Student submits feedback on Topic 4: Easy -> Hard (with actual time 50m).
    5. Regenerate plan:
       - Verify Topic 4's allocated duration ADAPTS and increases significantly.
       - Verify reason tag reflects the previous difficulty feedback.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register student
        email = f"adaptive_student_{uuid.uuid4().hex[:8]}@medpilot.edu"
        reg = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Adaptive Planning Student",
            "college": "Maulana Azad Medical College",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch seeded subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        assert subjs_res.status_code == 200
        subjects = subjs_res.json()
        s_anat = next((s for s in subjects if "anat" in s["name"].lower()), subjects[0])
        s_phys = next((s for s in subjects if "phys" in s["name"].lower()), subjects[1])
        s_biochem = next((s for s in subjects if "biochem" in s["name"].lower()), subjects[2])
        s_path = next((s for s in subjects if "path" in s["name"].lower()), subjects[3])
        chosen_ids = [s_anat["id"], s_phys["id"], s_biochem["id"], s_path["id"]]

        today = date.today()

        # 1. Topic 1: Difficult / High Priority (Anatomy - Brachial Plexus)
        # We also seed historical feedback: student previously rated Brachial Plexus as "hard"
        anat_occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": today.isoformat(),
            "start_time": "08:00:00",
            "end_time": "09:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{anat_occ.json()['id']}/topics", headers=headers, json={
            "title": "Brachial Plexus"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": anat_occ.json()["id"],
            "status": "present"
        })

        # Past completed task for Brachial Plexus marked 'hard'
        past_task_1 = await ac.post("/api/planner/tasks", headers=headers, json={
            "subject_id": s_anat["id"],
            "title": "Anatomy — Brachial Plexus",
            "scheduled_date": (today - timedelta(days=2)).isoformat(),
            "priority": "high",
            "estimated_minutes": 35
        })
        await ac.post(f"/api/planner/tasks/{past_task_1.json()['id']}/feedback", headers=headers, json={
            "feedback": "hard",
            "actual_minutes": 45
        })

        # 2. Topic 2: Missed Class Catch-up (Physiology - Cardiac Cycle)
        phys_occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_phys["id"],
            "date": today.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{phys_occ.json()['id']}/topics", headers=headers, json={
            "title": "Cardiac Cycle"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": phys_occ.json()["id"],
            "status": "absent"
        })

        # 3. Topic 3: Approaching Exam in 3 days (Biochemistry - Glycolysis)
        await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_biochem["id"],
            "name": "Biochemistry Assessment",
            "exam_date": (today + timedelta(days=3)).isoformat(),
            "target_score": 85.0,
            "important_topics": ["Glycolysis"]
        })

        # 4. Topic 4: Easy / Already Revised (Pathology - Cell Injury)
        path_occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_path["id"],
            "date": (today - timedelta(days=5)).isoformat(),
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{path_occ.json()['id']}/topics", headers=headers, json={
            "title": "Cell Injury"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": path_occ.json()["id"],
            "status": "present"
        })

        # Past completed task for Cell Injury marked 'easy'
        past_task_4 = await ac.post("/api/planner/tasks", headers=headers, json={
            "subject_id": s_path["id"],
            "title": "Pathology — Cell Injury",
            "scheduled_date": (today - timedelta(days=4)).isoformat(),
            "priority": "low",
            "estimated_minutes": 25
        })
        await ac.post(f"/api/planner/tasks/{past_task_4.json()['id']}/feedback", headers=headers, json={
            "feedback": "easy",
            "actual_minutes": 20
        })

        # ======================================================================
        # PHASE 1: GENERATE INITIAL PLAN (Total available time = 120 minutes)
        # ======================================================================
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": chosen_ids,
            "planning_style": "balanced"
        })
        assert plan_res.status_code == 200, plan_res.text
        plan_data = plan_res.json()
        tasks = plan_data["tasks"]
        assert len(tasks) == 4, f"Expected 4 tasks, got {len(tasks)}"

        # 1. Total duration must match available time (120 minutes)
        total_time = sum(t["estimated_minutes"] for t in tasks)
        assert total_time == 120, f"Expected 120m, got {total_time}m"

        # 2. Verify durations are DIFFERENT (NOT uniform 30m)
        durations = [t["estimated_minutes"] for t in tasks]
        unique_durations = set(durations)
        assert len(unique_durations) >= 3, f"Expected at least 3 distinct durations, got {durations}"
        # Ensure NOT all 30m
        assert not all(d == 30 for d in durations)

        # 3. Find individual topic durations
        t_anat = next(t for t in tasks if "Brachial Plexus" in t["title"])
        t_phys = next(t for t in tasks if "Cardiac Cycle" in t["title"])
        t_biochem = next(t for t in tasks if "Glycolysis" in t["title"])
        t_path = next(t for t in tasks if "Cell Injury" in t["title"])

        # High priority/difficult topics should receive MORE time than easy topic
        assert t_anat["estimated_minutes"] > t_path["estimated_minutes"], (
            f"Anatomy ({t_anat['estimated_minutes']}m) should receive more time than Easy Pathology ({t_path['estimated_minutes']}m)"
        )
        assert t_biochem["estimated_minutes"] > t_path["estimated_minutes"], (
            f"Exam Biochem ({t_biochem['estimated_minutes']}m) should receive more time than Easy Pathology ({t_path['estimated_minutes']}m)"
        )

        # 4. Verify reasons are informative and concise
        assert "marked hard" in t_anat.get("reason", "").lower() or "hard" in t_anat.get("description", "").lower()
        assert "missed class" in t_phys.get("reason", "").lower() or "missed class" in t_phys.get("description", "").lower()
        assert "exam in 3" in t_biochem.get("reason", "").lower() or "exam in 3" in t_biochem.get("description", "").lower()
        assert "previously mastered" in t_path.get("reason", "").lower() or "quick review" in t_path.get("reason", "").lower()

        initial_path_duration = t_path["estimated_minutes"]

        # ======================================================================
        # PHASE 2: FEEDBACK LOOP ADAPTATION (Easy -> Hard)
        # ======================================================================
        # Student completes Pathology Cell Injury and marks it HARD with 50 minutes actual time
        await ac.post(f"/api/planner/tasks/{t_path['id']}/feedback", headers=headers, json={
            "feedback": "hard",
            "actual_minutes": 50
        })

        # Also add a new occurrence or keep topic active so it gets replanned
        path_occ2 = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_path["id"],
            "date": today.isoformat(),
            "start_time": "15:00:00",
            "end_time": "16:00:00",
            "status": "completed"
        })
        await ac.post(f"/api/timetable/occurrences/{path_occ2.json()['id']}/topics", headers=headers, json={
            "title": "Cell Injury"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": path_occ2.json()["id"],
            "status": "present"
        })

        # ======================================================================
        # PHASE 3: REGENERATE PLAN & VERIFY TIME ADAPTATION
        # ======================================================================
        plan_res2 = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": chosen_ids,
            "planning_style": "balanced"
        })
        assert plan_res2.status_code == 200
        tasks2 = plan_res2.json()["tasks"]
        t_path2 = next(t for t in tasks2 if "Cell Injury" in t["title"])

        # Verify Pathology duration increased because student marked it Hard!
        assert t_path2["estimated_minutes"] > initial_path_duration, (
            f"Pathology duration should increase after marking 'hard' (was {initial_path_duration}m, now {t_path2['estimated_minutes']}m)"
        )
        assert "marked hard" in t_path2.get("reason", "").lower() or "extended study" in t_path2.get("reason", "").lower()
