import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from app.main import app


@pytest.mark.asyncio
async def test_subject_topic_suggestions_and_academic_context():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_topics_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Topics Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200, reg.text
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Retrieve subjects seeded for 1st Year
        subj_res = await ac.get("/api/subjects/", headers=headers)
        assert subj_res.status_code == 200
        subjects = subj_res.json()

        s_anat = next((s for s in subjects if "anat" in s["name"].lower()), None)
        s_phys = next((s for s in subjects if "phys" in s["name"].lower()), None)
        s_biochem = next((s for s in subjects if "biochem" in s["name"].lower()), None)

        assert s_anat is not None
        assert s_phys is not None
        assert s_biochem is not None

        # 1. Anatomy suggestions
        res_anat = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_anat['id']}", headers=headers)
        assert res_anat.status_code == 200
        anat_data = res_anat.json()
        assert anat_data["subject_name"] == s_anat["name"]
        assert len(anat_data["suggestions"]) > 0
        # Should contain anatomy-relevant topics
        anat_text = " ".join(anat_data["suggestions"]).lower()
        assert any(kw in anat_text for kw in ["brachial plexus", "upper limb", "lower limb", "femoral", "thorax", "cranial"])
        # Should not contain unrelated clinical cardiology/pathology syndromes
        assert "heart failure" not in anat_text

        # 2. Physiology suggestions
        res_phys = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_phys['id']}", headers=headers)
        assert res_phys.status_code == 200
        phys_data = res_phys.json()
        phys_text = " ".join(phys_data["suggestions"]).lower()
        assert any(kw in phys_text for kw in ["action potential", "cardiac cycle", "ecg", "respiratory", "gfr", "synapse"])

        # 3. Biochemistry suggestions
        res_biochem = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_biochem['id']}", headers=headers)
        assert res_biochem.status_code == 200
        biochem_data = res_biochem.json()
        biochem_text = " ".join(biochem_data["suggestions"]).lower()
        assert any(kw in biochem_text for kw in ["glycolysis", "krebs", "tca", "fatty acid", "gluconeogenesis", "enzyme"])

        # 4. Prioritizing recorded class topics:
        # Create a class occurrence with a specific topic for Anatomy
        occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": (date.today() - timedelta(days=2)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "completed",
            "topics": ["Cubital Fossa & Anastomosis"]
        })
        assert occ_res.status_code == 200

        # Now check topic suggestions for Anatomy again: "Cubital Fossa & Anastomosis" should be prioritized at the top
        res_anat_updated = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_anat['id']}", headers=headers)
        assert res_anat_updated.status_code == 200
        updated_suggestions = res_anat_updated.json()["suggestions"]
        assert any("cubital fossa" in s.lower() for s in updated_suggestions[:3])


@pytest.mark.asyncio
async def test_topic_validation_and_gentle_warning():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_val_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Validation Student",
            "year_of_study": "MBBS 1st Year"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        s_anat = next(s for s in subjects if "anat" in s["name"].lower())

        # Test A: Cross-subject mismatch ("Heart Failure" for Anatomy)
        val_mismatch = await ac.post("/api/exams/validate-topic", headers=headers, json={
            "subject_id": s_anat["id"],
            "topic": "Heart Failure"
        })
        assert val_mismatch.status_code == 200
        resp_mismatch = val_mismatch.json()
        assert resp_mismatch["is_valid"] is False
        assert "Pathology / Medicine" in resp_mismatch["warning"]
        assert resp_mismatch["suggested_subject"] == "Pathology / Medicine"

        # Test B: Subject-appropriate topic ("Brachial Plexus" for Anatomy)
        val_ok = await ac.post("/api/exams/validate-topic", headers=headers, json={
            "subject_id": s_anat["id"],
            "topic": "Brachial Plexus and its branches"
        })
        assert val_ok.status_code == 200
        resp_ok = val_ok.json()
        assert resp_ok["is_valid"] is True
        assert resp_ok["warning"] is None


@pytest.mark.asyncio
async def test_non_destructive_existing_exam_inspection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_audit_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Audit Student",
            "year_of_study": "MBBS 1st Year"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.get("/api/subjects/", headers=headers)
        s_anat = next(s for s in subj_res.json() if "anat" in s["name"].lower())

        # Student adds an exam with a mismatched topic (allowed with 'Add Anyway')
        create_res = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_anat["id"],
            "name": "Anatomy Midterm",
            "exam_date": (date.today() + timedelta(days=5)).isoformat(),
            "target_score": 80.0,
            "important_topics": ["Heart Failure", "Femoral Triangle"]
        })
        assert create_res.status_code == 200
        exam_id = create_res.json()["id"]

        # Fetch exams via GET /exams/
        get_res = await ac.get("/api/exams/", headers=headers)
        assert get_res.status_code == 200
        exams = get_res.json()
        target_exam = next((e for e in exams if e["id"] == exam_id), None)
        assert target_exam is not None

        # Data integrity preserved
        assert "Heart Failure" in target_exam["important_topics"]
        assert "Femoral Triangle" in target_exam["important_topics"]

        # Non-destructive warning attached
        assert target_exam.get("topic_warnings") is not None
        warnings = target_exam["topic_warnings"]
        assert len(warnings) == 1
        assert warnings[0]["topic"] == "Heart Failure"
        assert "Pathology / Medicine" in warnings[0]["warning"]


