# backend/routes.py - Enhanced API endpoints with full functionality

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import csv
import io
from pydantic import BaseModel

from models import (
    get_db, Call, CallMetrics, TranscriptSegment, CallSummary, 
    Client, Agent
)
from auth import get_current_user
from services import RedisService, CallAnalyticsService

router = APIRouter(prefix="/api/v1", tags=["Call Center API"])

# Pydantic models for request/response
class CallCreateRequest(BaseModel):
    call_id: str
    room_name: str
    phone_number: str
    caller_name: Optional[str] = None
    client_id: Optional[int] = 1
    agent_id: Optional[int] = None

class WebhookCallData(BaseModel):
    """Flexible webhook data model"""
    call_id: str
    room_name: Optional[str] = None
    phone_number: Optional[str] = None
    caller_name: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class TranscriptSegmentData(BaseModel):
    """Redis transcript data model"""
    history_id: int
    timestamp: int  # Unix timestamp in milliseconds
    room_id: str
    speaker: str
    message: str

class DashboardFilters(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    client_id: Optional[int] = None
    agent_id: Optional[int] = None
    status: Optional[str] = None
    phone_number: Optional[str] = None

# Dashboard endpoints
@router.get("/dashboard/summary")
async def get_dashboard_summary(
    client_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get high-level dashboard summary data"""
    
    # Build base query
    query = db.query(Call)
    
    if client_id:
        query = query.filter(Call.client_id == client_id)
    
    if start_date:
        query = query.filter(Call.call_time >= start_date)
    
    if end_date:
        query = query.filter(Call.call_time <= end_date)
    
    # Get basic counts
    total_calls = query.count()
    calls_picked = query.filter(Call.status.in_(["active", "completed"])).count()
    completed_calls = query.filter(Call.status == "completed").count()
    
    # Calculate leads generated (calls with positive outcomes)
    leads_generated = query.filter(
        Call.call_outcome.in_(["lead_generated", "appointment_scheduled", "sale_completed"])
    ).count()
    
    # Get performance metrics
    completed_query = query.filter(Call.status == "completed")
    avg_duration = db.query(func.avg(Call.duration)).filter(
        Call.id.in_([c.id for c in completed_query.all()])
    ).scalar() or 0
    
    # Get today's stats for comparison
    today = datetime.now().date()
    today_calls = query.filter(func.date(Call.call_time) == today).count()
    
    # Calculate success rate
    success_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
    
    return {
        "total_calls": total_calls,
        "calls_picked": calls_picked,
        "leads_generated": leads_generated,
        "completed_calls": completed_calls,
        "success_rate": round(success_rate, 2),
        "avg_call_duration": round(avg_duration or 0, 2),
        "today_calls": today_calls,
        "performance_indicators": {
            "call_pickup_rate": round((calls_picked / total_calls * 100) if total_calls > 0 else 0, 2),
            "lead_conversion_rate": round((leads_generated / total_calls * 100) if total_calls > 0 else 0, 2)
        }
    }

@router.get("/dashboard/trends")
async def get_dashboard_trends(
    days: int = Query(7, description="Number of days to analyze"),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get trend data for charts"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Daily call counts
    daily_stats = db.query(
        func.date(Call.call_time).label('date'),
        func.count(Call.id).label('total_calls'),
        func.count(Call.id).filter(Call.status == 'completed').label('completed_calls'),
        func.count(Call.id).filter(
            Call.call_outcome.in_(['lead_generated', 'appointment_scheduled'])
        ).label('leads')
    ).filter(
        Call.call_time >= start_date,
        Call.call_time <= end_date
    )
    
    if client_id:
        daily_stats = daily_stats.filter(Call.client_id == client_id)
    
    daily_stats = daily_stats.group_by(func.date(Call.call_time)).all()
    
    # Hourly distribution for today
    today = datetime.now().date()
    hourly_stats = db.query(
        func.extract('hour', Call.call_time).label('hour'),
        func.count(Call.id).label('calls')
    ).filter(
        func.date(Call.call_time) == today
    )
    
    if client_id:
        hourly_stats = hourly_stats.filter(Call.client_id == client_id)
    
    hourly_stats = hourly_stats.group_by(func.extract('hour', Call.call_time)).all()
    
    return {
        "daily_trends": [
            {
                "date": stat.date.isoformat(),
                "total_calls": stat.total_calls,
                "completed_calls": stat.completed_calls,
                "leads": stat.leads
            }
            for stat in daily_stats
        ],
        "hourly_distribution": [
            {"hour": int(stat.hour), "calls": stat.calls}
            for stat in hourly_stats
        ]
    }

# Call history endpoints
@router.get("/calls")
async def get_call_history(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    agent_id: Optional[int] = Query(None),
    client_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get call history with filtering and pagination"""
    
    # Build query with filters
    query = db.query(Call).join(Agent, Call.agent_id == Agent.id, isouter=True)
    
    if client_id:
        query = query.filter(Call.client_id == client_id)
    
    if start_date:
        query = query.filter(Call.call_time >= start_date)
    
    if end_date:
        query = query.filter(Call.call_time <= end_date)
    
    if status:
        query = query.filter(Call.status == status)
    
    if phone_number:
        query = query.filter(Call.phone_number.like(f"%{phone_number}%"))
    
    if agent_id:
        query = query.filter(Call.agent_id == agent_id)
    
    if search:
        query = query.filter(
            or_(
                Call.caller_name.like(f"%{search}%"),
                Call.phone_number.like(f"%{search}%"),
                Call.call_id.like(f"%{search}%")
            )
        )
    
    # Get total count for pagination
    total_count = query.count()
    
    # Apply pagination and ordering
    calls = query.order_by(desc(Call.call_time)).offset((page - 1) * limit).limit(limit).all()
    
    # Format response
    formatted_calls = []
    for call in calls:
        formatted_calls.append({
            "id": call.id,
            "call_id": call.call_id,
            "phone_number": call.phone_number,
            "caller_name": call.caller_name,
            "call_time": call.call_time.isoformat() if call.call_time else None,
            "duration": call.duration,
            "status": call.status,
            "call_outcome": call.call_outcome,
            "agent_name": call.agent.name if call.agent else "Unknown",
            "room_name": call.room_name,
            "summary": call.summary
        })
    
    return {
        "calls": formatted_calls,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit
        }
    }

@router.get("/calls/{call_id}")
async def get_call_details(
    call_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information for a specific call"""
    
    call = db.query(Call).filter(
        or_(Call.call_id == call_id, Call.id == call_id)
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get call metrics
    metrics = db.query(CallMetrics).filter(CallMetrics.call_id == call.id).first()
    
    # Get transcript segments
    transcript_segments = db.query(TranscriptSegment).filter(
        TranscriptSegment.call_id == call.id
    ).order_by(TranscriptSegment.timestamp).all()
    
    return {
        "call": {
            "id": call.id,
            "call_id": call.call_id,
            "phone_number": call.phone_number,
            "caller_name": call.caller_name,
            "call_time": call.call_time.isoformat() if call.call_time else None,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "end_time": call.end_time.isoformat() if call.end_time else None,
            "duration": call.duration,
            "status": call.status,
            "call_outcome": call.call_outcome,
            "transcript": call.transcript,
            "summary": call.summary,
            "sentiment_score": call.sentiment_score,
            "quality_score": call.quality_score,
            "metadata": call.metadata
        },
        "metrics": {
            "llm_calls": metrics.llm_calls if metrics else 0,
            "avg_ttft": metrics.avg_ttft if metrics else 0,
            "tts_calls": metrics.tts_calls if metrics else 0,
            "avg_tts_ttfb": metrics.avg_tts_ttfb if metrics else 0,
            "asr_calls": metrics.asr_calls if metrics else 0,
            "total_interactions": metrics.total_interactions if metrics else 0,
            "avg_user_latency": metrics.avg_user_latency if metrics else 0
        } if metrics else {},
        "transcript_segments": [
            {
                "timestamp": segment.timestamp.isoformat(),
                "speaker": segment.speaker,
                "message": segment.message,
                "sentiment": segment.sentiment
            }
            for segment in transcript_segments
        ]
    }

# Export functionality
@router.get("/calls/export/csv")
async def export_calls_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Export call data as CSV"""
    
    # Build query with same filters as get_call_history
    query = db.query(Call).join(Agent, Call.agent_id == Agent.id, isouter=True)
    
    if client_id:
        query = query.filter(Call.client_id == client_id)
    if start_date:
        query = query.filter(Call.call_time >= start_date)
    if end_date:
        query = query.filter(Call.call_time <= end_date)
    if status:
        query = query.filter(Call.status == status)
    
    calls = query.order_by(desc(Call.call_time)).all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Call ID', 'Phone Number', 'Caller Name', 'Call Time', 'Duration (seconds)',
        'Status', 'Call Outcome', 'Agent Name', 'Room Name', 'Summary'
    ])
    
    # Write data
    for call in calls:
        writer.writerow([
            call.call_id,
            call.phone_number,
            call.caller_name or '',
            call.call_time.isoformat() if call.call_time else '',
            call.duration or 0,
            call.status or '',
            call.call_outcome or '',
            call.agent.name if call.agent else '',
            call.room_name or '',
            call.summary or ''
        ])
    
    output.seek(0)
    
    # Create response
    response = StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type='text/csv',
        headers={"Content-Disposition": f"attachment; filename=calls_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )
    
    return response

# Webhook endpoints
@router.post("/webhook/call-data")
async def webhook_call_data(
    call_data: WebhookCallData,
    db: Session = Depends(get_db)
):
    """Generic webhook to receive call data from external systems"""
    
    try:
        # Check if call exists
        existing_call = db.query(Call).filter(Call.call_id == call_data.call_id).first()
        
        if existing_call:
            # Update existing call
            if call_data.status:
                existing_call.status = call_data.status
            if call_data.end_time:
                existing_call.end_time = call_data.end_time
                if existing_call.start_time:
                    existing_call.duration = int((call_data.end_time - existing_call.start_time).total_seconds())
            if call_data.transcript:
                existing_call.transcript = call_data.transcript
            if call_data.summary:
                existing_call.summary = call_data.summary
            if call_data.metadata:
                existing_call.metadata = call_data.metadata
            
            db.commit()
            db.refresh(existing_call)
            return {"status": "success", "action": "updated", "call_id": existing_call.id}
        
        else:
            # Create new call
            new_call = Call(
                call_id=call_data.call_id,
                room_name=call_data.room_name,
                phone_number=call_data.phone_number,
                caller_name=call_data.caller_name,
                status=call_data.status or "active",
                start_time=call_data.start_time or datetime.utcnow(),
                end_time=call_data.end_time,
                transcript=call_data.transcript,
                summary=call_data.summary,
                metadata=call_data.metadata,
                client_id=1  # Default client
            )
            
            if call_data.start_time and call_data.end_time:
                new_call.duration = int((call_data.end_time - call_data.start_time).total_seconds())
            
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            return {"status": "success", "action": "created", "call_id": new_call.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")

@router.post("/webhook/transcript")
async def webhook_transcript_segment(
    transcript_data: TranscriptSegmentData,
    db: Session = Depends(get_db)
):
    """Webhook to receive individual transcript segments from Redis"""
    
    try:
        # Find the call by room_id (assuming room_id maps to call_id or room_name)
        call = db.query(Call).filter(
            or_(
                Call.call_id == transcript_data.room_id,
                Call.room_name == transcript_data.room_id
            )
        ).first()
        
        if not call:
            # Create a new call if it doesn't exist
            call = Call(
                call_id=transcript_data.room_id,
                room_name=transcript_data.room_id,
                status="active",
                start_time=datetime.utcnow(),
                client_id=1  # Default client
            )
            db.add(call)
            db.commit()
            db.refresh(call)
        
        # Create transcript segment
        segment = TranscriptSegment(
            call_id=call.id,
            history_id=transcript_data.history_id,
            timestamp=datetime.fromtimestamp(transcript_data.timestamp / 1000),  # Convert from milliseconds
            speaker=transcript_data.speaker,
            message=transcript_data.message
        )
        
        db.add(segment)
        db.commit()
        
        return {"status": "success", "call_id": call.id, "segment_id": segment.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing transcript: {str(e)}")

# Analytics endpoints
@router.get("/analytics/performance")
async def get_performance_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get performance analytics data"""
    
    # Base query for calls with metrics
    query = db.query(Call).join(CallMetrics, Call.id == CallMetrics.call_id, isouter=True)
    
    if client_id:
        query = query.filter(Call.client_id == client_id)
    if start_date:
        query = query.filter(Call.call_time >= start_date)
    if end_date:
        query = query.filter(Call.call_time <= end_date)
    
    calls_with_metrics = query.all()
    
    if not calls_with_metrics:
        return {"message": "No data available for the specified period"}
    
    # Calculate averages
    total_calls = len(calls_with_metrics)
    avg_duration = sum(c.duration for c in calls_with_metrics if c.duration) / total_calls
    
    # Metrics calculations
    calls_with_llm_metrics = [c for c in calls_with_metrics if c.metrics and c.metrics[0].avg_ttft]
    avg_ttft = sum(m.metrics[0].avg_ttft for m in calls_with_llm_metrics) / len(calls_with_llm_metrics) if calls_with_llm_metrics else 0
    
    calls_with_user_metrics = [c for c in calls_with_metrics if c.metrics and c.metrics[0].avg_user_latency]
    avg_user_latency = sum(m.metrics[0].avg_user_latency for m in calls_with_user_metrics) / len(calls_with_user_metrics) if calls_with_user_metrics else 0
    
    return {
        "period_summary": {
            "total_calls": total_calls,
            "avg_call_duration": round(avg_duration, 2),
            "avg_ttft": round(avg_ttft, 3),
            "avg_user_latency": round(avg_user_latency, 3)
        },
        "quality_metrics": {
            "calls_with_quality_scores": len([c for c in calls_with_metrics if c.quality_score]),
            "avg_quality_score": round(
                sum(c.quality_score for c in calls_with_metrics if c.quality_score) / 
                len([c for c in calls_with_metrics if c.quality_score]), 2
            ) if any(c.quality_score for c in calls_with_metrics) else 0
        }
    }

# Status endpoint
@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)):
    """Get system status and health"""
    
    # Get basic counts
    total_clients = db.query(Client).count()
    total_agents = db.query(Agent).count()
    total_calls = db.query(Call).count()
    
    # Get recent activity
    recent_calls = db.query(Call).filter(
        Call.call_time >= datetime.now() - timedelta(hours=24)
    ).count()
    
    active_calls = db.query(Call).filter(Call.status == "active").count()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": {
            "total_clients": total_clients,
            "total_agents": total_agents,
            "total_calls": total_calls
        },
        "activity": {
            "calls_last_24h": recent_calls,
            "active_calls": active_calls
        }
    }