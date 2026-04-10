"""
Pydantic v2 schemas for all API request and response bodies.
These are the "contracts" between the frontend and backend.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
import uuid


# ── Enums ─────────────────────────────────────────────────────────────────────

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED  = "failed"
    SKIPPED = "skipped"

class AgentName(str, Enum):
    PLANNER  = "PlannerAgent"
    EXECUTOR = "ExecutorAgent"
    DEBUGGER = "DebugAgent"
    REVIEWER = "ReviewerAgent"


# ── Agent Communication Types ─────────────────────────────────────────────────

class AgentStep(BaseModel):
    """
    Represents one agent's work within a multi-step task.
    Streamed to the frontend as SSE events so users see real-time progress.
    """
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: AgentName
    step_number: int
    input: str
    output: str
    status: AgentStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class PlanStep(BaseModel):
    """A single planned step produced by the PlannerAgent."""
    step_number: int
    description: str
    agent: AgentName = AgentName.EXECUTOR
    expected_output: str


# ── Task (Agent Orchestration) API ────────────────────────────────────────────

class TaskRequest(BaseModel):
    """Request body for POST /api/agents/run"""
    task: str = Field(..., min_length=3, max_length=4000, description="The task to execute")
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    context: dict = Field(default_factory=dict, description="Optional additional context")
    stream: bool = Field(default=True, description="Whether to stream SSE events")


class TaskResponse(BaseModel):
    """Response body for non-streaming task execution."""
    task_id: str
    session_id: str
    status: AgentStatus
    task: str
    plan: List[PlanStep] = []
    steps: List[AgentStep] = []
    final_output: Optional[str] = None
    error: Optional[str] = None
    total_duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── RAG / Query API ───────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Request body for POST /api/query"""
    query: str = Field(..., min_length=3, max_length=2000)
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str = Field(default="default", description="Document namespace/collection")
    top_k: int = Field(default=5, ge=1, le=20)
    stream: bool = Field(default=False)


class DocumentSource(BaseModel):
    """A retrieved document chunk, returned alongside the LLM's answer."""
    filename: str
    page: Optional[int] = None
    chunk_id: str
    content: str
    score: float  # Cosine similarity score (0.0 to 1.0)


class QueryResponse(BaseModel):
    """Response body for RAG queries."""
    answer: str
    sources: List[DocumentSource]
    session_id: str
    namespace: str
    query: str
    model_used: str


# ── File Upload API ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response body for POST /api/upload"""
    filename: str
    file_id: str
    namespace: str
    chunks_created: int
    pages_processed: int
    message: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentInfo(BaseModel):
    """Info about an uploaded document."""
    file_id: str
    filename: str
    namespace: str
    chunk_count: int
    pages: int
    size_bytes: int
    uploaded_at: datetime


# ── Chat API ──────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Request body for POST /api/chat"""
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    mode: str = Field(default="chat", description="'chat' | 'rag' | 'agent'")
    namespace: str = Field(default="default")


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    message: str
    session_id: str
    mode: str


# ── Health / System ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    llm_provider: str
    vector_db: str
    embedding_provider: str