@pytest.mark.asyncio
async def test_study_planner_combined_evidence_and_non_blind_prioritization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_plan_ev_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Test Plan Evidence Student",
            "year_of_study": "MBBS 1st Year"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        s_anat = next(s for s in subjects if "anat" in s["name"].lower())
        s_phys = next(s for s in subjects if "phys" in s["name"].lower())

        today = date.today()

        # 1. Anatomy has an upcoming exam in 3 days with "Brachial Plexus"
        exam_res = await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_anat["id"],
            "name": "Anatomy Block Exam",
            "exam_date": (today + timedelta(days=3)).isoformat(),
            "exam_type": "Internal Assessment",
            "target_score": 85.0,
            "important_topics": ["Brachial Plexus"]
        })
        assert exam_res.status_code == 200

        # 2. Student was absent for a class covering "Brachial Plexus" 2 days ago
        occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": s_anat["id"],
            "date": (today - timedelta(days=2)).isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed",
            "topics": ["Brachial Plexus"]
        })
        assert occ_res.status_code == 200
        occ_id = occ_res.json()["id"]

        # Mark absent
        att_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "absent",
            "notes": "Doctor appointment"
        })
        assert att_res.status_code == 200

        # 3. Physiology has a distant exam in 25 days (not imminent)
        await ac.post("/api/exams/", headers=headers, json={
            "subject_id": s_phys["id"],
            "name": "Physiology University Prof",
            "exam_date": (today + timedelta(days=25)).isoformat(),
            "exam_type": "University Prof Exam",
            "target_score": 75.0,
            "important_topics": ["Action Potential"]
        })

        # Generate 1-day plan with 2 hours (120 mins) available time
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"], s_phys["id"]],
            "planning_style": "priority"
        })
        assert plan_res.status_code == 200
        plan_data = plan_res.json()
        tasks = plan_data["tasks"]

        # Verify Anatomy Brachial Plexus task
        anat_task = next((t for t in tasks if t["subject_id"] == s_anat["id"] and "brachial" in t["title"].lower()), None)
        assert anat_task is not None, "Expected study task for Brachial Plexus"

        # Check explainable reason format
        reason = anat_task.get("reason", "")
        assert "Exam in 3 days" in reason or "Exam in 2 days" in reason or "Exam" in reason
        assert "High-priority" in reason or "Designated" in reason
        # Check missed class connection
        assert "Missed class" in reason
        assert anat_task.get("missed_class_date") is not None

        # Verify planning score reflects combined evidence
        assert anat_task.get("planning_score", 0) > 10.0, f"Score should reflect combined evidence: {anat_task.get('planning_score')}"

        # Verify non-blind prioritization:
        # The distant 25-day exam in Physiology should NOT starve or receive identical priority to the urgent 3-day exam + missed class
        phys_task = next((t for t in tasks if t["subject_id"] == s_phys["id"]), None)
        if phys_task:
            assert anat_task["planning_score"] > phys_task["planning_score"], (
                f"Urgent exam + missed class ({anat_task['planning_score']}) must outscore distant 25-day exam ({phys_task['planning_score']})"
            )
            assert anat_task["estimated_minutes"] >= phys_task["estimated_minutes"]


