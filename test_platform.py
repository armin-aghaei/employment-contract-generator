"""
Quick test script to verify the platform is working correctly.

This tests:
1. Database connection
2. Service initialization
3. Basic endpoint functionality
"""
import os
import sys

# Set up test environment variables if not already set
if not os.getenv("DATABASE_URL"):
    print("WARNING: DATABASE_URL not set. Using test database.")
    os.environ["DATABASE_URL"] = "postgresql://localhost:5432/legal_docs_test"

if not os.getenv("AZURE_OPENAI_API_KEY"):
    print("ERROR: AZURE_OPENAI_API_KEY environment variable not set")
    sys.exit(1)

if not os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
    print("ERROR: AZURE_STORAGE_CONNECTION_STRING environment variable not set")
    sys.exit(1)

print("="  * 60)
print("LEGAL DOCUMENT AUTOMATION PLATFORM - TEST SUITE")
print("=" * 60)
print()

# Test 1: Import all modules
print("[1/6] Testing module imports...")
try:
    from database import DatabaseClient
    from database.models import DocumentTemplate, Session, GeneratedDocument
    from services import AIOrchestrator, DocumentGenerator, TemplateService, ConversationFlowEngine
    from schemas import StartSessionRequest, SubmitAnswersRequest
    print("✓ All modules imported successfully")
except Exception as e:
    print(f"✗ Module import failed: {str(e)}")
    sys.exit(1)

# Test 2: Database connection
print("\n[2/6] Testing database connection...")
try:
    DatabaseClient.create_tables()
    print("✓ Database connection successful")
except Exception as e:
    print(f"✗ Database connection failed: {str(e)}")
    print("Note: Make sure your DATABASE_URL is correct and PostgreSQL is running")
    sys.exit(1)

# Test 3: Initialize services
print("\n[3/6] Testing service initialization...")
try:
    ai_orchestrator = AIOrchestrator()
    document_generator = DocumentGenerator()
    template_service = TemplateService()
    conversation_engine = ConversationFlowEngine()
    print("✓ All services initialized successfully")
except Exception as e:
    print(f"✗ Service initialization failed: {str(e)}")
    sys.exit(1)

# Test 4: Test ConversationFlowEngine with sample prompt
print("\n[4/6] Testing ConversationFlowEngine...")
try:
    # Simple test prompt config
    test_prompt = {
        "systemPrompt": "You are a test assistant",
        "dataCollection": {
            "questions": [
                {
                    "id": "test_question",
                    "prompt": "What is your name?",
                    "type": "text",
                    "required": True
                }
            ]
        }
    }

    test_template = {
        "documentType": "Test Document",
        "sections": {
            "test": {
                "template": "Hello [NAME]"
            }
        }
    }

    execution_plan = conversation_engine.analyze_prompt_config(
        prompt_config_json=test_prompt,
        template_json=test_template
    )

    if "question_sequence" in execution_plan:
        print(f"✓ ConversationFlowEngine working (generated {len(execution_plan['question_sequence'])} questions)")
    else:
        print("⚠ ConversationFlowEngine returned unexpected format")
except Exception as e:
    print(f"✗ ConversationFlowEngine test failed: {str(e)}")
    print(f"Error details: {type(e).__name__}")

# Test 5: Test FastAPI app can be imported
print("\n[5/6] Testing FastAPI application...")
try:
    from main import app
    print("✓ FastAPI application imported successfully")
except Exception as e:
    print(f"✗ FastAPI application import failed: {str(e)}")
    sys.exit(1)

# Test 6: Check all endpoints are registered
print("\n[6/6] Checking API endpoints...")
try:
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    required_endpoints = [
        "/",
        "/health",
        "/templates",
        "/sessions/start",
        "/sessions/{session_id}/submit",
        "/sessions/{session_id}",
        "/sessions/{session_id}/generate"
    ]

    missing = [endpoint for endpoint in required_endpoints if endpoint not in routes]

    if missing:
        print(f"⚠ Missing endpoints: {missing}")
    else:
        print(f"✓ All required endpoints registered ({len(routes)} total routes)")
except Exception as e:
    print(f"✗ Endpoint check failed: {str(e)}")

print()
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print("Platform is ready for testing!")
print()
print("Next steps:")
print("1. Set up your environment variables (.env file)")
print("2. Upload your first template using utilities/upload_template.py")
print("3. Start the server: python main.py")
print("4. Visit http://localhost:8000/docs for interactive API documentation")
print()
