import uuid
import io
import pytest
from datetime import date, time, timedelta
from httpx import AsyncClient, ASGITransport
from reportlab.pdfgen import canvas

from app.main import app


@pytest.mark.asyncio
async def test_subject_management_and_safe_deletion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"subj_test_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Subject Test Student",
            "college": "AIIMS",
            "year_of_study": "MBBS 2nd Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create a new custom subject: Dermatology
        create_res = await ac.post("/api/subjects/", headers=headers, json={
            "name": "Dermatology",
            "code": "DERM",
            "color": "#F59E0B",
            "target_attendance": 80.0,
            "faculty": "Dr. Kapoor",
            "academic_year": "MBBS 2nd Year"
        })
        assert create_res.status_code == 200
        derm = create_res.json()
        assert derm["name"] == "Dermatology"
        assert derm["faculty"] == "Dr. Kapoor"
        assert derm["target_attendance"] == 80.0

        # 2. Verify enriched subjects endpoint
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        assert subjs_res.status_code == 200
        subjs = subjs_res.json()
        derm_enriched = next(s for s in subjs if s["id"] == derm["id"])
        assert derm_enriched["classes_conducted"] == 0
        assert derm_enriched["classes_attended"] == 0
        # 0 conducted classes must return None (rendered as '—' in UI, never 100%)
        assert derm_enriched["current_percentage"] is None

        # 3. Create a manual class and mark attendance for Dermatology
        manual_res = await ac.post("/api/attendance/manual", headers=headers, json={
            "subject_id": derm["id"],
            "date": str(date.today()),
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "status": "present",
            "faculty": "Dr. Kapoor",
            "room": "OPD Block",
            "notes": "Clinical dermatology posting"
        })
        assert manual_res.status_code == 200

        # 4. Attempt deleting subject without force -> expect 409 Conflict
        del_attempt = await ac.delete(f"/api/subjects/{derm['id']}", headers=headers)
        assert del_attempt.status_code == 409
        assert "attendance records" in del_attempt.json()["detail"].lower()

        # 5. Delete subject with force=true -> succeeds
        del_force = await ac.delete(f"/api/subjects/{derm['id']}?force=true", headers=headers)
        assert del_force.status_code == 200
        assert "deleted successfully" in del_force.json()["message"]


@pytest.mark.asyncio
async def test_attendance_marking_and_cancelled_class_invariance():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"att_calc_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Attendance Invariance Student",
            "college": "JIPMER",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch subjects
        subjs_res = await ac.get("/api/subjects/", headers=headers)
        anat = next(s for s in subjs_res.json() if s["name"] == "Anatomy")

        today = date.today()

        # Log 8 Present classes
        for i in range(8):
            await ac.post("/api/attendance/manual", headers=headers, json={
                "subject_id": anat["id"],
                "date": str(today - timedelta(days=20 - i)),
                "start_time": "09:00:00",
                "end_time": "10:00:00",
                "status": "present"
            })

        # Log 2 Absent classes
        for i in range(2):
            await ac.post("/api/attendance/manual", headers=headers, json={
                "subject_id": anat["id"],
                "date": str(today - timedelta(days=10 - i)),
                "start_time": "09:00:00",
                "end_time": "10:00:00",
                "status": "absent"
            })

        # 8 Present + 2 Absent = 10 Conducted -> Exactly 80.0%
        sum_res1 = await ac.get("/api/attendance/summary", headers=headers)
        assert sum_res1.status_code == 200
        s1 = sum_res1.json()
        assert s1["total_conducted"] == 10
        assert s1["total_attended"] == 8
        assert s1["total_missed"] == 2
        assert s1["overall_percentage"] == 80.0

        # Now add 1 CANCELLED class
        cancel_res = await ac.post("/api/attendance/manual", headers=headers, json={
            "subject_id": anat["id"],
            "date": str(today - timedelta(days=1)),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "status": "cancelled",
            "notes": "College sports day holiday"
        })
        assert cancel_res.status_code == 200

        # Strict Requirement: Attendance must remain 80.0%, denominator must remain 10, NOT 11 or 72.7%
        sum_res2 = await ac.get("/api/attendance/summary", headers=headers)
        s2 = sum_res2.json()
        assert s2["total_conducted"] == 10
        assert s2["total_attended"] == 8
        assert s2["total_missed"] == 2
        assert s2["total_cancelled"] == 1
        assert s2["overall_percentage"] == 80.0


