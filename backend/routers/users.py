from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import DigestToggle, UserCreate, UserOut

router = APIRouter()


@router.post("/users", response_model=UserOut)
def upsert_user(body: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == body.telegram_id).first()
    if user:
        user.username = body.username
        user.first_name = body.first_name
    else:
        user = User(
            telegram_id=body.telegram_id,
            username=body.username,
            first_name=body.first_name,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/digest-enabled", response_model=list[UserOut])
def digest_enabled_users(db: Session = Depends(get_db)):
    return db.query(User).filter(User.digest_enabled == True).all()


@router.patch("/users/{user_id}/digest", response_model=UserOut)
def toggle_digest(user_id: int, body: DigestToggle, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.digest_enabled = body.enabled
    db.commit()
    db.refresh(user)
    return user
