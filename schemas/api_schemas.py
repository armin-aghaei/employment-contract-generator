"""API request/response schemas using Pydantic."""
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field


# Template schemas
class TemplateItem(BaseModel):
    """Template list item."""
    id: UUID
    name: str
    description: Optional[str] = None
    version: str
    is_active: bool

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """Response for listing templates."""
    templates: List[TemplateItem]


# Question and Progress schemas for Loveable frontend
class QuestionSchema(BaseModel):
    """Simple question format for Loveable frontend to render."""
    field_id: str = Field(..., description="Unique identifier for this question")
    label: str = Field(..., description="Question text to display")
    input_type: str = Field(..., description="Input type: text, select, date, number, email, tel, etc.")
    options: Optional[List[str]] = Field(None, description="Options for select/radio inputs")
    required: bool = Field(default=True, description="Whether this field is required")
    help_text: Optional[str] = Field(None, description="Helper text to display below the field")
    placeholder: Optional[str] = Field(None, description="Placeholder text for the input")
    current_value: Optional[Any] = Field(None, description="Current value if already answered")
    suggestion: Optional[str] = Field(None, description="AI-powered smart suggestion")
    validation_pattern: Optional[str] = Field(None, description="Regex pattern for validation")


class ProgressSchema(BaseModel):
    """Progress tracking information."""
    current_step: int = Field(..., description="Current step number")
    total_steps: int = Field(..., description="Total number of steps")
    percent_complete: float = Field(..., description="Percentage complete (0-100)")
    phase_name: Optional[str] = Field(None, description="Name of current phase/section")


class ValidationError(BaseModel):
    """Individual validation error."""
    field: str = Field(..., description="Field ID that failed validation")
    message: str = Field(..., description="Error message to display")
    severity: str = Field(default="error", description="error or warning")


# Session schemas
class StartSessionRequest(BaseModel):
    """Request to start a new document generation session."""
    template_name: str = Field(..., description="Name of the document template to use")


class StartSessionResponse(BaseModel):
    """Response when starting a new session."""
    session_id: UUID
    template_name: str
    welcome_message: str = Field(..., description="Welcome message for the user")
    current_questions: List[QuestionSchema] = Field(..., description="First set of questions to display")
    progress: ProgressSchema = Field(..., description="Progress information")
    status: str = "in_progress"
    created_at: datetime


class SendMessageRequest(BaseModel):
    """Request to send a message in the conversation."""
    message: str = Field(..., description="User's message to the AI")


class SendMessageResponse(BaseModel):
    """Response from AI after user message."""
    session_id: UUID
    ai_response: str = Field(..., description="AI's response to the user")
    status: str = Field(..., description="Session status: in_progress, ready_for_generation, completed")
    is_complete: bool = Field(..., description="Whether data collection is complete")
    collected_data: Dict[str, Any] = Field(default_factory=dict, description="Data collected so far")


class SubmitAnswersRequest(BaseModel):
    """Request to submit answers to questions."""
    answers: Dict[str, Any] = Field(..., description="Map of field_id to answer value")


class SubmitAnswersResponse(BaseModel):
    """Response after submitting answers."""
    session_id: UUID
    validation_passed: bool = Field(..., description="Whether all answers passed validation")
    errors: List[ValidationError] = Field(default_factory=list, description="Validation errors if any")
    warnings: List[ValidationError] = Field(default_factory=list, description="Warnings (non-blocking)")
    next_questions: List[QuestionSchema] = Field(default_factory=list, description="Next questions to display")
    progress: ProgressSchema = Field(..., description="Updated progress information")
    is_complete: bool = Field(..., description="Whether all required data has been collected")
    status: str = Field(..., description="Session status")


class SessionStateResponse(BaseModel):
    """Current state of a session."""
    session_id: UUID
    template_id: UUID
    template_name: str
    status: str
    messages: List[Dict[str, str]] = Field(..., description="Conversation history")
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


# Document generation schemas
class GenerateDocumentRequest(BaseModel):
    """Request to generate a document."""
    format: str = Field(..., description="Document format: 'pdf' or 'docx'")


class GenerateDocumentResponse(BaseModel):
    """Response after generating document."""
    document_id: UUID
    session_id: UUID
    blob_url: str = Field(..., description="URL to download the generated document")
    file_format: str
    file_size_bytes: Optional[int] = None
    generated_at: datetime


# Error schemas
class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    status_code: int = 400
