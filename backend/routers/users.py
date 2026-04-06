from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserCreate, UserOut

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
