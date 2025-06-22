# Webhook logic
from .db import Call, SessionLocal
from sqlalchemy.orm import Session

def webhook_update(data: dict, db: Session):
    # Example: store call data in DB
    call = Call(**data)
    db.add(call)
    db.commit()
    db.refresh(call)
    return {"status": "success", "call_id": call.id}
