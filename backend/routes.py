# API endpoints
from fastapi import APIRouter, Depends, HTTPException
from .db import SessionLocal, Call
from sqlalchemy.orm import Session
from .auth import get_current_user
from .dashboard import get_dashboard_data, get_call_history
from .webhook import webhook_update

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    return get_dashboard_data()

@router.get("/calls")
def call_history(user=Depends(get_current_user)):
    return get_call_history()

@router.post("/webhook")
def webhook(data: dict, db: Session = Depends(get_db)):
    return webhook_update(data, db)
