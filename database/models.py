"""
Database models for Legal Document Automation Platform.
All tables prefixed with 'document_generator_' for organization.
Uses existing Azure PostgreSQL database.
"""
import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class DocumentTemplate(Base):
    """
    Store document template metadata.

    Actual template JSON and prompt config JSON are stored in Azure Blob Storage.
    This table only tracks metadata and blob paths.
    """

    __tablename__ = "document_generator_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)

    # Azure Blob Storage paths (without container name)
    # Format: "templates/{template_id}/template.json"
    template_blob_path = Column(String(500), nullable=False)

    # Format: "templates/{template_id}/prompt_config.json"
    prompt_blob_path = Column(String(500), nullable=False)

    # Metadata
    version = Column(String(20), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Session(Base):
    """Track user conversation sessions."""

    __tablename__ = "document_generator_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Store template name for reference
    template_name = Column(String(255), nullable=False)

    # GPT-4o's execution plan (cached after initial analysis)
    # This is generated once per session and reused for performance
    execution_plan = Column(JSONB)

    # Track which questions have been answered
    # Format: ["contract_type", "employer_name", ...]
    answered_question_ids = Column(JSONB, default=list)

    # Current position in question sequence
    current_sequence_number = Column(Integer, default=0)

    # Data extracted from user answers
    collected_data = Column(JSONB, default=dict)

    # Status tracking
    status = Column(String(20), default="in_progress")  # in_progress, ready_for_generation, completed

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))

    # Relationships
    generated_documents = relationship("GeneratedDocument", back_populates="session")


class GeneratedDocument(Base):
    """Track generated documents."""
    
    __tablename__ = "document_generator_documents"
    
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("document_generator_sessions.session_id"), nullable=False)
    
    # File information
    blob_url = Column(String(500), nullable=False)
    file_format = Column(String(10), nullable=False)  # pdf or docx
    file_size_bytes = Column(Integer)
    
    # Metadata
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="generated_documents")
