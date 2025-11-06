"""
Migration script to load Employment Agreement template into database.

This demonstrates how to add new templates to the platform.
The template and prompt config are stored as JSON in the database,
and the AI will interpret them dynamically.
"""
import os
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseClient
from database.models import DocumentTemplate


# Employment Agreement Template JSON
EMPLOYMENT_AGREEMENT_TEMPLATE = {
    "title": "EMPLOYMENT AGREEMENT",
    "sections": [
        {
            "section_title": "PARTIES",
            "content": [
                "This Employment Agreement (the \"Agreement\") is entered into as of [EFFECTIVE_DATE], between:",
                "",
                "EMPLOYER: [EMPLOYER_NAME]",
                "Address: [EMPLOYER_ADDRESS]",
                "(the \"Employer\")",
                "",
                "EMPLOYEE: [EMPLOYEE_NAME]",
                "Address: [EMPLOYEE_ADDRESS]",
                "(the \"Employee\")"
            ]
        },
        {
            "section_title": "1. POSITION AND DUTIES",
            "content": [
                "1.1 The Employer hereby employs the Employee in the position of [POSITION_TITLE].",
                "",
                "1.2 The Employee's duties shall include: [JOB_DUTIES]",
                "",
                "1.3 The Employee shall report to: [REPORTS_TO]",
                "",
                "1.4 The Employee's principal place of work shall be: [WORK_LOCATION]"
            ]
        },
        {
            "section_title": "2. TERM OF EMPLOYMENT",
            "content": [
                "2.1 Employment Start Date: [START_DATE]",
                "",
                "2.2 This is [EMPLOYMENT_TYPE] employment.",
                "",
                "[OPTIONAL_END_DATE_SECTION]"
            ]
        },
        {
            "section_title": "3. COMPENSATION",
            "content": [
                "3.1 Base Salary: The Employee shall receive an annual salary of [ANNUAL_SALARY], payable in accordance with the Employer's standard payroll practices.",
                "",
                "[OPTIONAL_BONUS_SECTION]",
                "",
                "3.2 Benefits: [BENEFITS_DESCRIPTION]"
            ]
        },
        {
            "section_title": "4. WORKING HOURS",
            "content": [
                "4.1 The Employee's standard working hours shall be [WORKING_HOURS] per week.",
                "",
                "4.2 Work Schedule: [WORK_SCHEDULE]"
            ]
        },
        {
            "section_title": "5. VACATION AND LEAVE",
            "content": [
                "5.1 The Employee shall be entitled to [VACATION_DAYS] days of paid vacation per year.",
                "",
                "5.2 Additional leave entitlements shall be in accordance with applicable employment standards legislation and the Employer's policies."
            ]
        },
        {
            "section_title": "6. TERMINATION",
            "content": [
                "6.1 Notice Period: Either party may terminate this Agreement by providing [NOTICE_PERIOD] written notice.",
                "",
                "6.2 Severance: Upon termination without cause, the Employee shall be entitled to [SEVERANCE_TERMS].",
                "",
                "6.3 The Employer may terminate employment immediately for just cause without notice or payment in lieu."
            ]
        },
        {
            "section_title": "7. CONFIDENTIALITY",
            "content": [
                "7.1 The Employee acknowledges that during employment, they may have access to confidential information.",
                "",
                "7.2 The Employee agrees to maintain confidentiality of all proprietary information both during and after employment.",
                "",
                "7.3 This obligation shall survive termination of this Agreement."
            ]
        },
        {
            "section_title": "8. INTELLECTUAL PROPERTY",
            "content": [
                "8.1 All intellectual property created by the Employee in the course of employment shall be the exclusive property of the Employer.",
                "",
                "8.2 The Employee agrees to execute any documents necessary to assign such rights to the Employer."
            ]
        },
        {
            "section_title": "9. GOVERNING LAW",
            "content": [
                "9.1 This Agreement shall be governed by and construed in accordance with the laws of [JURISDICTION].",
                "",
                "9.2 This Agreement constitutes the entire agreement between the parties and supersedes all prior agreements and understandings."
            ]
        },
        {
            "section_title": "SIGNATURES",
            "signature_block": {
                "employer_signature": {
                    "content": [
                        "EMPLOYER:",
                        "",
                        "_________________________________",
                        "[EMPLOYER_SIGNATORY_NAME]",
                        "[EMPLOYER_SIGNATORY_TITLE]",
                        "Date: _____________"
                    ]
                },
                "employee_signature": {
                    "content": [
                        "EMPLOYEE:",
                        "",
                        "_________________________________",
                        "[EMPLOYEE_NAME]",
                        "Date: _____________"
                    ]
                }
            }
        }
    ]
}


