"""
SQLAlchemy ORM Models.
Maps Python classes to database tables.

Tables:
  - documents: Tracks uploaded PDFs and their ingestion status
  - tasks:     Records multi-agent task executions
  - chat_logs: Persists chat history per session
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Boolean, JSON
from db.database import Base


class DocumentRecord(Base):
    """One row per uploaded PDF/document."""
    __tablename__ = "documents"

    id          = Column(String, primary_key=True)   # UUID
    filename    = Column(String, nullable=False)
    namespace   = Column(String, default="default")
    file_path   = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    page_count  = Column(Integer, default=0)
    size_bytes  = Column(Integer, default=0)
    status      = Column(String, default="pending")  # pending | processing | ready | failed
    error       = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at= Column(DateTime, nullable=True)


class TaskRecord(Base):
    """One row per multi-agent task execution."""
    __tablename__ = "tasks"

    id           = Column(String, primary_key=True)   # UUID
    session_id   = Column(String, nullable=False, index=True)
    task_text    = Column(Text, nullable=False)
    status       = Column(String, default="pending")  # pending | running | success | failed
    step_count   = Column(Integer, default=0)
    final_output = Column(Text, nullable=True)
    error        = Column(Text, nullable=True)
    duration_ms  = Column(Integer, nullable=True)
    plan_json    = Column(JSON, nullable=True)        # Stores the PlanStep list
    steps_json   = Column(JSON, nullable=True)        # Stores AgentStep list
    created_at   = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class ChatLog(Base):
    """Persistent chat history — one row per message."""
    __tablename__ = "chat_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    role       = Column(String, nullable=False)   # "user" | "assistant"
    content    = Column(Text, nullable=False)
    mode       = Column(String, default="chat")   # "chat" | "rag" | "agent"
    created_at = Column(DateTime, default=datetime.utcnow)
