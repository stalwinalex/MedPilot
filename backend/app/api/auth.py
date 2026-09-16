from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import get_current_user, create_access_token, get_password_hash, verify_password
from app.models.models import Profile, Subject, Habit
from app.schemas.schemas import UserLogin, UserRegister, TokenResponse, ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])

DEFAULT_MBBS_SUBJECTS = [
    {"name": "Anatomy", "code": "ANAT", "color": "#0D9488"},
    {"name": "Physiology", "code": "PHYS", "color": "#2563EB"},
    {"name": "Biochemistry", "code": "BIOCHEM", "color": "#7C3AED"},
    {"name": "Pathology", "code": "PATH", "color": "#E11D48"},
    {"name": "Pharmacology", "code": "PHARM", "color": "#D97706"},
    {"name": "Microbiology", "code": "MICRO", "color": "#059669"},
    {"name": "Community Medicine", "code": "PSM", "color": "#4B5563"},
    {"name": "Forensic Medicine", "code": "FMT", "color": "#4338CA"},
]

DEFAULT_HABITS = [
    {"name": "Adequate Sleep (7-8 hours)", "category": "sleep"},
    {"name": "Hydration Goal (2.5L Water)", "category": "hydration"},
    {"name": "Regular Nutritious Meals", "category": "nutrition"},
    {"name": "Clinical Study Break & Stretch", "category": "break"},
    {"name": "Evening Academic Review Check-in", "category": "routine"},
]


@router.post("/register", response_model=TokenResponse)
async def register(req: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    stmt = select(Profile).filter(Profile.email == req.email.lower())
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    profile = Profile(
        email=req.email.lower(),
        full_name=req.full_name,
        college=req.college or "Medical College",
        year_of_study=req.year_of_study or "MBBS 1st Year",
        hashed_password=get_password_hash(req.password),
        target_attendance_percentage=75.0,
        daily_study_target_minutes=180
    )
    db.add(profile)
    await db.flush()

    # Seed default MBBS subjects for the student
    for s in DEFAULT_MBBS_SUBJECTS:
        subj = Subject(
            user_id=profile.id,
            name=s["name"],
            code=s["code"],
            color=s["color"],
            target_attendance=75.0
        )
        db.add(subj)

    # Seed default health & habit items (non-punitive)
    for h in DEFAULT_HABITS:
        habit = Habit(
            user_id=profile.id,
            name=h["name"],
            category=h["category"]
        )
        db.add(habit)

    await db.commit()
    await db.refresh(profile)

    token = create_access_token({"sub": profile.id, "email": profile.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": profile.id,
            "email": profile.email,
            "full_name": profile.full_name,
            "college": profile.college,
            "year_of_study": profile.year_of_study,
            "target_attendance_percentage": profile.target_attendance_percentage
        }
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLogin, db: AsyncSession = Depends(get_db)):
    stmt = select(Profile).filter(Profile.email == req.email.lower())
    profile = (await db.execute(stmt)).scalars().first()

    if not profile or not verify_password(req.password, profile.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token({"sub": profile.id, "email": profile.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": profile.id,
            "email": profile.email,
            "full_name": profile.full_name,
            "college": profile.college,
            "year_of_study": profile.year_of_study,
            "target_attendance_percentage": profile.target_attendance_percentage
        }
    )


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(current_user: Profile = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    update_data: ProfileUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    if update_data.college is not None:
        current_user.college = update_data.college
    if update_data.year_of_study is not None:
        current_user.year_of_study = update_data.year_of_study
    if update_data.target_attendance_percentage is not None:
        current_user.target_attendance_percentage = update_data.target_attendance_percentage
    if update_data.daily_study_target_minutes is not None:
        current_user.daily_study_target_minutes = update_data.daily_study_target_minutes

    await db.commit()
    await db.refresh(current_user)
    return current_user
