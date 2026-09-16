# MedPilot — Your AI Academic Companion 🩺

> **An Agentic AI Web Application designed specifically for MBBS students.**  
> MedPilot reduces academic stress and streamlines academic planning, attendance management, daily routines, revision, and active learning workflows.

---

## ⚠️ Important Educational & Clinical Disclaimer
**MedPilot is an educational support and academic planning application.**  
It is **strictly NOT** a medical diagnosis tool, does not prescribe medications, does not replace clinical judgment or qualified physicians, and does not provide clinical management directives. All academic materials, MCQs, and summaries generated must be cross-checked with standard medical textbooks (Guyton, Robbins, Harrison's, etc.) and university/institutional syllabi.

---

## 🌟 Key Features

1. **"What Should I Do Now?" Signature Contextual Agent**
   - Evaluates the student's live timetable, upcoming classes, deterministic attendance deficits, exam countdowns, uncompleted daily tasks, and wellness routines.
   - Decides the optimal next action with 3 rationale bullet points and 1-click action triggers.

2. **2-Level Medical Timetable Engine**
   - **Level A (Standing Rules)**: Weekly recurring lecture schedules, clinical postings, labs, and tutorials.
   - **Level B (Occurrences)**: Actual scheduled occurrences with date/time, status (`scheduled`, `completed`, `cancelled`, `rescheduled`), topics taught, and swap detection.
   - **Extra Classes & Rescheduling**: Full support for impromptu extra classes and date shifts without corrupting recurring rules.

3. **Deterministic Attendance Portal & Safe Bunk Calculator**
   - Transparent calculation: $\text{Attendance \%} = \frac{\text{Attended Classes}}{\text{Conducted Classes}} \times 100$.
   - **Strict Cancelled Class Handling**: Cancelled classes never count as conducted, never decrease percentage, and require no confirmation.
   - **Target Deficit Formula**: $x = \lceil \frac{T \cdot C - A}{1 - T} \rceil$ classes required to reach target $T$.
   - **Safe Bunk Buffer Formula**: $y = \lfloor \frac{A - T \cdot C}{T} \rfloor$ classes safe to miss without dropping below $T$.
   - Unconfirmed class queue with 1-click "Present", "Absent", or "Cancelled" marking.

4. **AI Academic Learning Assistant**
   - Evidence-grounded academic tutor citing standard textbooks (Guyton, Robbins, Katzung, Park, etc.).
   - Pre-class prep briefings and post-class revision debriefings.
   - **Flexible Study Mode**: Tailored 30-minute high-yield cram sessions, 60-minute core revision, or 120-minute comprehensive deep-dives.

5. **AI Study Planner & Focus Logging**
   - High-yield task scheduling with priority tagging and estimated durations.
   - AI Study Plan Generator based on upcoming exam dates and subject syllabus.
   - Non-punitive study session focus timer and study log.

6. **Exam Countdown & Preparation Cockpit**
   - Real-time countdown to internal assessments, send-ups, and university professional exams.
   - High-yield syllabus coverage and revision status tracking.

7. **Previous-Year Question (PYQ) Analyzer**
   - Analyzes past university exam questions.
   - Identifies high-yield repeating topics, topic frequencies, and expected question styles (Long Answer, Short Notes, Applied Clinical Vignettes).

8. **Clinical ReportLab PDF Generator**
   - High-yield study notes, flashcards, and MCQ quiz exports.
   - Generates beautifully formatted medical PDFs with disclaimers and citations.

9. **Non-Punitive Daily Wellness & Routine Tracker**
   - Tracks sleep, hydration, meals, study breaks, and evening review check-ins.
   - Zero guilt-tripping or streak-shaming; missed habits are simply missed habits.

10. **Private Student Study Circle & Resource Sharing**
    - Mutual batchmate friend requests via email.
    - Direct sharing of generated study decks, MCQs, and summaries.
    - Zero public social feeds or distractions.

---

## 🛠 Tech Stack

- **Frontend**: Plain React.js + Vite + JavaScript (no TypeScript, no Next.js), Tailwind CSS, Lucide React Icons.
- **Backend**: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy (asyncio / aiosqlite / asyncpg), ReportLab.
- **Database**: PostgreSQL / Supabase with Row Level Security (RLS) + SQLite for local test/dev.
- **LLM**: Agnostic provider abstraction with Google Gemini (`gemini-1.5-flash`) and an offline MBBS academic heuristic fallback provider.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 2. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
```
Run tests to verify:
```bash
pytest tests/
```
Start the FastAPI server:
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive API documentation: `http://localhost:8000/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## 📁 Repository Structure
```
├── backend/
│   ├── app/
│   │   ├── agent/            # MedPilot LLM Providers, Tools & Orchestrator
│   │   ├── api/              # FastAPI Routers (auth, timetable, attendance, etc.)
│   │   ├── core/             # Config, Database engine, JWT Security
│   │   ├── models/           # SQLAlchemy Async ORM Models
│   │   ├── schemas/          # Pydantic v2 Data Transfer Objects
│   │   └── services/         # Attendance, Timetable & ReportLab PDF Services
│   ├── tests/                # Pytest Async Test Suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/              # Client fetch wrapper
│   │   ├── components/       # Responsive Sidebar, Navbar
│   │   ├── context/          # Auth & Session State Provider
│   │   └── pages/            # 12 Complete MedPilot Modules
│   ├── package.json
│   └── vite.config.js
└── supabase/
    └── migrations/           # Full DDL & RLS Security Policies
```