@pytest.mark.asyncio
async def test_today_classes_and_status_toggle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"today_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Today Student",
            "college": "MMC",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subjs_res = await ac.get("/api/subjects/", headers=headers)
        phys = next(s for s in subjs_res.json() if s["name"] == "Physiology")

        today = date.today()
        # Add recurring rule for today's weekday
        rule_res = await ac.post("/api/timetable/rules", headers=headers, json={
            "subject_id": phys["id"],
            "day_of_week": today.weekday(),
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "faculty": "Dr. Sen",
            "room": "Physio Lab"
        })
        assert rule_res.status_code == 200

        # Query today's classes
        today_res = await ac.get("/api/attendance/today", headers=headers)
        assert today_res.status_code == 200
        today_classes = today_res.json()
        assert len(today_classes) >= 1
        target_occ = next(c for c in today_classes if c["subject_id"] == phys["id"])

        # 1. Mark Absent accidentally
        m1 = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": target_occ["id"],
            "status": "absent"
        })
        assert m1.status_code == 200
        assert m1.json()["status"] == "absent"

        # 2. Correct to Present (must update, zero duplicate records)
        m2 = await ac.post("/api/attendance/mark", headers=headers, json={
            "occurrence_id": target_occ["id"],
            "status": "present"
        })
        assert m2.status_code == 200
        assert m2.json()["status"] == "present"
        assert m2.json()["id"] == m1.json()["id"]  # Same record ID updated!


@pytest.mark.asyncio
async def test_pdf_timetable_import_and_duplicate_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"import_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Import Student",
            "college": "CMC Vellore",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Generate a real PDF in memory with ReportLab
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "MBBS First Year Timetable")
        c.drawString(100, 700, "Monday 09:00 - 10:00 Anatomy Dr. Sharma Room 101")
        c.drawString(100, 650, "Tuesday 11:00 - 12:00 Physiology Dr. Gupta Lab 2")
        c.drawString(100, 600, "Wednesday 14:00 - 15:00 Biochemistry Dr. Rao LT-1")
        c.save()
        pdf_bytes = buf.getvalue()

        # Upload and parse PDF
        files = {"file": ("schedule.pdf", pdf_bytes, "application/pdf")}
        parse_res = await ac.post("/api/timetable/import/parse", headers=headers, files=files)
        assert parse_res.status_code == 200
        preview = parse_res.json()

        assert len(preview["extracted_items"]) >= 3
        items = preview["extracted_items"]

        # Verify extracted schedule items
        anat_item = next((it for it in items if "ANAT" in it["subject_name"].upper()), None)
        assert anat_item is not None
        assert anat_item["day_name"] == "Monday"
        assert anat_item["start_time"] == "09:00"
        assert anat_item["end_time"] == "10:00"

        # Confirm import
        confirm_res = await ac.post("/api/timetable/import/confirm", headers=headers, json={
            "items": items,
            "duplicate_mode": "skip"
        })
        assert confirm_res.status_code == 200
        confirm_data = confirm_res.json()
        assert confirm_data["imported_count"] >= 3

        # Verify recurring rules exist
        rules_res = await ac.get("/api/timetable/rules", headers=headers)
        assert rules_res.status_code == 200
        assert len(rules_res.json()) >= 3

        # Second import with the same file to test duplicate detection
        files2 = {"file": ("schedule.pdf", pdf_bytes, "application/pdf")}
        parse_res2 = await ac.post("/api/timetable/import/parse", headers=headers, files=files2)
        assert parse_res2.status_code == 200
        preview2 = parse_res2.json()
        assert preview2["duplicate_count"] >= 3


@pytest.mark.asyncio
async def test_image_ocr_timetable_import():
    from PIL import Image, ImageDraw
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"ocr_{uuid.uuid4().hex[:8]}@medpilot.io"
        reg_res = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "OCR Student",
            "college": "KMC Manipal",
            "year_of_study": "MBBS 1st Year"
        })
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Generate a synthetic timetable image with PIL
        img = Image.new("RGB", (800, 300), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((30, 40), "Monday 09:00 - 10:00 Anatomy Dr. Sharma Room 101", fill=(0, 0, 0))
        d.text((30, 100), "Tuesday 11:00 - 12:00 Physiology Dr. Gupta Lab 2", fill=(0, 0, 0))
        d.text((30, 160), "Thursday 14:00 - 15:00 Biochemistry Dr. Rao LT-1", fill=(0, 0, 0))

        img_buf = io.BytesIO()
        img.save(img_buf, format="JPEG")
        img_bytes = img_buf.getvalue()

        # Upload image to timetable parser
        files = {"file": ("timetable_photo.jpg", img_bytes, "image/jpeg")}
        parse_res = await ac.post("/api/timetable/import/parse", headers=headers, files=files)
        assert parse_res.status_code == 200
        preview = parse_res.json()

        # Check that OCR extracted items
        assert len(preview["extracted_items"]) >= 2
        items = preview["extracted_items"]

        # Confirm import of extracted OCR items
        confirm_res = await ac.post("/api/timetable/import/confirm", headers=headers, json={
            "items": items,
            "duplicate_mode": "skip"
        })
        assert confirm_res.status_code == 200
        assert confirm_res.json()["imported_count"] >= 2
