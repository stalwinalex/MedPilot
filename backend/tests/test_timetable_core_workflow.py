import uuid
import pytest
from datetime import date, time, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_timetable_core_workflow_end_to_end():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"workflow_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Core Workflow Student",
            "college": "KMC Manipal",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Verify 0/0 attendance bug fix:
        # Initially, with 0 classes conducted, overall_percentage must be None (rendered as '—', NOT 100%)
        summary_res = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert summary["total_conducted"] == 0
        assert summary["overall_percentage"] is None
        assert summary["pending_confirmations"] == []

        # 2. Add Subject: Pharmacology
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Pharmacology",
            "code": "PHARM",
            "color": "#10B981",
            "target_attendance": 75.0,
            "faculty": "Dr. Reddy"
        })
        assert subj_res.status_code == 200
        pharm = subj_res.json()

        # 3. Create Recurring Rule: Friday at 09:00 - 10:00
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": pharm["id"],
            "day_of_week": 4,  # Friday
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "faculty": "Dr. Reddy",
            "room": "LH-3"
        })
        assert rule_res.status_code == 200
        rule = rule_res.json()

        # 4. Verify Duplicate Prevention across repeated occurrence generations
        today = date.today()
        start_d = today - timedelta(days=today.weekday())
        end_d = start_d + timedelta(days=20)  # 3 Fridays

        occs_res1 = await ac.get(f"/api/timetable/occurrences?start_date={start_d}&end_date={end_d}", headers=headers)
        assert occs_res1.status_code == 200
        count1 = len([o for o in occs_res1.json() if o["rule_id"] == rule["id"]])
        assert count1 == 3

        # Call again (simulating multiple page reloads / refreshes)
        occs_res2 = await ac.get(f"/api/timetable/occurrences?start_date={start_d}&end_date={end_d}", headers=headers)
        assert occs_res2.status_code == 200
        count2 = len([o for o in occs_res2.json() if o["rule_id"] == rule["id"]])
        # Must be EXACTLY 3, zero duplicate occurrences created!
        assert count2 == count1

        # 5. Atomic Check-in: Mark class as present with topic covered
        pharm_occs = [o for o in occs_res2.json() if o["rule_id"] == rule["id"]]
        occ_to_checkin = pharm_occs[0]

        checkin_res = await ac.post("/api/attendance/check-in", headers=headers, json={
            "occurrence_id": occ_to_checkin["id"],
            "status": "present",
            "topic_title": "Autonomic Nervous System: Cholinergic Agonists",
            "notes": "Covered Pilocarpine and Neostigmine"
        })
        assert checkin_res.status_code == 200
        checked_in = checkin_res.json()
        assert checked_in["status"] == "completed"
        assert checked_in["attendance"]["status"] == "present"
        assert len(checked_in["topics"]) >= 1
        assert any(t["title"] == "Autonomic Nervous System: Cholinergic Agonists" for t in checked_in["topics"])

        # 6. Verify Attendance Recalculation after Check-in:
        # Now: 1 conducted, 1 attended -> 100.0%
        summary_res2 = await ac.get("/api/attendance/summary", headers=headers)
        summary2 = summary_res2.json()
        assert summary2["total_conducted"] == 1
        assert summary2["total_attended"] == 1
        assert summary2["overall_percentage"] == 100.0

        # 7. Cancelled Class Reversibility:
        # Cancel the second occurrence
        occ_to_cancel = pharm_occs[1]
        cancel_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_to_cancel["id"],
            "status": "cancelled"
        })
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # Cancelled class must NOT increase conducted count (still 1, not 2)
        summary_res3 = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res3.json()["total_conducted"] == 1

        # Reverse cancellation back to present!
        uncancel_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ_to_cancel["id"],
            "status": "present"
        })
        assert uncancel_res.status_code == 200
        assert uncancel_res.json()["status"] == "present"

        # Now total conducted should be 2 (both attended -> 100%)
        summary_res4 = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res4.json()["total_conducted"] == 2
        assert summary_res4.json()["total_attended"] == 2

        # 8. Update Rule & Future Occurrences:
        # Change rule time to 11:00 - 12:00 and room to "Hall A"
        update_rule_res = await ac.put(f"/api/timetable/rules/{rule['id']}", headers=headers, json={
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "room": "Hall A",
            "update_future_occurrences": True
        })
        assert update_rule_res.status_code == 200
        updated_rule = update_rule_res.json()
        assert updated_rule["room"] == "Hall A"
        assert updated_rule["start_time"] == "11:00:00"

        # Check future occurrence 3: should have updated room and time
        occs_res3 = await ac.get(f"/api/timetable/occurrences?start_date={start_d}&end_date={end_d}", headers=headers)
        occ3 = next(o for o in occs_res3.json() if o["id"] == pharm_occs[2]["id"])
        assert occ3["room"] == "Hall A"
        assert occ3["start_time"] == "11:00:00"

        # But occurrence 1 (which was completed/attended) should remain intact!
        occ1_check = next(o for o in occs_res3.json() if o["id"] == occ_to_checkin["id"])
        assert occ1_check["attendance"]["status"] == "present"


