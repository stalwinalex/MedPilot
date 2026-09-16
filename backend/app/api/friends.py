from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Profile, Friend, FriendRequest, SharedResource, GeneratedResource
from app.schemas.schemas import FriendRequestSend, FriendRequestRespond, ShareResourceRequest

router = APIRouter(prefix="/friends", tags=["Friends & Private Sharing"])


@router.get("/")
async def get_friends(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Friend).filter(Friend.user_id == current_user.id)
    friendships = (await db.execute(stmt)).scalars().all()
    
    friend_ids = [f.friend_user_id for f in friendships]
    if not friend_ids:
        return []

    p_stmt = select(Profile).filter(Profile.id.in_(friend_ids))
    profiles = (await db.execute(p_stmt)).scalars().all()
    return [{"id": p.id, "full_name": p.full_name, "email": p.email, "college": p.college} for p in profiles]


@router.get("/requests")
async def get_friend_requests(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Incoming requests
    inc_stmt = select(FriendRequest).filter(
        FriendRequest.receiver_id == current_user.id,
        FriendRequest.status == "pending"
    )
    incoming = (await db.execute(inc_stmt)).scalars().all()

    sender_ids = [r.sender_id for r in incoming]
    senders = {}
    if sender_ids:
        s_res = await db.execute(select(Profile).filter(Profile.id.in_(sender_ids)))
        for p in s_res.scalars().all():
            senders[p.id] = {"full_name": p.full_name, "email": p.email, "college": p.college}

    return [
        {
            "id": r.id,
            "sender_id": r.sender_id,
            "sender": senders.get(r.sender_id, {}),
            "created_at": r.created_at
        }
        for r in incoming
    ]


@router.post("/requests")
async def send_friend_request(
    req: FriendRequestSend,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if req.recipient_email.lower() == current_user.email.lower():
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")

    target_res = await db.execute(select(Profile).filter(Profile.email == req.recipient_email.lower()))
    recipient = target_res.scalars().first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Student with that email not found")

    # Check if already friends
    f_res = await db.execute(select(Friend).filter(Friend.user_id == current_user.id, Friend.friend_user_id == recipient.id))
    if f_res.scalars().first():
        raise HTTPException(status_code=400, detail="Already friends with this student")

    # Check existing request
    req_res = await db.execute(select(FriendRequest).filter(
        FriendRequest.sender_id == current_user.id,
        FriendRequest.receiver_id == recipient.id,
        FriendRequest.status == "pending"
    ))
    if req_res.scalars().first():
        raise HTTPException(status_code=400, detail="Friend request already pending")

    freq = FriendRequest(
        sender_id=current_user.id,
        receiver_id=recipient.id,
        status="pending"
    )
    db.add(freq)
    await db.commit()
    return {"message": f"Friend request sent to {recipient.full_name}"}


@router.post("/requests/{request_id}/respond")
async def respond_to_friend_request(
    request_id: str,
    action: str,  # 'accept' or 'reject'
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.receiver_id == current_user.id,
        FriendRequest.status == "pending"
    )
    req = (await db.execute(stmt)).scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found")

    if action == "accept":
        req.status = "accepted"
        # Create mutual friendship records
        f1 = Friend(user_id=req.sender_id, friend_user_id=req.receiver_id)
        f2 = Friend(user_id=req.receiver_id, friend_user_id=req.sender_id)
        db.add(f1)
        db.add(f2)
    else:
        req.status = "rejected"

    await db.commit()
    return {"message": f"Request {action}ed"}


@router.post("/share")
async def share_resource(
    req: ShareResourceRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify user owns the resource
    res_stmt = select(GeneratedResource).filter(
        GeneratedResource.id == req.resource_id,
        GeneratedResource.user_id == current_user.id
    )
    resource = (await db.execute(res_stmt)).scalars().first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found or unauthorized")

    # Verify recipient is a friend
    fr_stmt = select(Friend).filter(
        Friend.user_id == current_user.id,
        Friend.friend_user_id == req.recipient_user_id
    )
    friendship = (await db.execute(fr_stmt)).scalars().first()
    if not friendship:
        raise HTTPException(status_code=403, detail="Can only share resources with accepted friends")

    # Create or update shared resource entry
    sh_stmt = select(SharedResource).filter(
        SharedResource.resource_id == req.resource_id,
        SharedResource.receiver_id == req.recipient_user_id
    )
    existing = (await db.execute(sh_stmt)).scalars().first()
    if not existing:
        shared = SharedResource(
            resource_id=req.resource_id,
            sender_id=current_user.id,
            receiver_id=req.recipient_user_id,
            permission=req.permission or "view"
        )
        db.add(shared)
    else:
        existing.permission = req.permission or "view"

    await db.commit()
    return {"message": "Resource shared successfully"}


@router.get("/shared-with-me")
async def get_shared_with_me(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(SharedResource)
        .options(selectinload(SharedResource.resource))
        .filter(SharedResource.receiver_id == current_user.id)
        .order_by(SharedResource.created_at.desc())
    )
    shared_items = (await db.execute(stmt)).scalars().all()

    results = []
    for s in shared_items:
        sender = (await db.execute(select(Profile).filter(Profile.id == s.sender_id))).scalars().first()
        results.append({
            "shared_id": s.id,
            "resource_id": s.resource_id,
            "title": s.resource.title if s.resource else "Untitled",
            "resource_type": s.resource.resource_type if s.resource else "notes",
            "permission": s.permission,
            "shared_by": sender.full_name if sender else "A student",
            "created_at": s.created_at
        })
    return results
