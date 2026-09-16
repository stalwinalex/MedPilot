import pytest
import pytest_asyncio
import uuid
from datetime import date, time, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine, Base
from app.core.security import create_access_token
from app.models.models import Profile, Subject, TimetableRule, ClassOccurrence, ClassTopic, Attendance


@pytest_asyncio.fixture(autouse=True)
async def init_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_full_attendance_and_timetable_edge_cases():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"att_test_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Test Student",
            "college": "Medical College",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        subjs = subjs_res.json()
        anat = next(s for s in subjs if s["name"] == "Anatomy")
        phys = next(s for s in subjs if s["name"] == "Physiology")

        # 1. Add recurring rule: Every Monday at 10:00 AM Anatomy
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": anat["id"],
            "day_of_week": 0,  # Monday
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "faculty": "Dr. Anatomist",
            "room": "Dissection Hall"
        })
        assert rule_res.status_code == 200

        # 2. Get occurrences for next 14 days
        today = date.today()
        start_d = today - timedelta(days=today.weekday())
        end_d = start_d + timedelta(days=13)
        occs_res = await ac.get(f"/api/timetable/occurrences?start_date={start_d}&end_date={end_d}", headers=headers)
        assert occs_res.status_code == 200
        occs = occs_res.json()
        anat_occs = [o for o in occs if o["subject_id"] == anat["id"]]
        assert len(anat_occs) >= 2

        occ1 = anat_occs[0]
        occ2 = anat_occs[1]

        # 3. Add Multiple topics to occ1
        t1_res = await ac.post(f"/api/timetable/occurrences/{occ1['id']}/topics", headers=headers, json={
            "title": "Cubital Fossa Boundaries & Contents",
            "order_index": 0
        })
        assert t1_res.status_code == 200

        t2_res = await ac.post(f"/api/timetable/occurrences/{occ1['id']}/topics", headers=headers, json={
            "title": "Median Nerve Pathway & Compression Sites",
            "order_index": 1
        })
        assert t2_res.status_code == 200

        # 4. Mark occ1 as PRESENT
        mark_res1 = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ1["id"],
            "status": "present"
        })
        assert mark_res1.status_code == 200

        # 5. Add Extra Class (Ad-hoc)
        extra_res = await ac.post("/api/timetable/occurrences", headers=headers, json={
            "subject_id": phys["id"],
            "date": str(today),
            "start_time": "15:00:00",
            "end_time": "16:00:00",
            "faculty": "Dr. Physiologist",
            "room": "Seminar Room",
            "is_extra_class": True,
            "topics": ["Renal Clearance & GFR Calculation"]
        })
        assert extra_res.status_code == 200
        extra_occ = extra_res.json()
        assert extra_occ["is_extra_class"] is True

        # 6. Mark extra class as ABSENT
        mark_res2 = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": extra_occ["id"],
            "status": "absent"
        })
        assert mark_res2.status_code == 200

        # 7. Check attendance summary:
        # Anatomy: 1 conducted, 1 attended -> 100%
        # Physiology: 1 conducted, 0 attended, 1 missed -> 0%
        # Overall: 2 conducted, 1 attended -> 50%
        summary_res = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert summary["total_conducted"] == 2
        assert summary["total_attended"] == 1
        assert summary["total_missed"] == 1
        assert summary["overall_percentage"] == 50.0

        # 8. Cancel occ2 (Second Anatomy class)
        cancel_res = await ac.put(f"/api/timetable/occurrences/{occ2['id']}", headers=headers, json={
            "status": "cancelled"
        })
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # 9. Verify Cancelled class does NOT affect attendance or increase conducted count
        summary_res2 = await ac.get("/api/attendance/summary", headers=headers)
        summary2 = summary_res2.json()
        assert summary2["total_conducted"] == 2  # Still 2, NOT 3!
        assert summary2["overall_percentage"] == 50.0

        # Cancelled classes are reversible: student can un-cancel and mark attendance directly
        reverse_mark = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": occ2["id"],
            "status": "present"
        })
        assert reverse_mark.status_code == 200
        assert reverse_mark.json()["status"] == "present"

        # Verify summary now includes restored class (3 conducted: 2 attended, 1 missed)
        summary_res3 = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res3.json()["total_conducted"] == 3
        assert summary_res3.json()["total_attended"] == 2

        # 10. Reschedule extra class to tomorrow
        resched_res = await ac.post("/api/timetable/reschedule", headers=headers, json={
            "occurrence_id": extra_occ["id"],
            "new_date": str(today + timedelta(days=1)),
            "new_start_time": "16:00:00",
            "new_end_time": "17:00:00",
            "notes": "Shifted to afternoon slot"
        })
        assert resched_res.status_code == 200
        assert resched_res.json()["status"] == "rescheduled"
        assert resched_res.json()["original_date"] == str(today)


