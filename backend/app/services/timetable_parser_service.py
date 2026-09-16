import os
import re
import json
import zlib
import base64
import asyncio
import tempfile
from typing import List, Dict, Any, Tuple, Optional
from datetime import time

from reportlab.pdfbase import pdfutils
from app.models.models import Subject, TimetableRule
from app.schemas.schemas import TimetableImportItem, TimetableImportPreview

MBBS_SUBJECT_CATALOG = {
    "ANATOMY": ["ANAT", "ANATOMY", "GROSS ANATOMY", "HISTOLOGY", "EMBRYOLOGY", "NEUROANATOMY", "DH"],
    "PHYSIOLOGY": ["PHYS", "PHYSIOLOGY", "HUMAN PHYSIOLOGY"],
    "BIOCHEMISTRY": ["BIOCHEM", "BIOCHEMISTRY", "MEDICAL BIOCHEMISTRY"],
    "PATHOLOGY": ["PATH", "PATHOLOGY", "HISTOPATHOLOGY", "HAEMATOLOGY", "CLINICAL PATHOLOGY"],
    "PHARMACOLOGY": ["PHARM", "PHARMACOLOGY", "CLINICAL PHARMACOLOGY"],
    "MICROBIOLOGY": ["MICRO", "MICROBIOLOGY", "BACTERIOLOGY", "VIROLOGY", "PARASITOLOGY"],
    "COMMUNITY MEDICINE": ["PSM", "SPM", "COMMUNITY MEDICINE", "PREVENTIVE AND SOCIAL MEDICINE"],
    "FORENSIC MEDICINE": ["FMT", "FORENSIC MEDICINE", "TOXICOLOGY", "FORENSIC MEDICINE & TOXICOLOGY"],
    "OPHTHALMOLOGY": ["OPHTH", "OPHTHALMOLOGY", "EYE"],
    "ENT": ["ENT", "OTORHINOLARYNGOLOGY", "EAR NOSE THROAT"],
    "GENERAL MEDICINE": ["MED", "MEDICINE", "GENERAL MEDICINE", "INTERNAL MEDICINE"],
    "GENERAL SURGERY": ["SURG", "SURGERY", "GENERAL SURGERY"],
    "OBSTETRICS & GYNAECOLOGY": ["OBG", "OBGYN", "OBS & GYNAE", "GYNAECOLOGY", "OBSTETRICS"],
    "PAEDIATRICS": ["PAED", "PEDIATRICS", "PAEDIATRICS"],
    "ORTHOPAEDICS": ["ORTHO", "ORTHOPAEDICS", "ORTHOPEDICS"],
    "DERMATOLOGY": ["DERM", "DERMATOLOGY", "DVL"],
    "PSYCHIATRY": ["PSYCH", "PSYCHIATRY"],
    "RADIOLOGY": ["RADIO", "RADIOLOGY", "RADIODIAGNOSIS"],
    "ANAESTHESIA": ["ANAESTH", "ANAESTHESIA", "ANESTHESIOLOGY"],
}

