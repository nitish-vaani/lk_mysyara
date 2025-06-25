# backend/services.py - Service layer for Redis integration and analytics

import redis
import json
import asyncio
import aioredis
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from models import CallMetricsDetail, SyncStatus
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

class EnhancedRedisService:
    """Enhanced Redis service for multi-DB operations - ADD THIS CLASS"""
    
    def __init__(self):
        self.transcript_redis = None
        self.metrics_redis = None
        self._connected = False
        
    async def initialize(self) -> bool:
        """Initialize Redis connections"""
        try:
            from config import settings  # Use your existing settings
            
            # Connect to transcript database (DB 0)
            self.transcript_redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB_TRANSCRIPTS,
                password=getattr(settings, 'REDIS_PASSWORD', None),
                decode_responses=True,
                socket_connect_timeout=5
            )
            
            # Connect to metrics database (DB 15)
            self.metrics_redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB_METRICS,
                password=getattr(settings, 'REDIS_PASSWORD', None),
                decode_responses=True,
                socket_connect_timeout=5
            )
            
            # Test connections
            await self.transcript_redis.ping()
            await self.metrics_redis.ping()
            
            self._connected = True
            logger.info(f"✅ Enhanced Redis connected: {settings.REDIS_HOST}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced Redis connection failed: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def get_room_history(self, room_id: str) -> List[Dict[str, Any]]:
        """Get transcript history for a room"""
        try:
            history_key = f"room_history:{room_id}"
            messages = await self.transcript_redis.lrange(history_key, 0, -1)
            
            parsed_messages = []
            for msg in messages:
                try:
                    parsed = json.loads(msg)
                    parsed_messages.append(parsed)
                except json.JSONDecodeError:
                    continue
            
            parsed_messages.sort(key=lambda x: x.get('timestamp', 0))
            return parsed_messages
            
        except Exception as e:
            logger.error(f"❌ Error getting room history: {e}")
            return []
    
    async def get_enhanced_metrics(self, call_id: str) -> Dict[str, Any]:
        """Get enhanced metrics for a call"""
        try:
            metrics_key = f"enhanced_metrics:call:{call_id}"
            metrics_data = await self.metrics_redis.get(metrics_key)
            
            if metrics_data:
                return json.loads(metrics_data)
            return {}
                
        except Exception as e:
            logger.error(f"❌ Error getting metrics: {e}")
            return {}
    
    async def get_sync_candidates(self) -> List[str]:
        """Get all room IDs that need syncing"""
        try:
            # Get transcript room IDs
            transcript_keys = await self.transcript_redis.keys("room_history:*")
            transcript_rooms = {key.replace("room_history:", "") for key in transcript_keys}
            
            # Get metrics call IDs
            metrics_keys = await self.metrics_redis.keys("enhanced_metrics:call:*")
            metrics_calls = {key.replace("enhanced_metrics:call:", "") for key in metrics_keys}
            
            # Return union of both
            return list(transcript_rooms.union(metrics_calls))
            
        except Exception as e:
            logger.error(f"❌ Error getting sync candidates: {e}")
            return []
    
    async def publish_post_call_event(self, room_id: str, status: str, metadata: Dict = None) -> bool:
        """Publish post-call event"""
        try:
            from config import settings
            event_data = {
                "room_id": room_id,
                "action": "call_ended",
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            await self.transcript_redis.publish(settings.POST_CALL_QUEUE_NAME, json.dumps(event_data))
            logger.info(f"📤 Published post-call event for {room_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error publishing post-call event: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup connections"""
        try:
            if self.transcript_redis:
                await self.transcript_redis.close()
            if self.metrics_redis:
                await self.metrics_redis.close()
            self._connected = False
        except Exception as e:
            logger.error(f"❌ Redis cleanup error: {e}")

@dataclass
class SyncResult:
    """Result of a sync operation - ADD THIS CLASS"""
    success: bool
    room_id: str
    records_created: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class EnhancedSyncService:
    """Enhanced sync service for Redis to PostgreSQL - ADD THIS CLASS"""
    
    def __init__(self, enhanced_redis: EnhancedRedisService):
        self.enhanced_redis = enhanced_redis
        self.default_client_id = None
        
    async def initialize(self) -> bool:
        """Initialize sync service"""
        try:
            from config import settings
            
            # Get default client ID
            db = SessionLocal()
            try:
                from models import Client  # Use your existing Client model
                client = db.query(Client).filter(Client.name.like(f"%{settings.CLIENT_ID}%")).first()
                if client:
                    self.default_client_id = client.id
                else:
                    # Create default client if not exists
                    client = Client(name=settings.CLIENT_NAME)
                    db.add(client)
                    db.commit()
                    self.default_client_id = client.id
            finally:
                db.close()
            
            logger.info("✅ Enhanced sync service initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Sync service initialization failed: {e}")
            return False
    
    async def sync_all_data(self) -> Dict[str, Any]:
        """Sync all pending data from Redis to PostgreSQL"""
        try:
            candidates = await self.enhanced_redis.get_sync_candidates()
            
            if not candidates:
                return {"status": "success", "message": "No data to sync", "total": 0}
            
            logger.info(f"🔄 Syncing {len(candidates)} calls...")
            
            successful = 0
            total_records = 0
            
            for room_id in candidates:
                try:
                    result = await self.sync_room_data(room_id)
                    if result.success:
                        successful += 1
                        total_records += result.records_created
                        logger.debug(f"✅ Synced {room_id}: {result.records_created} records")
                    else:
                        logger.warning(f"❌ Failed {room_id}: {result.errors}")
                        
                except Exception as e:
                    logger.error(f"❌ Exception syncing {room_id}: {e}")
                
                await asyncio.sleep(0.1)  # Small delay
            
            logger.info(f"✅ Sync completed: {successful}/{len(candidates)} successful, {total_records} records")
            
            return {
                "status": "success",
                "total_candidates": len(candidates),
                "successful": successful,
                "failed": len(candidates) - successful,
                "records_created": total_records
            }
            
        except Exception as e:
            logger.error(f"❌ Sync failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def sync_room_data(self, room_id: str) -> SyncResult:
        """Sync data for a specific room"""
        try:
            # Get data from Redis
            transcript_data = await self.enhanced_redis.get_room_history(room_id)
            metrics_data = await self.enhanced_redis.get_enhanced_metrics(room_id)
            
            if not transcript_data and not metrics_data:
                return SyncResult(success=True, room_id=room_id, errors=["No data in Redis"])
            
            db = SessionLocal()
            try:
                from models import Call, TranscriptSegment, CallMetrics  # Use your existing models
                
                # Check if call exists
                call = db.query(Call).filter(Call.call_id == room_id).first()
                
                records_created = 0
                
                if not call:
                    # Create new call
                    call = Call(
                        call_id=room_id,
                        room_name=room_id,
                        client_id=self.default_client_id,
                        status="active",
                        call_time=datetime.utcnow(),
                        synced_from_redis=False
                    )
                    
                    # Extract info from data if available
                    if transcript_data:
                        first_msg = min(transcript_data, key=lambda x: x.get('timestamp', 0))
                        call.call_time = datetime.fromtimestamp(first_msg.get('timestamp', 0) / 1000)
                    
                    if metrics_data:
                        call.phone_number = metrics_data.get("phone_number", "")
                        call.caller_name = metrics_data.get("caller_name", "")
                        if metrics_data.get("status") in ["completed", "failed"]:
                            call.status = metrics_data["status"]
                    
                    db.add(call)
                    db.flush()
                    records_created += 1
                
                # Sync transcript data
                if transcript_data:
                    for msg in transcript_data:
                        existing = db.query(TranscriptSegment).filter(
                            TranscriptSegment.call_id == call.id,
                            TranscriptSegment.history_id == msg.get('history_id')
                        ).first()
                        
                        if not existing:
                            segment = TranscriptSegment(
                                call_id=call.id,
                                history_id=msg.get('history_id'),
                                timestamp=datetime.fromtimestamp(msg.get('timestamp', 0) / 1000),
                                speaker=msg.get('speaker', 'unknown'),
                                message=msg.get('message', '')
                            )
                            db.add(segment)
                            records_created += 1
                
                # Sync metrics data
                if metrics_data:
                    existing_metrics = db.query(CallMetrics).filter(CallMetrics.call_id == call.id).first()
                    
                    if not existing_metrics:
                        # Calculate aggregated metrics
                        llm_metrics = metrics_data.get('llm_metrics', [])
                        tts_metrics = metrics_data.get('tts_metrics', [])
                        
                        avg_ttft = 0
                        if llm_metrics:
                            ttfts = [m.get('ttft', 0) for m in llm_metrics if m.get('ttft', 0) > 0]
                            avg_ttft = sum(ttfts) / len(ttfts) if ttfts else 0
                        
                        metrics = CallMetrics(
                            call_id=call.id,
                            llm_calls=len(llm_metrics),
                            avg_ttft=avg_ttft,
                            tts_calls=len(tts_metrics),
                            total_interactions=len(llm_metrics) + len(tts_metrics),
                            additional_metrics=metrics_data
                        )
                        db.add(metrics)
                        records_created += 1
                    
                    # Create detailed metrics
                    for llm_metric in metrics_data.get('llm_metrics', []):
                        detail = CallMetricsDetail(
                            call_id=call.id,
                            metric_type="llm",
                            event_timestamp=datetime.fromtimestamp(llm_metric.get('timestamp', 0)),
                            duration_ms=llm_metric.get('ttft', 0) * 1000,
                            event_details=llm_metric,
                            success=True
                        )
                        db.add(detail)
                        records_created += 1
                
                # Mark as synced
                call.synced_from_redis = True
                call.last_sync_time = datetime.utcnow()
                
                db.commit()
                return SyncResult(success=True, room_id=room_id, records_created=records_created)
                
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()
                
        except Exception as e:
            return SyncResult(success=False, room_id=room_id, errors=[str(e)])

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

# Global enhanced services
enhanced_redis_service = None
enhanced_sync_service = None

async def enhanced_background_sync_task():
    """Enhanced background task - ADD THIS or REPLACE your existing background_sync_task"""
    global enhanced_redis_service, enhanced_sync_service
    
    # Initialize services
    enhanced_redis_service = EnhancedRedisService()
    if not await enhanced_redis_service.initialize():
        logger.error("❌ Failed to initialize enhanced Redis service")
        return
    
    enhanced_sync_service = EnhancedSyncService(enhanced_redis_service)
    if not await enhanced_sync_service.initialize():
        logger.error("❌ Failed to initialize enhanced sync service")
        return
    
    logger.info("🚀 Enhanced background sync started")
    
    while True:
        try:
            from config import settings
            
            # Run sync
            result = await enhanced_sync_service.sync_all_data()
            
            if result["status"] == "success":
                logger.info(f"✅ Enhanced sync: {result.get('records_created', 0)} records")
            else:
                logger.warning(f"⚠️ Enhanced sync issues: {result}")
            
        except Exception as e:
            logger.error(f"❌ Enhanced sync error: {e}")
        
        # Wait for next sync
        await asyncio.sleep(settings.sync_interval_seconds)

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