# Prompt Configuration for AI Conversation
EMPLOYMENT_AGREEMENT_PROMPT_CONFIG = {
    "document_type": "Employment Agreement",
    "jurisdiction": "Canada (adaptable to provinces)",
    "description": "Guide user through creating a comprehensive employment agreement",

    "conversation_phases": [
        {
            "phase": "introduction",
            "description": "Welcome and explain the process",
            "initial_message": "Hello! I'll help you create a professional Employment Agreement. This will take about 10-15 minutes. I'll guide you through gathering all necessary information step by step. Are you ready to begin?"
        },
        {
            "phase": "parties",
            "description": "Collect information about employer and employee",
            "required_fields": [
                "EFFECTIVE_DATE",
                "EMPLOYER_NAME",
                "EMPLOYER_ADDRESS",
                "EMPLOYEE_NAME",
                "EMPLOYEE_ADDRESS"
            ],
            "questions": [
                "What is the effective date of this agreement? (e.g., January 1, 2025)",
                "What is the legal name of the Employer (company)?",
                "What is the Employer's business address?",
                "What is the full legal name of the Employee?",
                "What is the Employee's residential address?"
            ]
        },
        {
            "phase": "position_details",
            "description": "Collect job position information",
            "required_fields": [
                "POSITION_TITLE",
                "JOB_DUTIES",
                "REPORTS_TO",
                "WORK_LOCATION"
            ],
            "questions": [
                "What is the Employee's job title/position?",
                "Please describe the main duties and responsibilities for this role",
                "Who will the Employee report to? (Title or name)",
                "What is the primary work location? (Office address or 'Remote')"
            ]
        },
        {
            "phase": "employment_term",
            "description": "Collect employment term details",
            "required_fields": [
                "START_DATE",
                "EMPLOYMENT_TYPE"
            ],
            "optional_fields": [
                "END_DATE",
                "OPTIONAL_END_DATE_SECTION"
            ],
            "questions": [
                "What is the employment start date?",
                "Is this permanent employment or fixed-term contract?",
                "If fixed-term, what is the end date? (or type 'N/A' if permanent)"
            ]
        },
        {
            "phase": "compensation",
            "description": "Collect salary and benefits information",
            "required_fields": [
                "ANNUAL_SALARY",
                "BENEFITS_DESCRIPTION"
            ],
            "optional_fields": [
                "BONUS_AMOUNT",
                "OPTIONAL_BONUS_SECTION"
            ],
            "questions": [
                "What is the annual salary? (e.g., $75,000 CAD)",
                "Is there a performance bonus? If yes, describe the terms. If no, type 'No bonus'",
                "Please describe the benefits package (health insurance, retirement, etc.)"
            ]
        },
        {
            "phase": "working_conditions",
            "description": "Collect working hours and vacation",
            "required_fields": [
                "WORKING_HOURS",
                "WORK_SCHEDULE",
                "VACATION_DAYS"
            ],
            "questions": [
                "How many hours per week will the Employee work? (e.g., 40 hours)",
                "What is the work schedule? (e.g., Monday-Friday, 9am-5pm)",
                "How many paid vacation days per year?"
            ]
        },
        {
            "phase": "termination",
            "description": "Collect termination and severance terms",
            "required_fields": [
                "NOTICE_PERIOD",
                "SEVERANCE_TERMS"
            ],
            "questions": [
                "What is the notice period for termination? (e.g., 2 weeks, 1 month)",
                "What severance will be provided upon termination without cause? (e.g., 2 weeks pay per year of service, up to maximum of 24 weeks)"
            ]
        },
        {
            "phase": "legal_details",
            "description": "Collect jurisdiction and signing authority",
            "required_fields": [
                "JURISDICTION",
                "EMPLOYER_SIGNATORY_NAME",
                "EMPLOYER_SIGNATORY_TITLE"
            ],
            "questions": [
                "Which province/territory's laws will govern this agreement? (e.g., Ontario, British Columbia)",
                "Who will sign on behalf of the Employer? (Full name)",
                "What is their title? (e.g., CEO, HR Director)"
            ]
        },
        {
            "phase": "review",
            "description": "Review all collected information",
            "completion_message": "Perfect! I've collected all the necessary information for your Employment Agreement. Please review the data I've gathered. If everything looks correct, I can now generate your document in PDF or DOCX format."
        }
    ],

    "validation_rules": {
        "EFFECTIVE_DATE": "Must be a valid date",
        "START_DATE": "Must be a valid date",
        "ANNUAL_SALARY": "Must include currency and amount",
        "WORKING_HOURS": "Must be a reasonable number (typically 35-50)",
        "VACATION_DAYS": "Must comply with minimum standards (typically 10+ days in Canada)"
    },

    "legal_notes": [
        "This template complies with Canadian employment law principles",
        "Provincial employment standards legislation will override contract terms where applicable",
        "Consider having the agreement reviewed by legal counsel before execution",
        "Ensure compliance with minimum wage, vacation, and notice requirements for your jurisdiction"
    ]
}