@pytest.mark.asyncio
async def test_friends_and_private_sharing_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email1 = f"student_alpha_{uuid.uuid4().hex[:8]}@aiims.edu"
        email2 = f"student_beta_{uuid.uuid4().hex[:8]}@aiims.edu"

        # Register Student 1
        res1 = await ac.post("/api/auth/register", json={
            "email": email1,
            "password": "Password123!",
            "full_name": "Student Alpha"
        })
        assert res1.status_code == 200
        token1 = res1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        user1_id = res1.json()["user"]["id"]

        # Register Student 2
        res2 = await ac.post("/api/auth/register", json={
            "email": email2,
            "password": "Password123!",
            "full_name": "Student Beta"
        })
        assert res2.status_code == 200
        token2 = res2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        user2_id = res2.json()["user"]["id"]

        # Student 1 generates a resource
        gen_res = await ac.post("/api/resources/generate", headers=headers1, json={
            "topic": "Anatomy of the Inguinal Canal",
            "resource_type": "summary"
        })
        assert gen_res.status_code == 200
        resource_id = gen_res.json()["id"]

        # Student 2 tries to download Student 1's resource before being friends (should be 403 Forbidden)
        dl_unauthorized = await ac.get(f"/api/resources/{resource_id}/download", headers=headers2)
        assert dl_unauthorized.status_code == 403

        # Student 1 sends friend request to Student 2
        freq_res = await ac.post("/api/friends/requests", headers=headers1, json={
            "recipient_email": email2
        })
        assert freq_res.status_code == 200

        # Student 2 gets pending requests and accepts
        reqs_res = await ac.get("/api/friends/requests", headers=headers2)
        assert reqs_res.status_code == 200
        req_id = reqs_res.json()[0]["id"]

        acc_res = await ac.post(f"/api/friends/requests/{req_id}/respond?action=accept", headers=headers2)
        assert acc_res.status_code == 200

        # Student 1 shares resource with Student 2
        share_res = await ac.post("/api/friends/share", headers=headers1, json={
            "resource_id": resource_id,
            "recipient_user_id": user2_id,
            "permission": "download"
        })
        assert share_res.status_code == 200

        # Student 2 checks shared-with-me and can now download!
        shared_inbox = await ac.get("/api/friends/shared-with-me", headers=headers2)
        assert shared_inbox.status_code == 200
        assert len(shared_inbox.json()) == 1

        dl_authorized = await ac.get(f"/api/resources/{resource_id}/download", headers=headers2)
        assert dl_authorized.status_code == 200
        assert dl_authorized.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_attendance_management_features():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"mgmt_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Management Test Student",
            "college": "AIIMS",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 0 conducted classes -> overall_percentage is None (not 100%, not 0%)
        summary_res = await ac.get("/api/attendance/summary", headers=headers)
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert summary["total_conducted"] == 0
        assert summary["overall_percentage"] is None

        # 2. Get subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        subjs = subjs_res.json()
        anat = next(s for s in subjs if s["name"] == "Anatomy")
        phys = next(s for s in subjs if s["name"] == "Physiology")

        # 3. Add manual attendance for Anatomy: 1 Present, 1 Absent
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        p1_res = await ac.post("/api/attendance/manual", headers=headers, json={
            "subject_id": anat["id"],
            "date": str(two_days_ago),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "present",
            "notes": "Upper limb dissection"
        })
        assert p1_res.status_code == 200
        occ1_id = p1_res.json()["id"]

        p2_res = await ac.post("/api/attendance/manual", headers=headers, json={
            "subject_id": anat["id"],
            "date": str(yesterday),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "status": "absent",
            "notes": "Fever"
        })
        assert p2_res.status_code == 200
        occ2_id = p2_res.json()["id"]

        # Check summary: conducted=2, attended=1, missed=1 -> 50.0%
        sum2 = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert sum2["total_conducted"] == 2
        assert sum2["total_attended"] == 1
        assert sum2["total_missed"] == 1
        assert sum2["overall_percentage"] == 50.0

        # 4. Edit old attendance record: Absent -> Present + add topic title
        edit_res = await ac.put(f"/api/attendance/history/{occ2_id}", headers=headers, json={
            "status": "present",
            "topic_title": "Histology of Cartilage",
            "notes": "Make-up session completed"
        })
        assert edit_res.status_code == 200
        edited = edit_res.json()
        assert edited["attendance"]["status"] == "present"
        assert len(edited["topics"]) > 0
        assert edited["topics"][0]["title"] == "Histology of Cartilage"

        # Check summary: now conducted=2, attended=2, missed=0 -> 100.0%
        sum3 = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert sum3["total_conducted"] == 2
        assert sum3["total_attended"] == 2
        assert sum3["overall_percentage"] == 100.0

        # 5. Start New Semester (Archiving)
        sem_res = await ac.post("/api/attendance/new-semester", headers=headers, json={
            "semester_label": "Semester 1 - 2025"
        })
        assert sem_res.status_code == 200
        assert sem_res.json()["status"] == "ok"

        # After semester archive, active attendance counts reset fresh: 0 conducted, None percentage
        sum_after_sem = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert sum_after_sem["total_conducted"] == 0
        assert sum_after_sem["overall_percentage"] is None

        # History retains archived records
        hist_res = await ac.get("/api/attendance/history?archive_status=archived", headers=headers)
        assert hist_res.status_code == 200
        hist_records = hist_res.json()
        assert len(hist_records) >= 2
        assert any(r["archive_label"] == "Semester 1 - 2025" for r in hist_records)

        # 6. Add new attendance in active semester for Physiology
        p3_res = await ac.post("/api/attendance/manual", headers=headers, json={
            "subject_id": phys["id"],
            "date": str(today),
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "status": "present",
            "notes": "Cardiovascular Physiology"
        })
        assert p3_res.status_code == 200

        sum_phys = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert sum_phys["total_conducted"] == 1

        # 7. Test Reset Attendance: Wrong confirmation should be rejected
        bad_reset = await ac.post("/api/attendance/reset", headers=headers, json={
            "subject_id": phys["id"],
            "remove_topics": True,
            "confirmation": "incorrect"
        })
        assert bad_reset.status_code == 400

        # 8. Test Reset Attendance: Correct "RESET"
        good_reset = await ac.post("/api/attendance/reset", headers=headers, json={
            "subject_id": phys["id"],
            "remove_topics": True,
            "confirmation": "RESET"
        })
        assert good_reset.status_code == 200

        # Physiology is now reset back to 0 conducted / None percentage
        sum_reset = (await ac.get("/api/attendance/summary", headers=headers)).json()
        assert sum_reset["total_conducted"] == 0
        assert sum_reset["overall_percentage"] is None


