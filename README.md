# Legal Document Automation Platform

AI-powered legal document generation platform with conversational interface powered by Azure OpenAI GPT-4o.

## Features

- **AI-First Architecture**: GPT-4o dynamically interprets document templates and prompts
- **Conversational Interface**: Natural conversation flow for collecting document data
- **Document-Agnostic Design**: Works with any document template structure
- **Professional Document Generation**: Creates formatted Word documents
- **Azure Integration**: Leverages Azure OpenAI, PostgreSQL, and Blob Storage

## Architecture

- **FastAPI**: Async REST API framework
- **Azure OpenAI GPT-4o**: Conversation intelligence
- **Azure PostgreSQL**: Session and template storage with JSONB support
- **Azure Blob Storage**: Template and document storage
- **ConversationFlowEngine**: 500+ line service handling GPT-4o-powered conversations

## API Endpoints

- `GET /health` - Health check
- `GET /templates` - List available templates
- `POST /sessions/start` - Start new document generation session
- `POST /sessions/{session_id}/submit_answers` - Submit answers to questions
- `GET /sessions/{session_id}` - Get session details
- `POST /sessions/{session_id}/generate` - Generate final document

## Environment Variables

Required environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_CONTAINER_NAME=document-templates
```

## Deployment

Automatic deployment to Azure App Service via GitHub Actions on push to main branch.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with required variables

# Run server
python3 -m uvicorn main:app --reload --port 8000
```

## Template Upload

Upload templates using the utility script:

```bash
python utilities/upload_template.py \
  --name "Employment Agreement - Canada" \
  --description "Canadian employment contract template" \
  --template path/to/template.json \
  --prompt path/to/prompt_config.json
```

## Testing

```bash
# Health check
curl http://localhost:8000/health

# List templates
curl http://localhost:8000/templates

# Start session
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{"template_name": "Employment Agreement - Canada"}'
```

## License

Proprietary - All Rights Reserved

# Legal Document Automation Platform v1.0.0
