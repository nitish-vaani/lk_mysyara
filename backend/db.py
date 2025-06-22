import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use AWS RDS/PostgreSQL connection string from environment or config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://username:password@host:port/dbname")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Call(Base):
    __tablename__ = "calls"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, index=True)
    agent_name = Column(String)
    call_time = Column(DateTime)
    duration = Column(Integer)
    status = Column(String)
    transcript = Column(String)
    summary = Column(String)

# To create tables: Base.metadata.create_all(bind=engine)
