from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Goal
from schemas import GoalCreate, GoalDeposit, GoalOut

router = APIRouter()


@router.post("/goals", response_model=GoalOut, status_code=201)
def create_goal(body: GoalCreate, db: Session = Depends(get_db)):
    goal = Goal(
        user_id=body.user_id,
        name=body.name,
        target=body.target,
        saved=0,
        deadline=body.deadline,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/goals", response_model=list[GoalOut])
def list_goals(user_id: int, db: Session = Depends(get_db)):
    return db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.created_at).all()


@router.put("/goals/{goal_id}/deposit", response_model=GoalOut)
def deposit(goal_id: int, body: GoalDeposit, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.saved = float(goal.saved) + body.amount
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
