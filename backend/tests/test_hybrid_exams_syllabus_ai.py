import uuid
import pytest
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.curriculum_service import CANONICAL_CURRICULUM_SYLLABUS
from app.services.exam_syllabus_ai_service import ExamSyllabusAIService


@pytest.mark.asyncio
async def test_primary_source_of_truth_authoritative_curriculum():
    """
    Requirement 1 & 7: PRIMARY SOURCE OF TRUTH & SAFETY AGAINST WRONG SUBJECTS
    - Normal topic suggestions must come from MedPilot's structured curriculum:
      Academic Year / Semester -> Subject -> Unit / Portion -> Topics
    - Do not use LLMs to freely invent or hallucinate the official syllabus.
    - Zero cross-subject leakage (e.g. Anatomy -> Heart Failure is strictly prohibited).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"hybrid_truth_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Authoritative Curriculum Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_anat = next(s for s in subjs if "anat" in s["name"].lower())

        # Query suggestions for Upper Limb
        res = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=Upper Limb", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # All suggestions must exist in CANONICAL_CURRICULUM_SYLLABUS["anatomy"]["Upper Limb"]
        canonical_ul = set(t.lower() for t in CANONICAL_CURRICULUM_SYLLABUS["anatomy"]["Upper Limb"])
        for suggestion in data["suggestions"]:
            assert suggestion.lower() in canonical_ul, f"Topic '{suggestion}' is not in authoritative curriculum!"

        # Cross-subject check: Heart Failure must NEVER appear under Anatomy
        all_text = " ".join(data["suggestions"]).lower()
        assert "heart failure" not in all_text


@pytest.mark.asyncio
async def test_ai_assisted_matching_unusual_or_custom_wording():
    """
    Requirement 2: AI-ASSISTED MATCHING
    Student types: "upper extremity nerves"
    MedPilot searches local syllabus, alias/fuzzy matching, or AI provider.
    Result:
    "upper extremity nerves" -> Anatomy -> "Upper Limb"
    Then loads the VERIFIED topics from MedPilot's curriculum database.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"hybrid_match_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Matching Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_anat = next(s for s in subjs if "anat" in s["name"].lower())

        # Test custom wording "upper extremity nerves"
        res = await ac.get(
            f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=upper extremity nerves",
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()

        # Must map to "Upper Limb"
        assert data["matched_portion"] == "Upper Limb"
        assert data["confidence"] in ["high", "medium"]
        assert len(data["suggestions"]) > 0

        # Verified topics must include Upper Limb topics like Brachial Plexus
        sugg_text = " ".join(data["suggestions"]).lower()
        assert "brachial plexus" in sugg_text
        assert any(kw in sugg_text for kw in ["median nerve", "carpal tunnel", "radial nerve", "ulnar nerve"])


@pytest.mark.asyncio
async def test_confidence_check_tiers():
    """
    Requirement 3: CONFIDENCE CHECK
    - High confidence: automatically shows matched syllabus suggestions.
    - Medium confidence: show "Did you mean {Portion}?"
    - Low confidence: show "We couldn't confidently match this portion to the syllabus. Add topics manually or choose a syllabus unit."
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"hybrid_conf_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Confidence Tiers Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_anat = next(s for s in subjs if "anat" in s["name"].lower())

        # 1. High confidence: exact or alias unit
        res_high = await ac.get(
            f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=Upper Limb",
            headers=headers
        )
        assert res_high.status_code == 200
        d_high = res_high.json()
        assert d_high["confidence"] == "high"
        assert d_high["matched_portion"] == "Upper Limb"
        assert len(d_high["suggestions"]) > 0

        # 2. Medium confidence: ambiguous input e.g. "limbs" (matches Upper Limb & Lower Limb)
        res_med = await ac.get(
            f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=limbs",
            headers=headers
        )
        assert res_med.status_code == 200
        d_med = res_med.json()
        assert d_med["confidence"] in ["medium", "high"]
        if d_med["confidence"] == "medium":
            assert "Did you mean" in d_med["match_message"]
            assert d_med["matched_portion"] in ["Upper Limb", "Lower Limb"]

        # 3. Low confidence: completely unmatchable / irrelevant text
        res_low = await ac.get(
            f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=astrophysics black hole thermodynamics",
            headers=headers
        )
        assert res_low.status_code == 200
        d_low = res_low.json()
        assert d_low["confidence"] == "low"
        assert d_low["matched_portion"] is None
        assert len(d_low["suggestions"]) == 0
        assert "We couldn't confidently match this portion to the syllabus" in d_low["match_message"]


@pytest.mark.asyncio
async def test_ai_assisted_ranking_and_context():
    """
    Requirement 4: AI-ASSISTED RANKING
    - Once verified syllabus topics are loaded, ranks them using available context
      (exam date, student-marked target score, missed classes, feedback history).
    - AI may rank or recommend topics, but must NOT change subject/unit mapping.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"hybrid_rank_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Ranking Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_phys = next(s for s in subjs if "phys" in s["name"].lower())

        # Record a missed class topic for CVS in Physiology
        today = date.today()
        occ = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_phys["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        assert occ.status_code == 200
        occ_id = occ.json()["id"]

        await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Regulation of Arterial Blood Pressure"
        })
        await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "absent"
        })

        # Fetch suggestions for Cardiovascular System
        res = await ac.get(
            f"/api/exams/topic-suggestions?subject_id={s_phys['id']}&portion=Cardiovascular System&days_remaining=3&target_score=85.0",
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        suggestions = data["suggestions"]
        assert len(suggestions) > 0

        # The missed topic ("Regulation of Arterial Blood Pressure") should be ranked prominently near the top
        top_3_lower = [t.lower() for t in suggestions[:3]]
        assert any("arterial blood pressure" in t or "blood pressure" in t for t in top_3_lower)


@pytest.mark.asyncio
async def test_api_fallback_without_ai():
    """
    Requirement 5: API FALLBACK
    - Feature works when no AI API key is configured.
    - Exact matching works, fuzzy matching works, aliases work, syllabus suggestions work.
    """
    # Directly test the fallback logic in ExamSyllabusAIService
    available_units = ["General Anatomy", "Upper Limb", "Lower Limb", "Thorax", "Head & Neck"]

    # 1. Exact match works without AI
    match1 = await ExamSyllabusAIService.match_portion_hybrid("Anatomy", "anatomy", "Thorax", available_units)
    assert match1["matched_portion"] == "Thorax"
    assert match1["confidence"] == "high"

    # 2. Medical alias works without AI
    match2 = await ExamSyllabusAIService.match_portion_hybrid("Anatomy", "anatomy", "arm", available_units)
    assert match2["matched_portion"] == "Upper Limb"
    assert match2["confidence"] == "high"

    # 3. Fuzzy substring works without AI
    match3 = await ExamSyllabusAIService.match_portion_hybrid("Anatomy", "anatomy", "head", available_units)
    assert match3["matched_portion"] == "Head & Neck"
    assert match3["confidence"] == "high"

    # 4. Unknown string yields low confidence
    match4 = await ExamSyllabusAIService.match_portion_hybrid("Anatomy", "anatomy", "unrelated topic", available_units)
    assert match4["confidence"] == "low"
    assert match4["matched_portion"] is None


@pytest.mark.asyncio
async def test_study_planner_connection_with_hybrid_topics():
    """
    Requirement 8: STUDY PLANNER CONNECTION
    - Only validated exam topics should feed Study Planner.
    - Preserves: Exam -> Subject -> Portion -> Topic -> Importance / Weightage.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"hybrid_planner_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Hybrid Planner Student",
            "year_of_study": "MBBS 1st Year"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        subjs = (await ac.get("/api/subjects/", headers=headers)).json()
        s_anat = next(s for s in subjs if "anat" in s["name"].lower())

        # Step 1: Query hybrid suggestions for "upper extremity nerves"
        res_sugg = await ac.get(
            f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=upper extremity nerves",
            headers=headers
        )
        assert res_sugg.status_code == 200
        matched_portion = res_sugg.json()["matched_portion"]
        suggestions = res_sugg.json()["suggestions"]
        assert matched_portion == "Upper Limb"
        assert len(suggestions) >= 2

        # Step 2: Create Exam using verified topics
        today = date.today()
        exam_date = today + timedelta(days=3)
        chosen_topics = [suggestions[0], suggestions[1]]
        create_exam = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_anat["id"],
            "name": "Upper Limb Internal",
            "exam_date": exam_date.isoformat(),
            "syllabus_portion": matched_portion,
            "target_score": 85.0,
            "important_topics": chosen_topics
        })
        assert create_exam.status_code == 200
        exam_data = create_exam.json()
        assert exam_data["syllabus_portion"] == "Upper Limb"
        assert exam_data["important_topics"] == chosen_topics

        # Step 3: Generate Study Plan
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 2,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"]],
            "planning_style": "priority_aware"
        })
        assert plan_res.status_code == 200
        tasks = plan_res.json()["tasks"]
        assert len(tasks) > 0

        # Study Planner tasks should carry the syllabus portion and verified topic names
        matched_task = next(
            (t for t in tasks if t["subject_id"] == s_anat["id"] and any(ct.lower() in t["title"].lower() for ct in chosen_topics)),
            None
        )
        assert matched_task is not None
        assert matched_task.get("syllabus_portion") == "Upper Limb"
        assert matched_task["priority"] == "high"
