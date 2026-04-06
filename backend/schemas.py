from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


# --- User ---

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Category ---

class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: Optional[str]
    color: Optional[str]

    model_config = {"from_attributes": True}


# --- Expense ---

class ExpenseCreate(BaseModel):
    user_id: int
    amount: float
    description: str
    category_id: Optional[int] = None
    date: Optional[date] = None
    is_recurring: bool = False
    recur_days: Optional[int] = None


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    date: Optional[date] = None
    is_recurring: Optional[bool] = None
    recur_days: Optional[int] = None


class ExpenseOut(BaseModel):
    id: int
    user_id: int
    amount: float
    description: str
    category_id: Optional[int]
    date: date
    is_recurring: bool
    recur_days: Optional[int]
    next_reminder: Optional[date]
    created_at: datetime
    category: Optional[CategoryOut] = None

    model_config = {"from_attributes": True}


# --- Stats ---

class StatsSummary(BaseModel):
    total: float
    count: int
    avg_per_day: float
    biggest_expense: Optional[dict] = None


class StatsByCategory(BaseModel):
    category_name: str
    icon: Optional[str]
    color: Optional[str]
    total: float
    percentage: float


class StatsByDay(BaseModel):
    date: date
    total: float


class StatsForecast(BaseModel):
    total_so_far: float
    daily_avg: float
    days_passed: int
    days_remaining: int
    projected: float
    last_month_total: float
    whatif: list[dict]


# --- Reminder ---

class ReminderOut(BaseModel):
    id: int
    expense_id: int
    user_id: int
    remind_at: date
    message: Optional[str]
    is_sent: bool
    expense: Optional[ExpenseOut] = None

    model_config = {"from_attributes": True}


# --- AI Agent ---

class AgentChatRequest(BaseModel):
    user_id: int
    message: str
    context_days: int = 30


class AgentChatResponse(BaseModel):
    reply: str


class AgentInsightRequest(BaseModel):
    user_id: int
    context_days: int = 30


class AgentInsightResponse(BaseModel):
    tip: str