DAY_MAPPING = {
    "MONDAY": 0, "MON": 0,
    "TUESDAY": 1, "TUE": 1, "TUES": 1,
    "WEDNESDAY": 2, "WED": 2,
    "THURSDAY": 3, "THU": 3, "THUR": 3, "THURS": 3,
    "FRIDAY": 4, "FRI": 4,
    "SATURDAY": 5, "SAT": 5,
    "SUNDAY": 6, "SUN": 6,
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TimetableParserService:
    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """
        Extracts selectable text from PDF streams using pure Python decompression.
        Supports /FlateDecode, /ASCII85Decode, and plain text streams.
        """
        extracted_lines: List[str] = []
        pos = 0

        while True:
            s_idx = pdf_bytes.find(b'stream', pos)
            if s_idx == -1:
                break
            start = s_idx + 6
            while start < len(pdf_bytes) and pdf_bytes[start:start+1] in (b'\r', b'\n', b' '):
                start += 1
            e_idx = pdf_bytes.find(b'endstream', start)
            if e_idx == -1:
                break
            raw_stream = pdf_bytes[start:e_idx].strip()
            pos = e_idx + 9

            # Determine filter from preceding dictionary if possible
            dict_start = max(0, s_idx - 300)
            dict_context = pdf_bytes[dict_start:s_idx]

            decompressed = None

            # Attempt ASCII85 decode if present
            stream_data = raw_stream
            if b'/ASCII85Decode' in dict_context or b'/A85' in dict_context:
                try:
                    stream_data = pdfutils.asciiBase85Decode(raw_stream.decode('latin1'))
                except Exception:
                    try:
                        stream_data = base64.a85decode(raw_stream)
                    except Exception:
                        stream_data = raw_stream

            # Attempt Flate / zlib decompression
            if b'/FlateDecode' in dict_context or True:
                for wbits in [zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 16]:
                    try:
                        decompressed = zlib.decompress(stream_data, wbits)
                        break
                    except Exception:
                        continue

            content = decompressed if decompressed is not None else stream_data

            # Extract strings from text operators: (text) Tj and [(text) kern (text)] TJ
            # 1. Tj operators
            tj_matches = re.findall(rb'\(((?:[^()\\]|\\.)*)\)\s*Tj', content)
            for m in tj_matches:
                line = TimetableParserService._clean_pdf_string(m)
                if line:
                    extracted_lines.append(line)

            # 2. TJ array operators
            tj_arrays = re.findall(rb'\[(.*?)\]\s*TJ', content, re.DOTALL)
            for arr in tj_arrays:
                parts = re.findall(rb'\(((?:[^()\\]|\\.)*)\)', arr)
                combined = ' '.join(TimetableParserService._clean_pdf_string(p) for p in parts if p)
                if combined.strip():
                    extracted_lines.append(combined.strip())

        # Fallback if no streams yielded text: scan printable ASCII strings
        if not extracted_lines:
            raw_strings = re.findall(rb'[A-Za-z0-9 :,.\-/]{5,}', pdf_bytes)
            for s in raw_strings:
                try:
                    dec = s.decode('utf-8', errors='ignore').strip()
                    if any(day in dec.upper() for day in DAY_MAPPING):
                        extracted_lines.append(dec)
                except Exception:
                    pass

        return '\n'.join(extracted_lines)

    @staticmethod
    def _clean_pdf_string(raw: bytes) -> str:
        try:
            # Handle PDF escaped parenthesis and backslashes
            s = raw.decode('latin1', errors='ignore')
            s = s.replace(r'\(', '(').replace(r'\)', ')').replace(r'\\', '\\')
            return s.strip()
        except Exception:
            return ""

    @staticmethod
    async def extract_text_from_image(image_bytes: bytes, filename: str = "timetable.jpg") -> str:
        """
        Runs OCR on image bytes.
        Uses compiled local Apple Vision OCR binary on macOS, with safe fallback.
        """
        ext = os.path.splitext(filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            # Path to compiled apple_vision_ocr utility
            util_path = os.path.join(os.path.dirname(__file__), "..", "utils", "apple_vision_ocr")
            if os.path.exists(util_path) and os.access(util_path, os.X_OK):
                proc = await asyncio.create_subprocess_exec(
                    util_path, tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    text = stdout.decode('utf-8', errors='ignore')
                    if text.strip():
                        return text

            # Fallback: Check if Gemini API Key is configured and try Gemini Vision
            from app.core.config import settings
            if settings.GEMINI_API_KEY:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    img_data = {
                        "mime_type": "image/jpeg" if ext.lower() in [".jpg", ".jpeg"] else f"image/{ext.lstrip('.')}",
                        "data": image_bytes
                    }
                    prompt = (
                        "Extract all text from this medical college timetable image accurately. "
                        "List each class with Day, Start Time, End Time, Subject, Faculty, and Room."
                    )
                    res = await model.generate_content_async([img_data, prompt])
                    return res.text or ""
                except Exception as e:
                    print(f"Gemini Vision fallback error: {e}")

            return ""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @staticmethod
    async def parse_with_gemini(
        file_bytes: bytes,
        filename: str,
        existing_subjects: List[Subject],
        api_key: Optional[str] = None
    ) -> Optional[List[TimetableImportItem]]:
        """
        Uses Gemini 1.5 Flash multimodal vision to parse image or PDF timetables
        into structured classes with high precision.
        """
        from app.core.config import settings
        resolved_key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY", "").strip() or (settings.GEMINI_API_KEY or "").strip()
        if not resolved_key:
            return None

        try:
            import google.generativeai as genai

            genai.configure(api_key=resolved_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

            ext = os.path.splitext(filename)[1].lower().lstrip('.')
            if ext == "pdf":
                mime_type = "application/pdf"
            elif ext in ["jpg", "jpeg"]:
                mime_type = "image/jpeg"
            elif ext == "png":
                mime_type = "image/png"
            elif ext == "webp":
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            file_part = {
                "mime_type": mime_type,
                "data": file_bytes
            }

            prompt = """
You are MedPilot's expert medical academic AI agent.
Analyze this medical college (MBBS) timetable file (PDF, photo, or scan).
Your goal is 100% extraction accuracy of all scheduled classes across the entire week.

Medical College Timetable Structure:
1. Grid / Tabular layouts:
   - Days of the week (Monday through Saturday/Sunday) are usually row headers (or column headers).
   - Time slots (e.g., 8:00 AM - 9:00 AM, 9:00 - 10:00, 10:00 - 11:00, 11:00 - 1:00, 2:00 - 4:00 PM) are column headers (or row headers).
   - Cells contain subjects, clinical postings, dissection hall (DH), hospital rounds, lectures, practicals, or tutorials.
2. Common MBBS Subjects:
   - Anatomy, Histology, Embryology, Dissection Hall (DH)
   - Physiology, Biochemistry
   - Pathology, Pharmacology, Microbiology
   - Forensic Medicine (FMT, Toxicology)
   - Community Medicine (PSM, SPM)
   - Ophthalmology (Eye), ENT (Otorhinolaryngology)
   - General Medicine, General Surgery, Obstetrics & Gynaecology (OBG/OBGYN), Paediatrics
   - Orthopaedics, Dermatology (DVL), Psychiatry, Radiology, Anaesthesia
   - Clinical Postings / Hospital Postings / Clinics
3. For each scheduled class/session, extract:
   - "day_of_week": Integer 0 to 6 (0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday).
   - "start_time": 24-hour format string "HH:MM" (e.g. "08:00", "09:00", "13:00", "14:00"). Convert 12-hour AM/PM correctly (e.g., 2:00 PM is "14:00").
   - "end_time": 24-hour format string "HH:MM" (e.g. "09:00", "10:00", "14:00", "16:00").
   - "subject_name": Standardized subject name (e.g. "Anatomy", "Physiology", "Pathology", "Clinical Posting - Medicine").
   - "faculty": Faculty / Doctor / Professor name if visible (e.g. "Dr. Sharma"), else empty string "".
   - "room": Room / Lecture Theatre / Lab / Hall if visible (e.g. "LT-1", "Dissection Hall", "Lab 2"), else empty string "".

Return ONLY a valid JSON object with the following schema:
{
  "classes": [
    {
      "day_of_week": 0,
      "start_time": "08:00",
      "end_time": "09:00",
      "subject_name": "Anatomy",
      "faculty": "",
      "room": "LT-1"
    }
  ]
}
"""

            response = await model.generate_content_async(
                [file_part, prompt],
                generation_config={"response_mime_type": "application/json"}
            )

            response_text = response.text or ""
            if not response_text.strip():
                return None

            data = json.loads(response_text)
            extracted_classes = data.get("classes", [])
            if not extracted_classes and isinstance(data, list):
                extracted_classes = data

            if not extracted_classes:
                return None

            items: List[TimetableImportItem] = []
            for entry in extracted_classes:
                try:
                    d = int(entry.get("day_of_week", 0))
                    if d < 0 or d > 6:
                        d = 0

                    s_raw = str(entry.get("start_time", "09:00")).strip()
                    e_raw = str(entry.get("end_time", "10:00")).strip()
                    s_t = TimetableParserService._normalize_time(s_raw) or time(9, 0)
                    e_t = TimetableParserService._normalize_time(e_raw) or time(10, 0)

                    subj_str = str(entry.get("subject_name", "General Medical Class")).strip()
                    fac = str(entry.get("faculty", "")).strip()
                    rm = str(entry.get("room", "")).strip()

                    matched_id, matched_name, is_new, detected_subj_name, confidence = TimetableParserService._match_subject(
                        subj_str, existing_subjects
                    )

                    item = TimetableImportItem(
                        day_of_week=d,
                        day_name=DAY_NAMES[d],
                        start_time=f"{s_t.hour:02d}:{s_t.minute:02d}",
                        end_time=f"{e_t.hour:02d}:{e_t.minute:02d}",
                        subject_name=detected_subj_name,
                        matched_subject_id=matched_id,
                        matched_subject_name=matched_name,
                        is_new_subject=is_new,
                        faculty=fac,
                        room=rm,
                        confidence=max(confidence, 0.95),
                        notes="AI Agent Vision Extracted",
                        has_conflict=False
                    )
                    items.append(item)
                except Exception:
                    continue

            return items if items else None
        except Exception as e:
            print(f"Gemini multimodal parsing error: {e}")
            return None

    @staticmethod
    def parse_timetable_text(raw_text: str, existing_subjects: List[Subject]) -> List[TimetableImportItem]:
        """
        Heuristic parsing of timetable text into structured candidate classes.
        Handles both 2D table grid formats and per-line class formats.
        """
        items: List[TimetableImportItem] = []
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]

        day_pattern = re.compile(r'\b(MONDAY|MON|TUESDAY|TUE|TUES|WEDNESDAY|WED|THURSDAY|THU|THUR|THURS|FRIDAY|FRI|SATURDAY|SAT|SUNDAY|SUN)\b', re.IGNORECASE)
        time_pattern = re.compile(
            r'(\d{1,2}(?:[:.]\d{2})?)\s*(?:am|pm)?\s*(?:-|to|–|—)\s*(\d{1,2}(?:[:.]\d{2})?)\s*(am|pm)?',
            re.IGNORECASE
        )
        faculty_pattern = re.compile(r'(?:Dr\.?|Prof\.?)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', re.IGNORECASE)
        room_pattern = re.compile(r'\b(Room\s*\d+|LT[- ]?\d+|LH[- ]?\d+|Lab[- ]?\d+|Hall[- ]?\d+|DH|Dissection Hall|Auditorium)\b', re.IGNORECASE)

        # 1. First, check if there is a header row with multiple time ranges (2D Table Grid format)
        header_slots: List[Tuple[time, time]] = []
        for line in lines:
            matches = list(time_pattern.finditer(line))
            if len(matches) >= 2:
                for m in matches:
                    s_t = TimetableParserService._normalize_time(m.group(1), is_end=False, ampm=m.group(3))
                    e_t = TimetableParserService._normalize_time(m.group(2), is_end=True, ampm=m.group(3))
                    if s_t and e_t:
                        header_slots.append((s_t, e_t))
                if header_slots:
                    break

        if header_slots:
            for line in lines:
                day_match = day_pattern.search(line)
                if not day_match:
                    continue

                day_str = day_match.group(1).upper()
                day_idx = DAY_MAPPING.get(day_str, 0)

                content_after_day = line[:day_match.start()] + " " + line[day_match.end():]
                if '|' in content_after_day:
                    cells = [c.strip() for c in content_after_day.split('|') if c.strip()]
                elif '\t' in content_after_day:
                    cells = [c.strip() for c in content_after_day.split('\t') if c.strip()]
                elif ',' in content_after_day:
                    cells = [c.strip() for c in content_after_day.split(',') if c.strip()]
                else:
                    cells = [c.strip() for c in content_after_day.split('  ') if c.strip()]
                    if len(cells) < 2:
                        cells = [c.strip() for c in content_after_day.split() if c.strip()]

                # Avoid re-parsing the header row
                if any(time_pattern.search(c) for c in cells):
                    continue

                for slot_idx, (start_t, end_t) in enumerate(header_slots):
                    if slot_idx >= len(cells):
                        break
                    cell_text = cells[slot_idx]
                    if not cell_text or cell_text.upper() in ["LUNCH", "BREAK", "RECESS", "FREE", "NIL", "-", "TEA"]:
                        continue

                    fac_match = faculty_pattern.search(cell_text)
                    faculty = fac_match.group(0) if fac_match else ""

                    room_match = room_pattern.search(cell_text)
                    room = room_match.group(0) if room_match else ""

                    remainder = cell_text
                    if fac_match:
                        remainder = faculty_pattern.sub('', remainder)
                    if room_match:
                        remainder = room_pattern.sub('', remainder)
                    remainder = re.sub(r'[:|,\-–—()\[\]]', ' ', remainder).strip()
                    remainder = re.sub(r'\s+', ' ', remainder)

                    if not remainder:
                        continue

                    matched_id, matched_name, is_new, detected_subj_name, confidence = TimetableParserService._match_subject(
                        remainder, existing_subjects
                    )

                    item = TimetableImportItem(
                        day_of_week=day_idx,
                        day_name=DAY_NAMES[day_idx],
                        start_time=f"{start_t.hour:02d}:{start_t.minute:02d}",
                        end_time=f"{end_t.hour:02d}:{end_t.minute:02d}",
                        subject_name=detected_subj_name,
                        matched_subject_id=matched_id,
                        matched_subject_name=matched_name,
                        is_new_subject=is_new,
                        faculty=faculty,
                        room=room,
                        confidence=confidence,
                        notes="Grid Extracted",
                        has_conflict=False
                    )
                    items.append(item)

        if items:
            return items

        # 2. Line-by-line parsing fallback
        current_day_idx: Optional[int] = None

        for line in lines:
            # Check if line contains a day header
            day_match = day_pattern.search(line)
            line_day_idx = None
            if day_match:
                day_str = day_match.group(1).upper()
                line_day_idx = DAY_MAPPING.get(day_str)
                cleaned_line = re.sub(day_pattern, '', line).strip(' :-')
                if not cleaned_line:
                    current_day_idx = line_day_idx
                    continue

            # Check for time range
            time_match = time_pattern.search(line)
            if not time_match:
                continue

            raw_start = time_match.group(1)
            raw_end = time_match.group(2)
            ampm = time_match.group(3)

            start_t = TimetableParserService._normalize_time(raw_start, is_end=False, ampm=ampm)
            end_t = TimetableParserService._normalize_time(raw_end, is_end=True, ampm=ampm)
            if not start_t or not end_t:
                continue

            target_day_idx = line_day_idx if line_day_idx is not None else current_day_idx
            if target_day_idx is None:
                target_day_idx = 0

            fac_match = faculty_pattern.search(line)
            faculty = fac_match.group(0) if fac_match else ""

            room_match = room_pattern.search(line)
            room = room_match.group(0) if room_match else ""

            remainder = line
            remainder = time_pattern.sub('', remainder)
            if day_match:
                remainder = day_pattern.sub('', remainder)
            if fac_match:
                remainder = faculty_pattern.sub('', remainder)
            if room_match:
                remainder = room_pattern.sub('', remainder)

            remainder = re.sub(r'[:|,\-–—()\[\]]', ' ', remainder).strip()
            remainder = re.sub(r'\s+', ' ', remainder)

            matched_id, matched_name, is_new, detected_subj_name, confidence = TimetableParserService._match_subject(
                remainder, existing_subjects
            )

            item = TimetableImportItem(
                day_of_week=target_day_idx,
                day_name=DAY_NAMES[target_day_idx],
                start_time=f"{start_t.hour:02d}:{start_t.minute:02d}",
                end_time=f"{end_t.hour:02d}:{end_t.minute:02d}",
                subject_name=detected_subj_name,
                matched_subject_id=matched_id,
                matched_subject_name=matched_name,
                is_new_subject=is_new,
                faculty=faculty,
                room=room,
                confidence=confidence,
                notes="",
                has_conflict=False
            )
            items.append(item)

        return items

    @staticmethod
    def _normalize_time(val: str, is_end: bool = False, ampm: Optional[str] = None) -> Optional[time]:
        val = val.strip().replace('.', ':')
        parts = val.split(':')
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

            # Handle AM/PM
            if ampm:
                ampm_upper = ampm.upper()
                if ampm_upper == "PM" and hour < 12:
                    hour += 12
                elif ampm_upper == "AM" and hour == 12:
                    hour = 0
            else:
                # MBBS Timetable heuristic:
                # Classes between 8 and 12 are AM.
                # Classes between 1 and 6 are PM (e.g. 1:00 = 13:00, 2:00 = 14:00).
                if 1 <= hour <= 6:
                    hour += 12

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
        except Exception:
            pass
        return None

    @staticmethod
    def _match_subject(
        text: str,
        existing_subjects: List[Subject]
    ) -> Tuple[Optional[str], Optional[str], bool, str, float]:
        """
        Fuzzy matching against user's existing subjects and MBBS subject catalog.
        Returns (matched_id, matched_name, is_new_subject, display_name, confidence)
        """
        cleaned = text.strip()
        tokens = [t.upper() for t in re.split(r'[\s/]+', cleaned) if len(t) > 1]

        # 1. Exact match with existing subject
        for s in existing_subjects:
            s_name_upper = s.name.upper()
            s_code_upper = (s.code or "").upper()
            if s_name_upper == cleaned.upper() or (s_code_upper and s_code_upper == cleaned.upper()):
                return s.id, s.name, False, s.name, 1.0

        # 2. Token match with existing subjects
        for s in existing_subjects:
            s_tokens = [t.upper() for t in re.split(r'[\s/]+', s.name) if len(t) > 1]
            s_code = (s.code or "").upper()
            for tok in tokens:
                if tok in s_tokens or (s_code and tok == s_code):
                    return s.id, s.name, False, s.name, 0.9

        # 3. Substring match with existing subjects
        for s in existing_subjects:
            if s.name.upper() in cleaned.upper() or (s.code and s.code.upper() in cleaned.upper()):
                return s.id, s.name, False, s.name, 0.85

        # 4. Check MBBS Subject Catalog to find canonical subject name
        for canonical, aliases in MBBS_SUBJECT_CATALOG.items():
            for tok in tokens:
                if tok in aliases or any(alias in cleaned.upper() for alias in aliases):
                    # Check if user already has this canonical subject
                    for s in existing_subjects:
                        if s.name.upper() == canonical or s.name.upper() in aliases:
                            return s.id, s.name, False, s.name, 0.85
                    # New subject suggested from catalog
                    return None, canonical.title(), True, canonical.title(), 0.75

        # If completely unrecognized, use the extracted text as a candidate new subject
        candidate_name = cleaned.title() if cleaned else "General Lecture"
        return None, candidate_name, True, candidate_name, 0.5

    @staticmethod
    def detect_conflicts(
        existing_rules: List[TimetableRule],
        items: List[TimetableImportItem]
    ) -> int:
        """
        Flags items that conflict with existing rules on the same day and time.
        """
        conflict_count = 0
        for item in items:
            try:
                i_start = time.fromisoformat(item.start_time)
                i_end = time.fromisoformat(item.end_time)
            except Exception:
                continue

            for rule in existing_rules:
                if rule.day_of_week == item.day_of_week and rule.is_active:
                    # Check overlap: max(start1, start2) < min(end1, end2)
                    if max(i_start, rule.start_time) < min(i_end, rule.end_time):
                        item.has_conflict = True
                        conflict_count += 1
                        break
        return conflict_count
