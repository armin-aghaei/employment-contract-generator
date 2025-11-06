"""
Legal Document Automation Platform - Main Application

A document-agnostic platform that uses Azure OpenAI GPT-4o to generate
customized legal documents through conversational AI.

Version: 1.0.0
"""
import os
from datetime import datetime
from uuid import UUID
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DBSession

from database import DatabaseClient, get_db
from database.models import DocumentTemplate, Session, GeneratedDocument
from schemas import (
    StartSessionRequest,
    StartSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionStateResponse,
    GenerateDocumentRequest,
    GenerateDocumentResponse,
    TemplateListResponse,
    TemplateItem,
    ErrorResponse,
    QuestionSchema,
    ProgressSchema,
    SubmitAnswersRequest,
    SubmitAnswersResponse,
    ValidationError
)
from services import AIOrchestrator, DocumentGenerator, TemplateService, ConversationFlowEngine

# Initialize FastAPI app
app = FastAPI(
    title="Legal Document Automation Platform",
    description="AI-powered legal document generation through conversational interface",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
ai_orchestrator = AIOrchestrator()
document_generator = DocumentGenerator()
template_service = TemplateService()
conversation_engine = ConversationFlowEngine()


@app.on_event("startup")
async def startup_event():
    """Create database tables on startup."""
    DatabaseClient.create_tables()


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": "Legal Document Automation Platform",
        "version": "1.0.0",
        "description": "AI-powered legal document generation",
        "endpoints": {
            "templates": "/templates",
            "start_session": "/sessions/start",
            "submit_answers": "/sessions/{session_id}/submit",
            "send_message": "/sessions/{session_id}/message",
            "session_state": "/sessions/{session_id}",
            "generate_document": "/sessions/{session_id}/generate",
            "docs": "/docs"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "legal-document-automation"
    }


# ==================== Template Endpoints ====================

@app.get("/templates", response_model=TemplateListResponse, tags=["Templates"])
async def list_templates(db: DBSession = Depends(get_db)):
    """
    List all active document templates.

    Returns list of available templates that users can choose from.
    """
    templates = db.query(DocumentTemplate).filter(
        DocumentTemplate.is_active == True
    ).all()

    return TemplateListResponse(
        templates=[
            TemplateItem(
                id=t.id,
                name=t.name,
                description=t.description,
                version=t.version,
                is_active=t.is_active
            )
            for t in templates
        ]
    )


@app.get("/templates/{template_id}", response_model=TemplateItem, tags=["Templates"])
async def get_template(template_id: UUID, db: DBSession = Depends(get_db)):
    """Get details of a specific template."""
    template = db.query(DocumentTemplate).filter(
        DocumentTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )

    return TemplateItem(
        id=template.id,
        name=template.name,
        description=template.description,
        version=template.version,
        is_active=template.is_active
    )


# ==================== Session Endpoints ====================

@app.post("/sessions/start", response_model=StartSessionResponse, tags=["Sessions"])
async def start_session(
    request: StartSessionRequest,
    db: DBSession = Depends(get_db)
):
    """
    Start a new document generation session.

    This creates a new conversation session with the AI for the specified template.
    GPT-4o analyzes the prompt configuration and generates the first questions.

    Templates are loaded from Azure Blob Storage.
    """
    # Get template metadata from database
    template = db.query(DocumentTemplate).filter(
        DocumentTemplate.name == request.template_name,
        DocumentTemplate.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{request.template_name}' not found or inactive"
        )

    # Load template and prompt config from Azure Blob Storage
    try:
        template_json, prompt_config_json = template_service.load_template_and_prompt(
            template_blob_path=template.template_blob_path,
            prompt_blob_path=template.prompt_blob_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load template from blob storage: {str(e)}"
        )

    # Use GPT-4o to analyze the prompt configuration and create execution plan
    try:
        execution_plan = conversation_engine.analyze_prompt_config(
            prompt_config_json=prompt_config_json,
            template_json=template_json
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze prompt configuration: {str(e)}"
        )

    # Get first questions from execution plan
    try:
        first_questions = conversation_engine.get_first_questions(
            execution_plan=execution_plan,
            num_questions=1
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get first questions: {str(e)}"
        )

    # Calculate initial progress
    progress = conversation_engine.calculate_progress(
        execution_plan=execution_plan,
        answered_question_ids=[],
        current_question=first_questions[0] if first_questions else None
    )

    # Create session in database
    session = Session(
        template_name=template.name,
        execution_plan=execution_plan,
        answered_question_ids=[],
        current_sequence_number=0,
        collected_data={},
        status="in_progress"
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return StartSessionResponse(
        session_id=session.session_id,
        template_name=template.name,
        welcome_message=execution_plan.get("welcome_message", "Let's get started with your document."),
        current_questions=first_questions,
        progress=ProgressSchema(**progress),
        status=session.status,
        created_at=session.created_at
    )


@app.post("/sessions/{session_id}/submit", response_model=SubmitAnswersResponse, tags=["Sessions"])
async def submit_answers(
    session_id: UUID,
    request: SubmitAnswersRequest,
    db: DBSession = Depends(get_db)
):
    """
    Submit answers to questions in the conversation.

    The AI will validate the answers, store the data, and return the next questions.
    This endpoint replaces the old message-based conversation flow with a structured
    question-answer flow that's easier for the Loveable frontend to render.
    """
    # Get session
    session = db.query(Session).filter(
        Session.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is already completed"
        )

    if not session.execution_plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session execution plan not found. Please start a new session."
        )

    # Get current questions being answered (for validation context)
    # These are the questions that were shown to the user in the current step
    try:
        current_questions = conversation_engine.get_next_questions(
            execution_plan=session.execution_plan,
            answered_question_ids=session.answered_question_ids,
            collected_data=session.collected_data,
            num_questions=1
        )
    except Exception as e:
        # Fallback: try to get questions from answer keys
        current_questions = []
        for field_id in request.answers.keys():
            for q in session.execution_plan.get("question_sequence", []):
                if q.get("question_id") == field_id:
                    current_questions.append(q)
                    break

    # Validate the submitted answers using GPT-4o
    try:
        validation_result = conversation_engine.validate_answers(
            execution_plan=session.execution_plan,
            answers=request.answers,
            collected_data=session.collected_data,
            current_questions=current_questions
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )

    # If validation failed, return errors without saving
    if not validation_result.get("is_valid", False):
        try:
            errors = [
                ValidationError(**error)
                for error in validation_result.get("errors", [])
            ]
            warnings = [
                ValidationError(**warning)
                for warning in validation_result.get("warnings", [])
            ]
        except Exception as e:
            # Log the validation result that failed to parse
            print(f"[ERROR] Failed to create ValidationError objects: {str(e)}")
            print(f"[ERROR] Validation result: {validation_result}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse validation errors: {str(e)}"
            )

        # Calculate current progress (no change)
        progress = conversation_engine.calculate_progress(
            execution_plan=session.execution_plan,
            answered_question_ids=session.answered_question_ids
        )

        return SubmitAnswersResponse(
            session_id=session.session_id,
            validation_passed=False,
            errors=errors,
            warnings=warnings,
            next_questions=[],
            progress=ProgressSchema(**progress),
            is_complete=False,
            status=session.status
        )

    # Validation passed - update session with new data
    session.collected_data.update(request.answers)

    # Track which questions were answered
    answered_field_ids = list(request.answers.keys())
    session.answered_question_ids.extend(answered_field_ids)

    # Get next questions
    try:
        next_questions = conversation_engine.get_next_questions(
            execution_plan=session.execution_plan,
            answered_question_ids=session.answered_question_ids,
            collected_data=session.collected_data,
            num_questions=1
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get next questions: {str(e)}"
        )

    # Add smart suggestions to questions if available
    for question in next_questions:
        try:
            suggestion = conversation_engine.get_smart_suggestion(
                question=question,
                collected_data=session.collected_data
            )
            if suggestion:
                question["suggestion"] = suggestion
        except Exception:
            pass  # Suggestions are optional, continue without them

    # Check if conversation is complete
    is_complete = conversation_engine.is_complete(
        execution_plan=session.execution_plan,
        answered_question_ids=session.answered_question_ids
    )

    # Update session status if complete
    if is_complete:
        session.status = "ready_for_generation"

    # Calculate progress
    progress = conversation_engine.calculate_progress(
        execution_plan=session.execution_plan,
        answered_question_ids=session.answered_question_ids,
        current_question=next_questions[0] if next_questions else None
    )

    # Commit changes to database
    db.commit()

    # Get warnings (non-blocking issues)
    warnings = [
        ValidationError(**warning)
        for warning in validation_result.get("warnings", [])
    ]

    return SubmitAnswersResponse(
        session_id=session.session_id,
        validation_passed=True,
        errors=[],
        warnings=warnings,
        next_questions=next_questions,
        progress=ProgressSchema(**progress),
        is_complete=is_complete,
        status=session.status
    )


@app.post("/sessions/{session_id}/message", response_model=SendMessageResponse, tags=["Sessions"])
async def send_message(
    session_id: UUID,
    request: SendMessageRequest,
    db: DBSession = Depends(get_db)
):
    """
    Send a message in the conversation.

    The AI will respond to the user's message, extract any data provided,
    and guide the conversation forward.
    """
    # Get session
    session = db.query(Session).filter(
        Session.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is already completed"
        )

    # Get template metadata from database
    template = db.query(DocumentTemplate).filter(
        DocumentTemplate.name == session.template_name,
        DocumentTemplate.is_active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{session.template_name}' not found"
        )

    # Load template and prompt config from Azure Blob Storage
    try:
        template_json, prompt_config_json = template_service.load_template_and_prompt(
            template_blob_path=template.template_blob_path,
            prompt_blob_path=template.prompt_blob_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load template from blob storage: {str(e)}"
        )

    # Continue conversation
    try:
        ai_response, updated_messages, collected_data, is_complete = ai_orchestrator.continue_conversation(
            user_message=request.message,
            messages_history=session.messages,
            template_json=template.template_json,
            prompt_config_json=template.prompt_config_json
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI conversation error: {str(e)}"
        )

    # Update session
    session.messages = updated_messages
    session.collected_data = collected_data

    if is_complete:
        session.status = "ready_for_generation"

    db.commit()

    return SendMessageResponse(
        session_id=session.session_id,
        ai_response=ai_response,
        status=session.status,
        is_complete=is_complete,
        collected_data=collected_data
    )


@app.get("/sessions/{session_id}", response_model=SessionStateResponse, tags=["Sessions"])
async def get_session_state(
    session_id: UUID,
    db: DBSession = Depends(get_db)
):
    """
    Get current state of a session.

    Returns full conversation history and collected data.
    """
    session = db.query(Session).filter(
        Session.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionStateResponse(
        session_id=session.session_id,
        template_id=session.document_template_id,
        template_name=session.template.name,
        status=session.status,
        messages=session.messages,
        collected_data=session.collected_data,
        created_at=session.created_at,
        updated_at=session.updated_at,
        expires_at=session.expires_at
    )


# ==================== Document Generation Endpoints ====================

@app.post("/sessions/{session_id}/generate", response_model=GenerateDocumentResponse, tags=["Documents"])
async def generate_document(
    session_id: UUID,
    request: GenerateDocumentRequest,
    db: DBSession = Depends(get_db)
):
    """
    Generate final document from session data.

    The AI will fill the template with collected data and generate
    a professional PDF or DOCX document.
    """
    # Get session
    session = db.query(Session).filter(
        Session.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    if session.status == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data collection not complete. Continue the conversation first."
        )

    # Validate format
    if request.format not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'pdf' or 'docx'"
        )

    # Get template
    template = session.template

    # Fill template with AI
    try:
        filled_template = ai_orchestrator.fill_template(
            template_json=template.template_json,
            collected_data=session.collected_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fill template: {str(e)}"
        )

    # Generate document
    try:
        if request.format == "pdf":
            blob_url, file_size = document_generator.generate_pdf(
                filled_template=filled_template,
                session_id=str(session.session_id)
            )
        else:  # docx
            blob_url, file_size = document_generator.generate_docx(
                filled_template=filled_template,
                session_id=str(session.session_id)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document generation failed: {str(e)}"
        )

    # Save document record
    generated_doc = GeneratedDocument(
        session_id=session.session_id,
        blob_url=blob_url,
        file_format=request.format,
        file_size_bytes=file_size
    )

    db.add(generated_doc)

    # Mark session as completed
    session.status = "completed"

    db.commit()
    db.refresh(generated_doc)

    return GenerateDocumentResponse(
        document_id=generated_doc.document_id,
        session_id=session.session_id,
        blob_url=blob_url,
        file_format=request.format,
        file_size_bytes=file_size,
        generated_at=generated_doc.generated_at
    )


@app.get("/sessions/{session_id}/documents", tags=["Documents"])
async def list_session_documents(
    session_id: UUID,
    db: DBSession = Depends(get_db)
):
    """List all documents generated for a session."""
    session = db.query(Session).filter(
        Session.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    documents = db.query(GeneratedDocument).filter(
        GeneratedDocument.session_id == session_id
    ).all()

    return {
        "session_id": session_id,
        "documents": [
            {
                "document_id": doc.document_id,
                "blob_url": doc.blob_url,
                "file_format": doc.file_format,
                "file_size_bytes": doc.file_size_bytes,
                "generated_at": doc.generated_at
            }
            for doc in documents
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