def load_template():
    """
    Load the employment agreement template.

    This script:
    1. Uploads template and prompt JSONs to Azure Blob Storage
    2. Creates metadata record in PostgreSQL database
    """
    print("Loading Employment Agreement template...")

    # Import services
    from services import TemplateService

    # Create database tables if they don't exist
    DatabaseClient.create_tables()

    # Initialize template service
    template_service = TemplateService()

    # Upload template and prompt to blob storage
    print("Uploading template and prompt to Azure Blob Storage...")
    try:
        template_blob_path, prompt_blob_path = template_service.upload_template(
            template_name="employment-agreement-canada",
            template_json=EMPLOYMENT_AGREEMENT_TEMPLATE,
            prompt_config_json=EMPLOYMENT_AGREEMENT_PROMPT_CONFIG
        )
        print(f"  Template uploaded to: {template_blob_path}")
        print(f"  Prompt uploaded to: {prompt_blob_path}")
    except Exception as e:
        print(f"ERROR: Failed to upload to blob storage: {e}")
        return

    # Create or update database record
    print("Creating database metadata record...")
    with DatabaseClient.get_session() as session:
        # Check if template already exists
        existing = session.query(DocumentTemplate).filter(
            DocumentTemplate.name == "Employment Agreement - Canada"
        ).first()

        if existing:
            print(f"  Template already exists, updating...")
            existing.template_blob_path = template_blob_path
            existing.prompt_blob_path = prompt_blob_path
            existing.description = "Comprehensive employment agreement for Canadian employers"
            existing.version = "1.0.0"
            existing.is_active = True
        else:
            # Create new template
            template = DocumentTemplate(
                name="Employment Agreement - Canada",
                description="Comprehensive employment agreement for Canadian employers",
                template_blob_path=template_blob_path,
                prompt_blob_path=prompt_blob_path,
                version="1.0.0",
                is_active=True
            )
            session.add(template)
            print(f"  Created new template record")

        print("\nTemplate loaded successfully!")
        print("\nTemplate Details:")
        print(f"  Name: Employment Agreement - Canada")
        print(f"  Version: 1.0.0")
        print(f"  Blob Storage:")
        print(f"    Template: {template_blob_path}")
        print(f"    Prompt: {prompt_blob_path}")
        print(f"  Sections: {len(EMPLOYMENT_AGREEMENT_TEMPLATE['sections'])}")
        print(f"  Conversation Phases: {len(EMPLOYMENT_AGREEMENT_PROMPT_CONFIG['conversation_phases'])}")
        print(f"  Total Placeholders: {len([f for phase in EMPLOYMENT_AGREEMENT_PROMPT_CONFIG['conversation_phases'] if 'required_fields' in phase for f in phase['required_fields']])}")


if __name__ == "__main__":
    load_template()
