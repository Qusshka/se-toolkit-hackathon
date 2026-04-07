from datetime import date, datetime, time, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Expense, Reminder
from schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate


def _is_impulse(created_at: datetime, recent_expenses: list) -> bool:
    late_night = created_at.time() >= time(23, 0) or created_at.time() <= time(4, 0)
    cutoff = created_at - timedelta(minutes=30)
    rapid = sum(1 for e in recent_expenses if e.created_at >= cutoff) >= 2
    return late_night or rapid

router = APIRouter()


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(body: ExpenseCreate, db: Session = Depends(get_db)):
    expense_date = body.date or date.today()
    next_reminder = None
    if body.is_recurring and body.recur_days:
        next_reminder = expense_date + timedelta(days=body.recur_days)

    now = datetime.utcnow()
    recent = (
        db.query(Expense)
        .filter(Expense.user_id == body.user_id, Expense.created_at >= now - timedelta(minutes=30))
        .all()
    )
    impulse = _is_impulse(now, recent)

    expense = Expense(
        user_id=body.user_id,
        amount=body.amount,
        description=body.description,
        category_id=body.category_id,
        date=expense_date,
        is_recurring=body.is_recurring,
        recur_days=body.recur_days,
        next_reminder=next_reminder,
        is_impulse=impulse,
    )
    db.add(expense)
    db.flush()

    if body.is_recurring and body.recur_days:
        db.add(Reminder(
            expense_id=expense.id,
            user_id=body.user_id,
            remind_at=next_reminder,
            message=f"Recurring: {body.description} — {body.amount}",
        ))

    db.commit()
    db.refresh(expense)
    return expense


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(
    user_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    category_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Expense).filter(Expense.user_id == user_id)
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    if category_id:
        q = q.filter(Expense.category_id == category_id)
    return q.order_by(Expense.date.desc(), Expense.id.desc()).offset(offset).limit(limit).all()


@router.get("/expenses/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.put("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, body: ExpenseUpdate, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
