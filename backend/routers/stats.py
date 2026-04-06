import calendar
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Category, Expense
from schemas import StatsByCategory, StatsByDay, StatsSummary, StatsForecast

router = APIRouter()


def _date_range(from_date, to_date, user_id, db):
    q = db.query(Expense).filter(Expense.user_id == user_id)
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    return q


@router.get("/stats/summary", response_model=StatsSummary)
def stats_summary(
    user_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    expenses = _date_range(from_date, to_date, user_id, db).all()
    if not expenses:
        return StatsSummary(total=0, count=0, avg_per_day=0, biggest_expense=None)

    total = sum(float(e.amount) for e in expenses)
    count = len(expenses)

    # days span
    if from_date and to_date:
        days = max((to_date - from_date).days + 1, 1)
    elif expenses:
        min_d = min(e.date for e in expenses)
        max_d = max(e.date for e in expenses)
        days = max((max_d - min_d).days + 1, 1)
    else:
        days = 1

    biggest = max(expenses, key=lambda e: float(e.amount))
    return StatsSummary(
        total=round(total, 2),
        count=count,
        avg_per_day=round(total / days, 2),
        biggest_expense={"description": biggest.description, "amount": float(biggest.amount)},
    )


@router.get("/stats/by-category", response_model=list[StatsByCategory])
def stats_by_category(
    user_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    expenses = _date_range(from_date, to_date, user_id, db).all()
    if not expenses:
        return []

    total = sum(float(e.amount) for e in expenses)
    totals: dict[int | None, float] = {}
    for e in expenses:
        totals[e.category_id] = totals.get(e.category_id, 0) + float(e.amount)

    result = []
    for cat_id, cat_total in totals.items():
        if cat_id:
            cat = db.query(Category).filter(Category.id == cat_id).first()
            name = cat.name if cat else "Unknown"
            icon = cat.icon if cat else None
            color = cat.color if cat else None
        else:
            name, icon, color = "Uncategorized", None, None
        result.append(StatsByCategory(
            category_name=name,
            icon=icon,
            color=color,
            total=round(cat_total, 2),
            percentage=round(cat_total / total * 100, 1) if total else 0,
        ))
    return sorted(result, key=lambda x: -x.total)


@router.get("/stats/by-day", response_model=list[StatsByDay])
def stats_by_day(
    user_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Expense.date, func.sum(Expense.amount).label("total"))
        .filter(Expense.user_id == user_id)
        .filter(Expense.date >= from_date if from_date else True)
        .filter(Expense.date <= to_date if to_date else True)
        .group_by(Expense.date)
        .order_by(Expense.date)
        .all()
    )
    return [StatsByDay(date=r.date, total=round(float(r.total), 2)) for r in rows]


@router.get("/stats/forecast", response_model=StatsForecast)
def stats_forecast(
    user_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM, defaults to current month"),
    db: Session = Depends(get_db),
):
    if month:
        year, mon = int(month.split("-")[0]), int(month.split("-")[1])
        month_start = date(year, mon, 1)
        today = date(year, mon, calendar.monthrange(year, mon)[1])
    else:
        today = date.today()
        month_start = today.replace(day=1)

    days_passed = max((today - month_start).days + 1, 1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining = days_in_month - days_passed

    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == user_id, Expense.date >= month_start, Expense.date <= today)
        .all()
    )

    total_so_far = sum(float(e.amount) for e in expenses)
    daily_avg = total_so_far / days_passed
    projected = round(total_so_far + daily_avg * days_remaining, 2)

    # last month total for comparison
    if month_start.month == 1:
        last_month_start = date(month_start.year - 1, 12, 1)
    else:
        last_month_start = date(month_start.year, month_start.month - 1, 1)
    last_month_end = month_start - __import__("datetime").timedelta(days=1)
    last_month_expenses = (
        db.query(Expense)
        .filter(Expense.user_id == user_id, Expense.date >= last_month_start, Expense.date <= last_month_end)
        .all()
    )
    last_month_total = round(sum(float(e.amount) for e in last_month_expenses), 2)

    # top categories for what-if
    by_cat: dict[str, float] = {}
    by_cat_count: dict[str, int] = {}
    by_cat_icon: dict[str, str] = {}
    for e in expenses:
        cat_name = e.category.name if e.category else "Other"
        cat_icon = (e.category.icon or "") if e.category else ""
        by_cat[cat_name] = by_cat.get(cat_name, 0) + float(e.amount)
        by_cat_count[cat_name] = by_cat_count.get(cat_name, 0) + 1
        by_cat_icon[cat_name] = cat_icon

    top = sorted(by_cat.items(), key=lambda x: -x[1])[:3]
    whatif = []
    for cat, spent in top:
        whatif.append({
            "category": cat,
            "icon": by_cat_icon.get(cat, ""),
            "total": round(spent, 2),
            "count": by_cat_count[cat],
            "save_half": round(spent / 2, 2),
            "projected_if_half": round(projected - spent / 2, 2),
        })

    return StatsForecast(
        total_so_far=round(total_so_far, 2),
        daily_avg=round(daily_avg, 2),
        days_passed=days_passed,
        days_remaining=days_remaining,
        projected=projected,
        last_month_total=last_month_total,
        whatif=whatif,
    )
