"""
Template Upload Utility

This script uploads a template and its prompt configuration to Azure Blob Storage
and creates the corresponding database record.

Usage:
    python utilities/upload_template.py \
        --name "Employment Agreement - Canada" \
        --description "Canadian employment contract template" \
        --template template.json \
        --prompt prompt_config.json

Environment variables required:
    - AZURE_STORAGE_CONNECTION_STRING
    - DATABASE_URL
"""
import os
import sys
import json
import uuid
import argparse
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables BEFORE importing database modules
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

from azure.storage.blob import BlobServiceClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from database.models import DocumentTemplate, Base


def validate_json_file(file_path: str) -> dict:
    """Load and validate a JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{file_path}': {str(e)}")
        sys.exit(1)


def upload_to_blob_storage(
    connection_string: str,
    container_name: str,
    blob_path: str,
    data: dict
) -> str:
    """
    Upload JSON data to Azure Blob Storage.

    Returns the blob path (without container name).
    """
    try:
        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # Get container client (create if doesn't exist)
        container_client = blob_service_client.get_container_client(container_name)
        try:
            container_client.create_container()
            print(f"Created container: {container_name}")
        except Exception:
            pass  # Container already exists

        # Upload blob
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_path
        )

        json_str = json.dumps(data, indent=2)
        blob_client.upload_blob(json_str, overwrite=True)

        print(f"Uploaded to blob: {container_name}/{blob_path}")
        return blob_path

    except Exception as e:
        print(f"Error uploading to blob storage: {str(e)}")
        sys.exit(1)


def create_database_record(
    database_url: str,
    name: str,
    description: str,
    template_blob_path: str,
    prompt_blob_path: str,
    version: str = "1.0.0"
) -> uuid.UUID:
    """Create a DocumentTemplate record in the database."""
    try:
        # Create database engine
        engine = create_engine(database_url)

        # Create tables if they don't exist
        Base.metadata.create_all(engine)

        # Create session
        with Session(engine) as session:
            # Check if template with this name already exists
            existing = session.query(DocumentTemplate).filter(
                DocumentTemplate.name == name
            ).first()

            if existing:
                print(f"Warning: Template '{name}' already exists with ID: {existing.id}")
                print("Updating existing template...")

                existing.description = description
                existing.template_blob_path = template_blob_path
                existing.prompt_blob_path = prompt_blob_path
                existing.version = version
                existing.is_active = True

                session.commit()
                return existing.id
            else:
                # Create new template record
                template = DocumentTemplate(
                    name=name,
                    description=description,
                    template_blob_path=template_blob_path,
                    prompt_blob_path=prompt_blob_path,
                    version=version,
                    is_active=True
                )

                session.add(template)
                session.commit()
                session.refresh(template)

                print(f"Created database record with ID: {template.id}")
                return template.id

    except Exception as e:
        print(f"Error creating database record: {str(e)}")
        sys.exit(1)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Upload a template to the Legal Document Automation Platform"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Template name (e.g., 'Employment Agreement - Canada')"
    )
    parser.add_argument(
        "--description",
        default="",
        help="Template description"
    )
    parser.add_argument(
        "--template",
        required=True,
        help="Path to template JSON file"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Path to prompt configuration JSON file"
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Template version (default: 1.0.0)"
    )
    parser.add_argument(
        "--container",
        default="document-templates",
        help="Azure Blob Storage container name (default: document-templates)"
    )

    args = parser.parse_args()

    # Validate environment variables
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    database_url = os.getenv("DATABASE_URL")

    if not connection_string:
        print("Error: AZURE_STORAGE_CONNECTION_STRING environment variable not set")
        sys.exit(1)

    if not database_url:
        print("Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    print(f"Uploading template: {args.name}")
    print(f"Template file: {args.template}")
    print(f"Prompt file: {args.prompt}")
    print()

    # Validate JSON files
    print("Validating JSON files...")
    template_data = validate_json_file(args.template)
    prompt_data = validate_json_file(args.prompt)
    print("JSON validation passed")
    print()

    # Generate unique template ID for blob paths
    template_id = str(uuid.uuid4())

    # Upload template to blob storage
    print("Uploading template to Azure Blob Storage...")
    template_blob_path = upload_to_blob_storage(
        connection_string=connection_string,
        container_name=args.container,
        blob_path=f"templates/{template_id}/template.json",
        data=template_data
    )

    # Upload prompt config to blob storage
    print("Uploading prompt configuration to Azure Blob Storage...")
    prompt_blob_path = upload_to_blob_storage(
        connection_string=connection_string,
        container_name=args.container,
        blob_path=f"templates/{template_id}/prompt_config.json",
        data=prompt_data
    )
    print()

    # Create database record
    print("Creating database record...")
    record_id = create_database_record(
        database_url=database_url,
        name=args.name,
        description=args.description,
        template_blob_path=template_blob_path,
        prompt_blob_path=prompt_blob_path,
        version=args.version
    )
    print()

    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"Template Name: {args.name}")
    print(f"Template ID: {record_id}")
    print(f"Template Blob: {template_blob_path}")
    print(f"Prompt Blob: {prompt_blob_path}")
    print()
    print("The template is now available in the platform.")
    print("Users can start sessions with this template using:")
    print(f'  POST /sessions/start  {{\"template_name\": \"{args.name}\"}}')


if __name__ == "__main__":
    main()
