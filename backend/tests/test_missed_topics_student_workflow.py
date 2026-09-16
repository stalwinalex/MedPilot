import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from app.main import app


@pytest.mark.asyncio
async def test_missed_topics_student_friendly_workflow():
    """
    Verifies the student-friendly Missed Class Topics section:
    - Clear Subject (e.g. Physiology)
    - Missed class date (e.g. 10 Sept)
    - Multiple topics recorded for one missed class shown separately with independent controls
    - Actions: [ Study ] [ Later ] [ Skip ]
    - Snooze topic until tomorrow / 3 days / 1 week / custom date
    - Skip topic excludes from plan but retains in class history (never deleted)
    - Allow skipped topics to be restored
    - No vague labels like "Medical Subject" or "Medical Topic"
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        uid = uuid.uuid4().hex[:8]
        reg_res = await ac.post("/api/auth/register", json={
            "email": f"physio_student_{uid}@medpilot.test",
            "password": "Password123!",
            "full_name": "Physiology Scholar",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200, reg_res.text
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create or fetch Physiology subject
        subj_res = await ac.get("/api/subjects/", headers=headers)
        subjects = subj_res.json()
        physio_subj = next((s for s in subjects if "physio" in s["name"].lower()), None)
        if not physio_subj:
            new_s = await ac.post("/api/subjects/", headers=headers, json={
                "name": "Physiology",
                "color": "#72C9BE",
                "target_attendance": 75.0
            })
            physio_subj = new_s.json()

        # Add a missed class on 10 Sept
        missed_class_date = date(2026, 9, 10)
        occ_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": physio_subj["id"],
            "date": missed_class_date.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "completed"
        })
        assert occ_res.status_code == 200
        occ_id = occ_res.json()["id"]

        # Record 2 separate topics for this single class
        top1_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Cardiac Cycle",
            "description": "Ventricular systole and diastole phases"
        })
        assert top1_res.status_code == 200
        t1 = top1_res.json()

        top2_res = await ac.post(f"/api/timetable/occurrences/{occ_id}/topics", headers=headers, json={
            "title": "Action Potential",
            "description": "Depolarization and repolarization in cardiac myocytes"
        })
        assert top2_res.status_code == 200
        t2 = top2_res.json()

        # Mark attendance absent
        att_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_id,
            "status": "absent"
        })
        assert att_res.status_code == 200

        # Step 1: Query GET /api/planner/missed-topics
        mt_res = await ac.get("/api/planner/missed-topics", headers=headers)
        assert mt_res.status_code == 200
        missed_data = mt_res.json()

        occ_item = next((m for m in missed_data if m["occurrence_id"] == occ_id), None)
        assert occ_item is not None, "Missed class occurrence must appear in /planner/missed-topics"

        # Verify real Subject name and date are present (no generic labels)
        assert occ_item["subject_name"] == "Physiology"
        assert occ_item["subject"]["name"] == "Physiology"
        assert occ_item["date"] == "2026-09-10"
        assert occ_item["class_date"] == "2026-09-10"

        # Verify both topics are returned separately
        assert len(occ_item["topics"]) == 2
        topic_titles = [top["title"] for top in occ_item["topics"]]
        assert "Cardiac Cycle" in topic_titles
        assert "Action Potential" in topic_titles

        topic_cardiac = next(t for t in occ_item["topics"] if t["title"] == "Cardiac Cycle")
        topic_action = next(t for t in occ_item["topics"] if t["title"] == "Action Potential")
        assert topic_cardiac["study_status"] == "study"
        assert topic_action["study_status"] == "study"

        # Step 2: Test [ Later ] action on "Cardiac Cycle"
        # Snooze for 3 days
        snooze_target = (date.today() + timedelta(days=3)).isoformat()
        snooze_res = await ac.put(f"/api/planner/topics/{topic_cardiac['id']}/status", headers=headers, json={
            "study_status": "later",
            "snooze_until": snooze_target
        })
        assert snooze_res.status_code == 200
        snoozed_data = snooze_res.json()
        assert snoozed_data["study_status"] == "later"
        assert snoozed_data["snooze_until"] == snooze_target

        # Verify "Action Potential" remained independently in 'study' status
        mt_res2 = await ac.get("/api/planner/missed-topics", headers=headers)
        occ_item2 = next(m for m in mt_res2.json() if m["occurrence_id"] == occ_id)
        t_cardiac_check = next(t for t in occ_item2["topics"] if t["id"] == topic_cardiac["id"])
        t_action_check = next(t for t in occ_item2["topics"] if t["id"] == topic_action["id"])
        assert t_cardiac_check["study_status"] == "later"
        assert t_action_check["study_status"] == "study"

        # Step 3: Test [ Skip ] action on "Action Potential"
        skip_res = await ac.put(f"/api/planner/topics/{topic_action['id']}/status", headers=headers, json={
            "study_status": "skip",
            "skip_reason": "already_know"
        })
        assert skip_res.status_code == 200
        skipped_data = skip_res.json()
        assert skipped_data["study_status"] == "skip"
        assert skipped_data["skip_reason"] == "already_know"

        # CRITICAL REQUIREMENT: Do not delete the class/topic when skipped!
        occ_history = await ac.get(f"/api/timetable/occurrences/{occ_id}", headers=headers)
        assert occ_history.status_code == 200
        assert len(occ_history.json()["topics"]) == 2, "Skipped topic must NOT be deleted from class history"

        # Step 4: Test [ Restore ] on skipped topic
        restore_res = await ac.post(f"/api/planner/topics/{topic_action['id']}/restore", headers=headers)
        assert restore_res.status_code == 200
        restored_data = restore_res.json()
        assert restored_data["study_status"] == "study"
        assert restored_data["skip_reason"] is None
        assert restored_data["snooze_until"] is None

        # Step 5: Test [ Study ] action on previously snoozed topic
        study_res = await ac.put(f"/api/planner/topics/{topic_cardiac['id']}/status", headers=headers, json={
            "study_status": "study"
        })
        assert study_res.status_code == 200
        study_data = study_res.json()
        assert study_data["study_status"] == "study"
        assert study_data["snooze_until"] is None
