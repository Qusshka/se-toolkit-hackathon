from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, SessionLocal, Base
from models import Category
from routers import categories, expenses, goals, stats, reminders, agent, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Category).count() == 0:
            db.add_all([
                Category(name="Food",          icon="🍔", color="#FF6384"),
                Category(name="Coffee",        icon="☕", color="#FF9F40"),
                Category(name="Transport",     icon="🚌", color="#FFCD56"),
                Category(name="Shopping",      icon="🛍️", color="#4BC0C0"),
                Category(name="Entertainment", icon="🎬", color="#36A2EB"),
                Category(name="Health",        icon="💊", color="#9966FF"),
                Category(name="Subscriptions", icon="📦", color="#C9CBCF"),
                Category(name="Other",         icon="💸", color="#E7E9ED"),
            ])
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="SpendSense API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(reminders.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
