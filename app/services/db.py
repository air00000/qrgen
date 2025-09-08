# app/services/db.py
from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from datetime import datetime, timedelta
import os

DB_PATH = os.getenv("DB_URL", "sqlite:///./app.db")
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})

class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    plan: str
    invoice_id: str
    start_at: datetime
    end_at: datetime

def init_db():
    SQLModel.metadata.create_all(engine)

def add_subscription(user_id: int, plan: str, invoice_id: str, days: int):
    now = datetime.utcnow()
    sub = Subscription(
        user_id=user_id,
        plan=plan,
        invoice_id=invoice_id,
        start_at=now,
        end_at=now + timedelta(days=days),
    )
    with Session(engine) as s:
        s.add(sub); s.commit()

def has_active_subscription(user_id: int) -> bool:
    now = datetime.utcnow()
    with Session(engine) as s:
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.end_at > now
        )
        return s.exec(stmt).first() is not None

def latest_subscription(user_id: int) -> Optional[Subscription]:
    with Session(engine) as s:
        stmt = select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.id.desc())
        return s.exec(stmt).first()
