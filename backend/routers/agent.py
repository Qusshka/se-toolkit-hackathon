from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Expense, Category
from schemas import AgentChatRequest, AgentChatResponse, AgentInsightRequest, AgentInsightResponse
from services import ai_agent

router = APIRouter()


def _get_expenses_as_dicts(user_id: int, context_days: int, db: Session) -> list[dict]:
    from_date = date.today() - timedelta(days=context_days)
    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == user_id, Expense.date >= from_date)
        .order_by(Expense.date)
        .all()
    )
    result = []
    for e in expenses:
        cat_name = e.category.name if e.category else "Other"
        result.append({
            "id": e.id,
            "amount": float(e.amount),
            "description": e.description,
            "category": cat_name,
            "date": str(e.date),
            "is_recurring": e.is_recurring,
        })
    return result


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(body: AgentChatRequest, db: Session = Depends(get_db)):
    expenses = _get_expenses_as_dicts(body.user_id, body.context_days, db)
    context = ai_agent.build_context(expenses, body.context_days)
    reply = await ai_agent.chat(body.message, context, one_liner=False)
    return AgentChatResponse(reply=reply)


@router.post("/agent/insight", response_model=AgentInsightResponse)
async def agent_insight(body: AgentInsightRequest, db: Session = Depends(get_db)):
    expenses = _get_expenses_as_dicts(body.user_id, body.context_days, db)
    if not expenses:
        return AgentInsightResponse(tip="💡 Start logging expenses to get personalized tips!")
    context = ai_agent.build_context(expenses, body.context_days)
    tip = await ai_agent.chat("Give me one insight about my spending.", context, one_liner=True)
    return AgentInsightResponse(tip=tip)