@pytest.mark.asyncio
async def test_timetable_classes_auto_appear_in_attendance():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"auto_att_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Auto Attendance Student",
            "college": "MMC",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        subjs = subjs_res.json()
        anat = next(s for s in subjs if s["name"] == "Anatomy")
        phys = next(s for s in subjs if s["name"] == "Physiology")

        today = date.today()
        today_weekday = today.weekday()

        # Create recurring rule for Anatomy today that has ALREADY ended (e.g., 06:00 to 07:00 AM)
        rule1_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": anat["id"],
            "day_of_week": today_weekday,
            "start_time": "06:00:00",
            "end_time": "07:00:00",
            "faculty": "Dr. Early",
            "room": "Hall A"
        })
        assert rule1_res.status_code == 200

        # Create recurring rule for Physiology today scheduled for later (e.g., 23:00 to 23:50)
        rule2_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": phys["id"],
            "day_of_week": today_weekday,
            "start_time": "23:00:00",
            "end_time": "23:50:00",
            "faculty": "Dr. Late",
            "room": "Hall B"
        })
        assert rule2_res.status_code == 200

        # Now without creating any attendance manually, query GET /api/attendance/classes
        classes_res = await ac.get("/api/attendance/classes", headers=headers)
        assert classes_res.status_code == 200
        data = classes_res.json()

        # Rule 1 (06:00-07:00) ended, so it MUST appear in ended_classes!
        ended = data["ended_classes"]
        assert len(ended) >= 1
        ended_anat = next(c for c in ended if c["subject_id"] == anat["id"])
        assert ended_anat["faculty"] == "Dr. Early"
        assert ended_anat["attendance"] is None or ended_anat["attendance"]["status"] == "not_marked"

        # Rule 2 (23:00-23:50) has not ended yet, so it is in upcoming_today!
        upcoming = data["upcoming_today"]
        assert any(c["subject_id"] == phys["id"] for c in upcoming)

        # Mark attendance for the ended Anatomy class as Present
        mark_res = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": ended_anat["id"],
            "status": "present"
        })
        assert mark_res.status_code == 200

        # Verify summary reflects 1 conducted, 1 attended -> 100%
        sum_res = await ac.get("/api/attendance/summary", headers=headers)
        assert sum_res.status_code == 200
        summary = sum_res.json()
        assert summary["total_conducted"] == 1
        assert summary["total_attended"] == 1
        assert summary["overall_percentage"] == 100.0