@pytest.mark.asyncio
async def test_edit_class_from_9_to_10_to_11_and_refresh_persists():
    """
    Test requirement:
    Edit one class from 9:00-10:00 to 10:00-11:00, save it, refresh the page,
    confirm the new time remains, ensure zero duplicates, and confirm cancelled classes
    are editable and reversible.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"edit_test_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Edit Bug Student",
            "college": "KMC Manipal",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Add subject
        subj_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Anatomy",
            "code": "ANAT",
            "color": "#14B8A6",
            "target_attendance": 75.0,
            "faculty": "Dr. Original"
        })
        assert subj_res.status_code == 200
        subj = subj_res.json()

        # 2. Create rule: Monday 09:00:00 - 10:00:00 starting from Monday
        today = date.today()
        mon = today - timedelta(days=today.weekday())
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": subj["id"],
            "day_of_week": 0,  # Monday
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "faculty": "Dr. Original",
            "room": "Room-101",
            "effective_from": mon.isoformat()
        })
        assert rule_res.status_code == 200
        rule = rule_res.json()

        # 3. Fetch occurrences for Monday
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={mon}&end_date={mon}", headers=headers)
        assert occs_res.status_code == 200
        occs = occs_res.json()
        assert len(occs) == 1
        occ = occs[0]
        assert occ["start_time"] == "09:00:00"
        assert occ["end_time"] == "10:00:00"

        # 4. Edit occurrence: from 9:00-10:00 to 10:00-11:00 with date and updated faculty/room
        edit_res = await ac.put(f"/api/timetable/occurrences/{occ['id']}", headers=headers, json={
            "subject_id": subj["id"],
            "date": occ["date"],
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Updated",
            "room": "Room-202",
            "status": "scheduled",
            "notes": "Shifted by 1 hour"
        })
        assert edit_res.status_code == 200, f"Edit failed with: {edit_res.text}"
        updated_occ = edit_res.json()
        assert updated_occ["start_time"] == "10:00:00"
        assert updated_occ["end_time"] == "11:00:00"
        assert updated_occ["faculty"] == "Dr. Updated"
        assert updated_occ["room"] == "Room-202"

        # 5. Refresh page / re-fetch occurrences
        refresh_res = await ac.get(f"/api/timetable/occurrences?start_date={mon}&end_date={mon}", headers=headers)
        assert refresh_res.status_code == 200
        refreshed_occs = refresh_res.json()

        # CONFIRM: Exactly 1 occurrence exists (no duplicates generated on refresh)
        assert len(refreshed_occs) == 1
        persisted = refreshed_occs[0]
        # CONFIRM: The new time remains!
        assert persisted["start_time"] == "10:00:00"
        assert persisted["end_time"] == "11:00:00"
        assert persisted["faculty"] == "Dr. Updated"
        assert persisted["room"] == "Room-202"

        # 6. Test cancelled class edit and reversibility
        # Cancel the occurrence
        cancel_res = await ac.post(f"/api/timetable/occurrences/{persisted['id']}/toggle-cancel", headers=headers)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # Edit the cancelled occurrence (change room while cancelled)
        edit_cancelled_res = await ac.put(f"/api/timetable/occurrences/{persisted['id']}", headers=headers, json={
            "subject_id": subj["id"],
            "date": persisted["date"],
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Updated",
            "room": "Room-Cancelled-Edit",
            "status": "cancelled"
        })
        assert edit_cancelled_res.status_code == 200
        assert edit_cancelled_res.json()["status"] == "cancelled"
        assert edit_cancelled_res.json()["room"] == "Room-Cancelled-Edit"

        # Reverse/restore the class back to scheduled
        restore_res = await ac.put(f"/api/timetable/occurrences/{persisted['id']}", headers=headers, json={
            "status": "scheduled"
        })
        assert restore_res.status_code == 200
        restored = restore_res.json()
        assert restored["status"] == "scheduled"
        assert restored["attendance"]["status"] == "not_marked"

        # Re-fetch on refresh
        final_refresh = await ac.get(f"/api/timetable/occurrences?start_date={mon}&end_date={mon}", headers=headers)
        assert len(final_refresh.json()) == 1
        assert final_refresh.json()[0]["start_time"] == "10:00:00"
        assert final_refresh.json()[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_day_schedule_batch_and_grid_parser():
    from app.services.timetable_parser_service import TimetableParserService

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"batch_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Batch Entry Student",
            "college": "AIIMS New Delhi",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create 2 subjects
        s1 = (await ac.post("/api/subjects/", headers=headers, json={"name": "Pathology", "code": "PATH"})).json()
        s2 = (await ac.post("/api/subjects/", headers=headers, json={"name": "Biochemistry", "code": "BIO"})).json()

        # 2. Batch add full day schedule (3 slots) for Monday (day_of_week=0) and also apply to Tuesday (day_of_week=1)
        today = date.today()
        mon = today - timedelta(days=today.weekday())
        batch_res = await ac.post("/api/timetable/rules/batch", headers=headers, json={
            "day_of_week": 0,
            "apply_to_days": [1],
            "replace_existing": True,
            "effective_from": mon.isoformat(),
            "slots": [
                {
                    "subject_id": s1["id"],
                    "start_time": "08:00:00",
                    "end_time": "09:00:00",
                    "faculty": "Dr. Sharma",
                    "room": "LT-1"
                },
                {
                    "subject_id": s2["id"],
                    "start_time": "09:00:00",
                    "end_time": "10:00:00",
                    "faculty": "Dr. Rao",
                    "room": "LT-2"
                },
                {
                    "subject_id": s1["id"],
                    "start_time": "10:00:00",
                    "end_time": "11:00:00",
                    "faculty": "Dr. Sharma",
                    "room": "Lab-1"
                }
            ]
        })
        assert batch_res.status_code == 200, batch_res.text
        rules = batch_res.json()
        assert len(rules) == 6  # 3 on Mon, 3 on Tue

        # Verify occurrences were generated for Monday
        today = date.today()
        mon = today - timedelta(days=today.weekday())
        tue = mon + timedelta(days=1)
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={mon}&end_date={tue}", headers=headers)
        assert occs_res.status_code == 200
        occs = occs_res.json()
        mon_occs = [o for o in occs if o["date"] == str(mon)]
        tue_occs = [o for o in occs if o["date"] == str(tue)]
        assert len(mon_occs) == 3
        assert len(tue_occs) == 3
        assert mon_occs[0]["start_time"] == "08:00:00"
        assert mon_occs[1]["start_time"] == "09:00:00"
        assert mon_occs[2]["start_time"] == "10:00:00"

        # 3. Test 2D Table Grid reconstruction in TimetableParserService
        grid_text = (
            "Time | 8:00 - 9:00 | 9:00 - 10:00 | 10:00 - 11:00\n"
            "Monday | Pathology | Biochemistry | Dissection\n"
            "Tuesday | Anatomy | Physiology | Pathology\n"
        )
        parsed_items = TimetableParserService.parse_timetable_text(grid_text, [])
        assert len(parsed_items) == 6
        assert parsed_items[0].day_of_week == 0
        assert parsed_items[0].start_time == "08:00"
        assert parsed_items[0].end_time == "09:00"
        assert parsed_items[0].subject_name == "Pathology"

        assert parsed_items[1].start_time == "09:00"
        assert parsed_items[1].end_time == "10:00"
        assert parsed_items[1].subject_name == "Biochemistry"

        assert parsed_items[3].day_of_week == 1
        assert parsed_items[3].start_time == "08:00"
        assert parsed_items[3].subject_name == "Anatomy"


