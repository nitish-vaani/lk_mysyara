import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Index, UniqueConstraint
import uuid

# Database configuration - supports both PostgreSQL and SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./call_center.db")

# Configure engine based on database type
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL)
else:
    # SQLite configuration
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Client(Base):
    """Client/Organization table"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    client_settings = Column(JSON)  # Store client-specific configurations
    
    # Relationships
    calls = relationship("Call", back_populates="client")
    agents = relationship("Agent", back_populates="client")

class Agent(Base):
    """Agent information table"""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    agent_type = Column(String(50))  # 'ai', 'human', 'hybrid'
    phone_number = Column(String(20))  # For human agents
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    agent_settings = Column(JSON)  # Agent-specific settings
    
    # Relationships
    client = relationship("Client", back_populates="agents")
    calls = relationship("Call", back_populates="agent")

class Call(Base):
    """Main calls table - designed for extensibility"""
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    
    # Call identifiers
    call_id = Column(String(255), unique=True, index=True)  # Unique call identifier
    room_name = Column(String(255), index=True)
    
    # Call details
    phone_number = Column(String(20), index=True)
    caller_name = Column(String(255))
    
    # Timestamps
    call_time = Column(DateTime, default=datetime.utcnow, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration = Column(Integer)  # Duration in seconds
    
    # Call status and outcome
    status = Column(String(50), index=True)  # 'initiated', 'active', 'completed', 'failed', 'timeout'
    call_outcome = Column(String(100))  # 'answered', 'busy', 'voicemail', 'rejected', 'lead_generated'
    
    # Content
    transcript = Column(Text)
    summary = Column(Text)
    
    # Extensible fields
    call_metadata = Column(JSON)  # Store any additional call data
    custom_fields = Column(JSON)  # Client-specific custom fields
    
    # AI/Analytics fields
    sentiment_score = Column(Float)
    intent_classification = Column(String(100))
    entities_extracted = Column(JSON)
    
    # Performance metrics
    response_time = Column(Float)
    quality_score = Column(Float)

    # Enhanced sync tracking fields (ADD these)
    synced_from_redis = Column(Boolean, default=False)
    last_sync_time = Column(DateTime)
    sync_source = Column(String(50))  # 'auto_sync', 'manual_sync', 'webhook'
    
    
    # Relationships
    client = relationship("Client", back_populates="calls")
    agent = relationship("Agent", back_populates="calls")
    metrics = relationship("CallMetrics", back_populates="call", cascade="all, delete-orphan")
    metrics_detail = relationship("CallMetricsDetail", back_populates="call", cascade="all, delete-orphan")
    transcripts = relationship("TranscriptSegment", back_populates="call", cascade="all, delete-orphan")
    call = relationship("Call", back_populates="metrics_detail")

class SyncStatus(Base):
    """Track sync operations between Redis and PostgreSQL - ADD THIS TABLE"""
    __tablename__ = "sync_status"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Sync details
    sync_type = Column(String(50), nullable=False)  # 'transcript', 'metrics', 'post_call'
    room_id = Column(String(255), nullable=False, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"))
    
    # Status tracking
    status = Column(String(50), nullable=False)  # 'pending', 'in_progress', 'completed', 'failed'
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    
    # Error tracking
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    error_details = Column(JSON)
    
    # Data tracking
    records_processed = Column(Integer, default=0)
    processing_time_ms = Column(Integer)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_sync_type_status', 'sync_type', 'status'),
        Index('idx_room_id_type', 'room_id', 'sync_type'),
    )


class CallMetrics(Base):
    """Detailed call metrics table"""
    __tablename__ = "call_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # LLM metrics
    llm_calls = Column(Integer, default=0)
    avg_ttft = Column(Float)  # Time to first token
    total_tokens_in = Column(Integer, default=0)
    total_tokens_out = Column(Integer, default=0)
    
    # TTS metrics
    tts_calls = Column(Integer, default=0)
    avg_tts_ttfb = Column(Float)  # Time to first byte
    total_audio_duration = Column(Float)
    
    # ASR metrics
    asr_calls = Column(Integer, default=0)
    avg_asr_latency = Column(Float)
    total_words_processed = Column(Integer, default=0)
    
    # User experience metrics
    avg_user_latency = Column(Float)
    total_interactions = Column(Integer, default=0)
    
    # System metrics during call
    cpu_usage = Column(JSON)  # Store CPU usage over time
    memory_usage = Column(JSON)  # Store memory usage over time

    # Enhanced LLM metrics (ADD these)
    min_ttft = Column(Float)
    max_ttft = Column(Float)
    avg_tokens_per_call = Column(Float)
    
    # Enhanced TTS metrics (ADD these)  
    min_tts_ttfb = Column(Float)
    max_tts_ttfb = Column(Float)
    total_characters_processed = Column(Integer, default=0)
    
    # Enhanced ASR metrics (ADD these)
    min_asr_latency = Column(Float)
    max_asr_latency = Column(Float)
    avg_words_per_utterance = Column(Float)
    
    # EOU metrics (ADD these)
    eou_events = Column(Integer, default=0)
    avg_eou_delay = Column(Float)
    min_eou_delay = Column(Float)
    max_eou_delay = Column(Float)
    
    # Enhanced user experience metrics (ADD these)
    min_user_latency = Column(Float)
    max_user_latency = Column(Float)
    user_wait_time = Column(Float)
    
    # Performance scores (ADD these)
    efficiency_score = Column(Float)  # Overall efficiency (0-100)
    performance_grade = Column(String(5))  # A, B, C, D, F
    
    # Timestamps (ADD these)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
    # Extensible metrics
    additional_metrics = Column(JSON)
    
    # Relationship
    call = relationship("Call", back_populates="metrics")

class TranscriptSegment(Base):
    """Individual transcript segments for detailed analysis"""
    __tablename__ = "transcript_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # Segment details
    history_id = Column(Integer, index=True)  # From Redis data
    timestamp = Column(DateTime, index=True)
    speaker = Column(String(50), index=True)  # 'user', 'agent', 'llm', etc.
    message = Column(Text)
    
    # Analysis fields
    sentiment = Column(String(50))
    confidence = Column(Float)
    intent = Column(String(100))
    
    # Timing metrics
    response_time = Column(Float)  # Time taken to generate this response
    
    # Extensible fields
    segment_metadata = Column(JSON)
    
    # Relationship
    call = relationship("Call", back_populates="transcripts")

class CallSummary(Base):
    """Daily/hourly call summaries for quick dashboard queries"""
    __tablename__ = "call_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    
    # Time period
    date = Column(DateTime, index=True)
    hour = Column(Integer)  # 0-23 for hourly summaries, null for daily
    
    # Summary metrics
    total_calls = Column(Integer, default=0)
    answered_calls = Column(Integer, default=0)
    completed_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    
    # Outcome metrics
    leads_generated = Column(Integer, default=0)
    appointments_scheduled = Column(Integer, default=0)
    
    # Performance metrics
    avg_call_duration = Column(Float)
    avg_response_time = Column(Float)
    avg_quality_score = Column(Float)
    
    # Revenue metrics (if applicable)
    total_revenue = Column(Float)
    avg_revenue_per_call = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class CallMetricsDetail(Base):
    """Individual metric events for detailed analysis - ADD THIS TABLE"""
    __tablename__ = "call_metrics_detail"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # Event details
    metric_type = Column(String(20), nullable=False, index=True)  # 'llm', 'tts', 'asr', 'eou', 'user_latency'
    event_timestamp = Column(DateTime, nullable=False, index=True)
    sequence_number = Column(Integer)  # Order within the call
    
    # Common metrics
    duration_ms = Column(Float)  # Duration of the event in milliseconds
    latency_ms = Column(Float)   # Latency for the event
    
    # Type-specific metrics stored as JSON
    event_details = Column(JSON)  # Raw event data
    # Examples:
    # LLM: {"ttft": 0.5, "tokens_in": 10, "tokens_out": 15}
    # TTS: {"ttfb": 0.3, "duration": 2.1, "characters": 150}
    # ASR: {"duration": 1.2, "words": 5, "confidence": 0.95}
    
    # Quality indicators
    success = Column(Boolean, default=True)
    error_code = Column(String(50))
    error_message = Column(Text)
    
    # Performance indicators
    performance_score = Column(Float)  # 0-100 score for this specific event
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_call_metric_type', 'call_id', 'metric_type'),
        Index('idx_event_timestamp', 'event_timestamp'),
        Index('idx_metric_type_timestamp', 'metric_type', 'event_timestamp'),
    )



# Database initialization functions
def create_database():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_default_data():
    """Initialize with default client and agent data"""
    db = SessionLocal()
    try:
        # Check if default client exists
        default_client = db.query(Client).filter(Client.name == "Default Client").first()
        if not default_client:
            default_client = Client(
                name="Default Client",
                client_settings={"timezone": "UTC", "currency": "USD"}
            )
            db.add(default_client)
            db.commit()
            db.refresh(default_client)
        
        # Check if default AI agent exists
        default_agent = db.query(Agent).filter(
            Agent.client_id == default_client.id,
            Agent.name == "Default AI Agent"
        ).first()
        if not default_agent:
            default_agent = Agent(
                client_id=default_client.id,
                name="Default AI Agent",
                agent_type="ai",
                agent_settings={"model": "gpt-4", "temperature": 0.7}
            )
            db.add(default_agent)
            db.commit()
            
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating database tables...")
    create_database()
    print("Initializing default data...")
    init_default_data()
    print("Database setup complete!")