# backend/services.py - Service layer for Redis integration and analytics

import redis
import json
import asyncio
import aioredis
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import (
    Call, CallMetrics, TranscriptSegment, CallSummary,
    SessionLocal, Agent, Client
)

class RedisService:
    """Service for interacting with Redis data from agents"""
    
    def __init__(self, redis_host: str = "sbi.vaaniresearch.com", redis_port: int = 6379, redis_db: int = 0):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_client = None
    
    async def connect(self):
        """Establish Redis connection"""
        try:
            self.redis_client = aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}",
                decode_responses=True
            )
            await self.redis_client.ping()
            return True
        except Exception as e:
            print(f"Redis connection failed: {e}")
            return False
    
    async def get_room_history(self, room_id: str) -> List[Dict]:
        """Get transcript history for a room from Redis"""
        if not self.redis_client:
            await self.connect()
        
        try:
            history_key = f"room_history:{room_id}"
            messages = await self.redis_client.lrange(history_key, 0, -1)
            
            parsed_messages = []
            for msg in messages:
                try:
                    parsed = json.loads(msg)
                    parsed_messages.append(parsed)
                except json.JSONDecodeError:
                    continue
            
            # Sort by timestamp
            parsed_messages.sort(key=lambda x: x.get('timestamp', 0))
            return parsed_messages
            
        except Exception as e:
            print(f"Error getting room history: {e}")
            return []
    
    async def get_enhanced_metrics(self, call_id: str) -> Dict:
        """Get enhanced metrics for a call from Redis"""
        if not self.redis_client:
            await self.connect()
        
        try:
            metrics_key = f"enhanced_metrics:call:{call_id}"
            metrics_data = await self.redis_client.get(metrics_key)
            
            if metrics_data:
                return json.loads(metrics_data)
            return {}
            
        except Exception as e:
            print(f"Error getting enhanced metrics: {e}")
            return {}
    
    async def sync_call_from_redis(self, room_id: str, db: Session) -> Optional[Call]:
        """Sync call data from Redis to database"""
        
        # Get transcript history
        history = await self.get_room_history(room_id)
        if not history:
            return None
        
        # Check if call already exists
        call = db.query(Call).filter(
            (Call.call_id == room_id) | (Call.room_name == room_id)
        ).first()
        
        if not call:
            # Create new call
            call = Call(
                call_id=room_id,
                room_name=room_id,
                status="active",
                start_time=datetime.utcnow(),
                client_id=1  # Default client
            )
            db.add(call)
            db.commit()
            db.refresh(call)
        
        # Add transcript segments
        for message in history:
            # Check if segment already exists
            existing_segment = db.query(TranscriptSegment).filter(
                TranscriptSegment.call_id == call.id,
                TranscriptSegment.history_id == message.get('history_id')
            ).first()
            
            if not existing_segment:
                segment = TranscriptSegment(
                    call_id=call.id,
                    history_id=message.get('history_id'),
                    timestamp=datetime.fromtimestamp(message.get('timestamp', 0) / 1000),
                    speaker=message.get('speaker', 'unknown'),
                    message=message.get('message', '')
                )
                db.add(segment)
        
        # Try to get enhanced metrics
        enhanced_metrics = await self.get_enhanced_metrics(room_id)
        if enhanced_metrics:
            # Check if metrics already exist
            existing_metrics = db.query(CallMetrics).filter(
                CallMetrics.call_id == call.id
            ).first()
            
            if not existing_metrics:
                metrics = CallMetrics(
                    call_id=call.id,
                    llm_calls=enhanced_metrics.get('llm_calls', 0),
                    avg_ttft=enhanced_metrics.get('avg_ttft', 0),
                    tts_calls=enhanced_metrics.get('tts_calls', 0),
                    asr_calls=enhanced_metrics.get('asr_calls', 0),
                    total_interactions=enhanced_metrics.get('total_interactions', 0),
                    avg_user_latency=enhanced_metrics.get('avg_user_latency', 0),
                    additional_metrics=enhanced_metrics
                )
                db.add(metrics)
        
        db.commit()
        return call
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

