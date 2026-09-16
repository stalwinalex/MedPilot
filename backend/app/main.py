from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
import app.models.models  # ensure models are registered
from app.api import auth, subjects, timetable, attendance, exams, planner, agent, resources, habits, friends, account


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # SQLite migration check for new columns
        def _check_sqlite_columns(sync_conn):
            try:
                cursor = sync_conn.connection.cursor()
                cursor.execute("PRAGMA table_info(profiles)")
                prof_cols = [row[1] for row in cursor.fetchall()]
                if prof_cols and "timetable_start_date" not in prof_cols:
                    cursor.execute("ALTER TABLE profiles ADD COLUMN timetable_start_date DATE DEFAULT NULL")

                cursor.execute("PRAGMA table_info(timetable_rules)")
                tr_cols = [row[1] for row in cursor.fetchall()]
                if tr_cols and "effective_from" not in tr_cols:
                    cursor.execute("ALTER TABLE timetable_rules ADD COLUMN effective_from DATE DEFAULT NULL")

                cursor.execute("PRAGMA table_info(subjects)")
                cols = [row[1] for row in cursor.fetchall()]
                if cols and "faculty" not in cols:
                    cursor.execute("ALTER TABLE subjects ADD COLUMN faculty VARCHAR(100) DEFAULT ''")
                if cols and "academic_year" not in cols:
                    cursor.execute("ALTER TABLE subjects ADD COLUMN academic_year VARCHAR(50) DEFAULT ''")

                cursor.execute("PRAGMA table_info(attendance)")
                att_cols = [row[1] for row in cursor.fetchall()]
                if att_cols and "is_archived" not in att_cols:
                    cursor.execute("ALTER TABLE attendance ADD COLUMN is_archived BOOLEAN DEFAULT 0")
                if att_cols and "archive_label" not in att_cols:
                    cursor.execute("ALTER TABLE attendance ADD COLUMN archive_label VARCHAR(100) DEFAULT ''")

                cursor.execute("PRAGMA table_info(class_occurrences)")
                occ_cols = [row[1] for row in cursor.fetchall()]
                if occ_cols and "is_archived" not in occ_cols:
                    cursor.execute("ALTER TABLE class_occurrences ADD COLUMN is_archived BOOLEAN DEFAULT 0")
                if occ_cols and "archive_label" not in occ_cols:
                    cursor.execute("ALTER TABLE class_occurrences ADD COLUMN archive_label VARCHAR(100) DEFAULT ''")

                cursor.execute("PRAGMA table_info(habits)")
                habit_cols = [row[1] for row in cursor.fetchall()]
                if habit_cols and "selected_days" not in habit_cols:
                    cursor.execute("ALTER TABLE habits ADD COLUMN selected_days VARCHAR(50) DEFAULT '0,1,2,3,4,5,6'")
                if habit_cols and "reminder_time" not in habit_cols:
                    cursor.execute("ALTER TABLE habits ADD COLUMN reminder_time VARCHAR(30) DEFAULT ''")
                if habit_cols and "note" not in habit_cols:
                    cursor.execute("ALTER TABLE habits ADD COLUMN note TEXT DEFAULT ''")
                if habit_cols and "is_paused" not in habit_cols:
                    cursor.execute("ALTER TABLE habits ADD COLUMN is_paused BOOLEAN DEFAULT 0")
                if habit_cols and "order_index" not in habit_cols:
                    cursor.execute("ALTER TABLE habits ADD COLUMN order_index INTEGER DEFAULT 0")

                cursor.execute("PRAGMA table_info(class_topics)")
                ct_cols = [row[1] for row in cursor.fetchall()]
                if ct_cols and "study_status" not in ct_cols:
                    cursor.execute("ALTER TABLE class_topics ADD COLUMN study_status VARCHAR(20) DEFAULT 'study'")
                if ct_cols and "snooze_until" not in ct_cols:
                    cursor.execute("ALTER TABLE class_topics ADD COLUMN snooze_until DATE DEFAULT NULL")
                if ct_cols and "skip_reason" not in ct_cols:
                    cursor.execute("ALTER TABLE class_topics ADD COLUMN skip_reason VARCHAR(50) DEFAULT NULL")

                cursor.execute("PRAGMA table_info(study_tasks)")
                task_cols = [row[1] for row in cursor.fetchall()]
                if task_cols and "actual_minutes" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN actual_minutes INTEGER DEFAULT NULL")
                if task_cols and "feedback" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN feedback VARCHAR(30) DEFAULT NULL")
                if task_cols and "reason" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN reason VARCHAR(255) DEFAULT ''")
                if task_cols and "topic_name" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN topic_name VARCHAR(255) DEFAULT NULL")
                if task_cols and "planning_score" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN planning_score FLOAT DEFAULT NULL")
                if task_cols and "missed_class_date" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN missed_class_date DATE DEFAULT NULL")
                if task_cols and "syllabus_portion" not in task_cols:
                    cursor.execute("ALTER TABLE study_tasks ADD COLUMN syllabus_portion VARCHAR(255) DEFAULT NULL")

                cursor.execute("PRAGMA table_info(exams)")
                exam_cols = [row[1] for row in cursor.fetchall()]
                if exam_cols and "syllabus_portion" not in exam_cols:
                    cursor.execute("ALTER TABLE exams ADD COLUMN syllabus_portion VARCHAR(255) DEFAULT NULL")
                if exam_cols and "updated_at" not in exam_cols:
                    cursor.execute("ALTER TABLE exams ADD COLUMN updated_at DATETIME DEFAULT NULL")

                cursor.execute("PRAGMA table_info(study_plans)")
                plan_cols = [row[1] for row in cursor.fetchall()]
                if plan_cols and "daily_study_budget_minutes" not in plan_cols:
                    cursor.execute("ALTER TABLE study_plans ADD COLUMN daily_study_budget_minutes INTEGER DEFAULT 120")
                if plan_cols and "updated_at" not in plan_cols:
                    cursor.execute("ALTER TABLE study_plans ADD COLUMN updated_at DATETIME DEFAULT NULL")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS wellbeing_checkins (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL,
                        date DATE NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        mood VARCHAR(20),
                        notes TEXT DEFAULT '',
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY (user_id) REFERENCES profiles (id) ON DELETE CASCADE,
                        CONSTRAINT uq_wellbeing_user_date UNIQUE (user_id, date)
                    )
                """)
            except Exception as e:
                pass
        await conn.run_sync(_check_sqlite_columns)

    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Agentic AI Academic Companion for MBBS Students",
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "version": settings.VERSION
    }

# Mount modular routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(subjects.router, prefix=settings.API_PREFIX)
app.include_router(timetable.router, prefix=settings.API_PREFIX)
app.include_router(attendance.router, prefix=settings.API_PREFIX)
app.include_router(exams.router, prefix=settings.API_PREFIX)
app.include_router(planner.router, prefix=settings.API_PREFIX)
app.include_router(agent.router, prefix=settings.API_PREFIX)
app.include_router(resources.router, prefix=settings.API_PREFIX)
app.include_router(habits.router, prefix=settings.API_PREFIX)
app.include_router(friends.router, prefix=settings.API_PREFIX)
app.include_router(account.router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