@pytest.mark.asyncio
async def test_dynamic_multi_subject_and_portion_filtering_cases():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg = await ac.post("/api/auth/register", json={
            "email": f"test_portions_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Portion Test Student",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subj_res = await ac.get("/api/subjects/", headers=headers)
        assert subj_res.status_code == 200
        subjects = subj_res.json()

        s_anat = next(s for s in subjects if "anat" in s["name"].lower())
        s_phys = next(s for s in subjects if "phys" in s["name"].lower())
        s_biochem = next(s for s in subjects if "biochem" in s["name"].lower())

        # =========================================================================
        # Case 1: Anatomy -> Upper Limb
        # =========================================================================
        res_anat_ul = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_anat['id']}&portion=Upper Limb", headers=headers)
        assert res_anat_ul.status_code == 200
        ul_data = res_anat_ul.json()
        assert ul_data["portion"] == "Upper Limb"
        assert "Upper Limb" in ul_data["available_portions"]
        assert "Lower Limb" in ul_data["available_portions"]
        assert len(ul_data["suggestions"]) > 0

        ul_text = " ".join(ul_data["suggestions"]).lower()
        # Must contain Upper Limb topics
        assert "brachial plexus" in ul_text
        assert any(kw in ul_text for kw in ["axilla", "cubital fossa", "median nerve", "carpal tunnel"])
        # Must NOT contain Lower Limb topics
        assert "femoral" not in ul_text
        assert "popliteal" not in ul_text
        # Must NOT contain unrelated heart failure
        assert "heart failure" not in ul_text

        # =========================================================================
        # Case 2: Physiology -> Cardiovascular System
        # =========================================================================
        res_phys_cvs = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_phys['id']}&portion=Cardiovascular System", headers=headers)
        assert res_phys_cvs.status_code == 200
        cvs_data = res_phys_cvs.json()
        assert cvs_data["portion"] == "Cardiovascular System"
        assert "Cardiovascular System" in cvs_data["available_portions"]
        assert "Respiratory System" in cvs_data["available_portions"]
        assert len(cvs_data["suggestions"]) > 0

        cvs_text = " ".join(cvs_data["suggestions"]).lower()
        # Must contain CVS topics
        assert "cardiac cycle" in cvs_text
        assert "ecg" in cvs_text
        assert any(kw in cvs_text for kw in ["blood pressure", "cardiac output", "frank-starling"])
        # Must NOT contain Respiratory or Anatomy topics
        assert "spirometry" not in cvs_text
        assert "brachial plexus" not in cvs_text

        # =========================================================================
        # Case 3: Biochemistry -> Carbohydrate Metabolism
        # =========================================================================
        res_bio_cho = await ac.get(f"/api/exams/topic-suggestions?subject_id={s_biochem['id']}&portion=Carbohydrate Metabolism", headers=headers)
        assert res_bio_cho.status_code == 200
        cho_data = res_bio_cho.json()
        assert cho_data["portion"] == "Carbohydrate Metabolism"
        assert "Carbohydrate Metabolism" in cho_data["available_portions"]
        assert "Lipid Metabolism" in cho_data["available_portions"]
        assert len(cho_data["suggestions"]) > 0

        cho_text = " ".join(cho_data["suggestions"]).lower()
        # Must contain Carbohydrate Metabolism topics
        assert "glycolysis" in cho_text
        assert any(kw in cho_text for kw in ["tca", "citric acid", "gluconeogenesis", "glycogen"])
        # Must NOT contain Lipid Metabolism or Anatomy
        assert "beta-oxidation" not in cho_text
        assert "ketone" not in cho_text
        assert "brachial" not in cho_text

        # =========================================================================
        # Case 4: Non-blocking warning & syllabus_portion persistence on Exam
        # =========================================================================
        # Gentle warning for mismatch
        warn_check = await ac.post("/api/exams/validate-topic", headers=headers, json={
            "subject_id": s_anat["id"],
            "topic": "Heart Failure"
        })
        assert warn_check.status_code == 200
        warn_data = warn_check.json()
        assert warn_data["is_valid"] is False
        assert "This topic may not belong to the selected subject. Add anyway?" in warn_data["warning"]

        # Student clicks "Add Anyway" and saves exam with portion & topics
        today = date.today()
        exam_payload = {
            "subject_id": s_anat["id"],
            "name": "Anatomy Upper Limb Term Exam",
            "syllabus_portion": "Upper Limb",
            "exam_date": (today + timedelta(days=2)).isoformat(),
            "exam_type": "Internal Assessment",
            "target_score": 85.0,
            "important_topics": ["Brachial Plexus", "Axillary Artery & Axilla", "Heart Failure"]
        }
        create_exam_res = await ac.post("/api/exams/", headers=headers, json=exam_payload)
        assert create_exam_res.status_code == 200
        created_exam = create_exam_res.json()
        assert created_exam["syllabus_portion"] == "Upper Limb"
        assert "Brachial Plexus" in created_exam["important_topics"]
        assert "Heart Failure" in created_exam["important_topics"]
        # Topic warning attached non-destructively
        assert len(created_exam["topic_warnings"]) == 1
        assert created_exam["topic_warnings"][0]["topic"] == "Heart Failure"

        # =========================================================================
        # Case 5: Study Planner inherits and surfaces syllabus_portion
        # =========================================================================
        plan_res = await ac.post("/api/planner/generate", headers=headers, json={
            "plan_days": 1,
            "study_hours": 2,
            "study_minutes": 0,
            "subject_mode": "choose",
            "subject_ids": [s_anat["id"]],
            "planning_style": "priority"
        })
        assert plan_res.status_code == 200
        plan_data = plan_res.json()
        tasks = plan_data["tasks"]
        assert len(tasks) > 0

        # Verify task carries syllabus_portion = "Upper Limb"
        ul_task = next((t for t in tasks if t["subject_id"] == s_anat["id"] and "brachial" in t["title"].lower()), None)
        assert ul_task is not None
        assert ul_task.get("syllabus_portion") == "Upper Limb"
        assert "Unit: Upper Limb" in ul_task.get("reason", "") or "Unit: Upper Limb" in ul_task.get("description", "")