class CallAnalyticsService:
    """Service for call analytics and insights"""
    
    @staticmethod
    def calculate_call_metrics(call: Call, transcript_segments: List[TranscriptSegment]) -> Dict:
        """Calculate various metrics for a call"""
        
        if not transcript_segments:
            return {}
        
        # Basic metrics
        total_segments = len(transcript_segments)
        user_segments = [s for s in transcript_segments if s.speaker == 'user']
        agent_segments = [s for s in transcript_segments if s.speaker in ['agent', 'llm']]
        
        # Calculate response times (simplified)
        response_times = []
        for i in range(len(transcript_segments) - 1):
            current = transcript_segments[i]
            next_segment = transcript_segments[i + 1]
            
            if current.speaker == 'user' and next_segment.speaker in ['agent', 'llm']:
                time_diff = (next_segment.timestamp - current.timestamp).total_seconds()
                if 0 < time_diff < 30:  # Reasonable response time
                    response_times.append(time_diff)
        
        return {
            "total_interactions": total_segments,
            "user_messages": len(user_segments),
            "agent_messages": len(agent_segments),
            "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
            "conversation_length": len(transcript_segments),
            "estimated_engagement": len(user_segments) / max(1, len(agent_segments))
        }
    
    @staticmethod
    def analyze_call_sentiment(transcript_segments: List[TranscriptSegment]) -> Dict:
        """Analyze sentiment of call (placeholder for actual sentiment analysis)"""
        
        # This is a placeholder - in production, you'd use a proper sentiment analysis service
        user_messages = [s.message for s in transcript_segments if s.speaker == 'user']
        
        # Simple keyword-based sentiment (replace with proper ML model)
        positive_words = ['good', 'great', 'excellent', 'happy', 'satisfied', 'thank you']
        negative_words = ['bad', 'terrible', 'angry', 'frustrated', 'disappointed', 'complaint']
        
        positive_count = sum(1 for msg in user_messages for word in positive_words if word.lower() in msg.lower())
        negative_count = sum(1 for msg in user_messages for word in negative_words if word.lower() in msg.lower())
        
        if positive_count > negative_count:
            overall_sentiment = "positive"
        elif negative_count > positive_count:
            overall_sentiment = "negative"
        else:
            overall_sentiment = "neutral"
        
        return {
            "overall_sentiment": overall_sentiment,
            "positive_indicators": positive_count,
            "negative_indicators": negative_count,
            "sentiment_score": (positive_count - negative_count) / max(1, len(user_messages))
        }
    
    @staticmethod
    def generate_call_summary(call: Call, transcript_segments: List[TranscriptSegment]) -> str:
        """Generate a summary of the call (placeholder for actual summarization)"""
        
        if not transcript_segments:
            return "No transcript available"
        
        # This is a placeholder - in production, you'd use a proper summarization service
        user_messages = [s.message for s in transcript_segments if s.speaker == 'user']
        agent_messages = [s.message for s in transcript_segments if s.speaker in ['agent', 'llm']]
        
        # Simple extraction-based summary
        key_topics = []
        
        # Look for common patterns
        if any('appointment' in msg.lower() for msg in user_messages + agent_messages):
            key_topics.append("appointment scheduling")
        
        if any('product' in msg.lower() or 'service' in msg.lower() for msg in user_messages + agent_messages):
            key_topics.append("product/service inquiry")
        
        if any('complaint' in msg.lower() or 'problem' in msg.lower() for msg in user_messages):
            key_topics.append("customer complaint")
        
        duration_text = f"Duration: {call.duration // 60}m {call.duration % 60}s" if call.duration else "Duration unknown"
        topics_text = f"Topics discussed: {', '.join(key_topics)}" if key_topics else "General conversation"
        
        return f"Call summary - {duration_text}. {topics_text}. Total interactions: {len(transcript_segments)}"
    
    @staticmethod
    def update_daily_summaries(db: Session, date: datetime = None):
        """Update daily summary statistics"""
        
        if not date:
            date = datetime.now().date()
        
        # Get all clients
        clients = db.query(Client).all()
        
        for client in clients:
            # Check if summary already exists
            existing_summary = db.query(CallSummary).filter(
                CallSummary.client_id == client.id,
                func.date(CallSummary.date) == date,
                CallSummary.hour.is_(None)  # Daily summary (not hourly)
            ).first()
            
            if existing_summary:
                continue  # Skip if already exists
            
            # Calculate metrics for the day
            day_start = datetime.combine(date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            day_calls = db.query(Call).filter(
                Call.client_id == client.id,
                Call.call_time >= day_start,
                Call.call_time < day_end
            ).all()
            
            if not day_calls:
                continue
            
            # Calculate summary metrics
            total_calls = len(day_calls)
            answered_calls = len([c for c in day_calls if c.status in ['completed', 'active']])
            completed_calls = len([c for c in day_calls if c.status == 'completed'])
            failed_calls = len([c for c in day_calls if c.status == 'failed'])
            
            leads_generated = len([c for c in day_calls if c.call_outcome in ['lead_generated', 'appointment_scheduled']])
            
            avg_duration = sum(c.duration for c in day_calls if c.duration) / len([c for c in day_calls if c.duration]) if any(c.duration for c in day_calls) else 0
            avg_quality = sum(c.quality_score for c in day_calls if c.quality_score) / len([c for c in day_calls if c.quality_score]) if any(c.quality_score for c in day_calls) else 0
            
            # Create summary
            summary = CallSummary(
                client_id=client.id,
                date=day_start,
                total_calls=total_calls,
                answered_calls=answered_calls,
                completed_calls=completed_calls,
                failed_calls=failed_calls,
                leads_generated=leads_generated,
                avg_call_duration=avg_duration,
                avg_quality_score=avg_quality
            )
            
            db.add(summary)
        
        db.commit()

class DataSyncService:
    """Service for syncing data between Redis and database"""
    
    def __init__(self, redis_service: RedisService):
        self.redis_service = redis_service
    
    async def sync_pending_calls(self):
        """Sync all pending calls from Redis to database"""
        
        if not await self.redis_service.connect():
            return
        
        try:
            # Get all room history keys
            keys = await self.redis_service.redis_client.keys("room_history:*")
            
            db = SessionLocal()
            synced_count = 0
            
            for key in keys:
                room_id = key.replace("room_history:", "")
                
                try:
                    call = await self.redis_service.sync_call_from_redis(room_id, db)
                    if call:
                        synced_count += 1
                except Exception as e:
                    print(f"Error syncing call {room_id}: {e}")
                    continue
            
            db.close()
            print(f"Synced {synced_count} calls from Redis")
            
        except Exception as e:
            print(f"Error in sync_pending_calls: {e}")
        finally:
            await self.redis_service.close()
    
    async def process_enhanced_metrics(self):
        """Process enhanced metrics from Redis"""
        
        if not await self.redis_service.connect():
            return
        
        try:
            # Get all enhanced metrics keys
            keys = await self.redis_service.redis_client.keys("enhanced_metrics:call:*")
            
            db = SessionLocal()
            processed_count = 0
            
            for key in keys:
                call_id = key.replace("enhanced_metrics:call:", "")
                
                try:
                    # Get metrics data
                    metrics_data = await self.redis_service.redis_client.get(key)
                    if not metrics_data:
                        continue
                    
                    metrics = json.loads(metrics_data)
                    
                    # Find corresponding call in database
                    call = db.query(Call).filter(Call.call_id == call_id).first()
                    if not call:
                        continue
                    
                    # Check if metrics already exist
                    existing_metrics = db.query(CallMetrics).filter(
                        CallMetrics.call_id == call.id
                    ).first()
                    
                    if existing_metrics:
                        # Update existing metrics
                        existing_metrics.llm_calls = len(metrics.get('llm_metrics', []))
                        existing_metrics.tts_calls = len(metrics.get('tts_metrics', []))
                        existing_metrics.asr_calls = len(metrics.get('asr_metrics', []))
                        existing_metrics.additional_metrics = metrics
                    else:
                        # Create new metrics
                        new_metrics = CallMetrics(
                            call_id=call.id,
                            llm_calls=len(metrics.get('llm_metrics', [])),
                            tts_calls=len(metrics.get('tts_metrics', [])),
                            asr_calls=len(metrics.get('asr_metrics', [])),
                            total_interactions=len(metrics.get('llm_metrics', [])) + len(metrics.get('tts_metrics', [])),
                            additional_metrics=metrics
                        )
                        db.add(new_metrics)
                    
                    processed_count += 1
                    
                except Exception as e:
                    print(f"Error processing metrics for {call_id}: {e}")
                    continue
            
            db.commit()
            db.close()
            print(f"Processed {processed_count} enhanced metrics")
            
        except Exception as e:
            print(f"Error in process_enhanced_metrics: {e}")
        finally:
            await self.redis_service.close()

# Background task functions
async def background_sync_task():
    """Background task to sync data from Redis"""
    
    redis_service = RedisService()
    sync_service = DataSyncService(redis_service)
    
    while True:
        try:
            print("Starting background sync...")
            await sync_service.sync_pending_calls()
            await sync_service.process_enhanced_metrics()
            
            # Update daily summaries
            db = SessionLocal()
            CallAnalyticsService.update_daily_summaries(db)
            db.close()
            
            print("Background sync completed")
            
        except Exception as e:
            print(f"Background sync error: {e}")
        
        # Wait 5 minutes before next sync
        await asyncio.sleep(300)

if __name__ == "__main__":
    # Test Redis connection
    async def test_redis():
        redis_service = RedisService()
        connected = await redis_service.connect()
        print(f"Redis connection: {'Success' if connected else 'Failed'}")
        
        if connected:
            # Test getting room history
            history = await redis_service.get_room_history("room1")
            print(f"Found {len(history)} messages in room1")
            await redis_service.close()
    
    asyncio.run(test_redis())