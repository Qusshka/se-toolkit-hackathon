from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Reminder
from schemas import ReminderOut

router = APIRouter()


@router.get("/reminders/due", response_model=list[ReminderOut])
def due_reminders(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Reminder)
        .filter(Reminder.user_id == user_id)
        .filter(Reminder.remind_at <= date.today())
        .filter(Reminder.is_sent == False)
        .order_by(Reminder.remind_at)
        .all()
    )


@router.post("/reminders/{reminder_id}/dismiss", response_model=ReminderOut)
def dismiss_reminder(reminder_id: int, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder.is_sent = True
    db.commit()
    db.refresh(reminder)
    return reminder
