"""
Conversation Flow Engine - GPT-4o powered universal document automation.

This service uses Azure OpenAI GPT-4o to:
1. Analyze any prompt configuration JSON (any structure)
2. Generate a standardized execution plan
3. Determine which questions to ask next
4. Validate user answers
5. Provide intelligent suggestions

The key innovation: Platform is truly document-agnostic because GPT-4o
handles ALL interpretation of prompt structures.
"""
import os
import json
from typing import Dict, List, Any, Tuple, Optional
from openai import AzureOpenAI


class ConversationFlowEngine:
    """
    AI-powered conversation flow engine.

    Uses GPT-4o to interpret any prompt config structure and drive
    the document generation conversation.
    """

    def __init__(self):
        """Initialize Azure OpenAI client."""
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    def analyze_prompt_config(
        self,
        prompt_config_json: Dict,
        template_json: Dict
    ) -> Dict:
        """
        Ask GPT-4o to analyze the prompt configuration and create an execution plan.

        This is the magic: GPT-4o reads ANY JSON structure and converts it into
        a standardized execution plan that the platform can use.

        Args:
            prompt_config_json: The prompt configuration (any structure)
            template_json: The document template structure

        Returns:
            Execution plan with standardized structure
        """
        analysis_prompt = f"""You are a conversation flow analyzer for a legal document generation platform.

Given a prompt configuration JSON (which may have ANY structure), analyze it and create a standardized execution plan.

## Prompt Configuration
```json
{json.dumps(prompt_config_json, indent=2)}
```

## Document Template
```json
{json.dumps(template_json, indent=2)}
```

## Your Task
Analyze the prompt configuration and extract:

1. **Structure Analysis**: Understand how questions are organized (phases/sections, flat list, hierarchical, custom)

2. **Question Sequence**: Extract ALL questions in the order they should be asked. Convert complex question types into simple web form types.

3. **Conditional Logic**: Identify any conditional/followUp questions and their triggers

4. **Validation Rules**: Extract validation requirements

5. **Field Mappings**: Map question IDs to template placeholder fields

Respond with JSON in this EXACT format (this is critical):
```json
{{
  "structure_analysis": {{
    "type": "describe the structure type",
    "total_questions": <number of total questions>,
    "has_conditional_logic": true/false,
    "description": "Brief description of the document flow"
  }},
  "question_sequence": [
    {{
      "sequence_number": 1,
      "question_id": "unique_id",
      "question_text": "What is...",
      "input_type": "text|select|date|number|email|tel",
      "options": ["option1", "option2"] or null,
      "required": true/false,
      "help_text": "helpful guidance" or null,
      "placeholder": "example value" or null,
      "validation_rules": ["rule1", "rule2"] or [],
      "maps_to_field": "TEMPLATE_FIELD_NAME" or null,
      "depends_on": null,
      "shows_after_sequence": null
    }}
  ],
  "conditional_questions": [
    {{
      "question_id": "conditional_question_id",
      "triggered_by_field": "parent_field_id",
      "trigger_condition": {{"field": "value"}},
      "question_text": "What is...",
      "input_type": "text|select|date|number",
      "required": true/false,
      "maps_to_field": "TEMPLATE_FIELD_NAME"
    }}
  ],
  "validation_rules": {{
    "field_validations": {{
      "field_id": ["min_length: 5", "max_length: 100"]
    }},
    "cross_field_validations": [
      {{
        "rule": "end_date must be after start_date",
        "fields": ["start_date", "end_date"],
        "error_message": "End date must be after start date"
      }}
    ]
  }},
  "welcome_message": "A friendly welcome message to start the conversation"
}}
```

IMPORTANT RULES:
- Convert ALL question types to simple web form types (text, select, date, number, email, tel)
- If a question type is "address", break it into multiple text fields (street, city, postal_code, etc.)
- If a question type is "object", break it into multiple questions for each property
- Include ALL questions, both required and optional
- Number questions sequentially starting from 1
- For conditional questions, clearly specify the trigger condition
- Make the welcome_message friendly and encouraging

Respond with ONLY the JSON, no additional text."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.1,  # Low temperature for consistent analysis
            response_format={"type": "json_object"}
        )

        execution_plan = json.loads(response.choices[0].message.content)
        return execution_plan

    def get_first_questions(
        self,
        execution_plan: Dict,
        num_questions: int = 1
    ) -> List[Dict]:
        """
        Extract the first question(s) from the execution plan.

        Args:
            execution_plan: The GPT-4o generated execution plan
            num_questions: How many questions to return (default 1)

        Returns:
            List of question dictionaries ready for Loveable frontend
        """
        question_sequence = execution_plan.get("question_sequence", [])

        if not question_sequence:
            return []

        # Return first N questions that have no dependencies
        first_questions = []
        for q in question_sequence[:num_questions]:
            if q.get("depends_on") is None and q.get("shows_after_sequence") is None:
                first_questions.append(self._format_question_for_frontend(q))

        return first_questions if first_questions else [self._format_question_for_frontend(question_sequence[0])]

    def get_next_questions(
        self,
        execution_plan: Dict,
        answered_question_ids: List[str],
        collected_data: Dict[str, Any],
        num_questions: int = 1
    ) -> List[Dict]:
        """
        Determine which question(s) to ask next based on current state.

        Args:
            execution_plan: The GPT-4o generated execution plan
            answered_question_ids: List of question IDs already answered
            collected_data: All data collected so far
            num_questions: How many questions to return

        Returns:
            List of next question dictionaries
        """
        question_sequence = execution_plan.get("question_sequence", [])
        conditional_questions = execution_plan.get("conditional_questions", [])

        next_questions = []

        # First, check for triggered conditional questions
        for cond_q in conditional_questions:
            if cond_q["question_id"] not in answered_question_ids:
                trigger_field = cond_q["triggered_by_field"]
                trigger_condition = cond_q["trigger_condition"]

                # Check if condition is met
                if self._check_condition(collected_data, trigger_condition):
                    next_questions.append(self._format_question_for_frontend(cond_q))
                    if len(next_questions) >= num_questions:
                        return next_questions

        # Then, get next unanswered sequential questions
        for q in question_sequence:
            if q["question_id"] not in answered_question_ids:
                # Check dependencies
                depends_on = q.get("depends_on")
                if depends_on and depends_on not in answered_question_ids:
                    continue  # Skip this question, dependency not met

                next_questions.append(self._format_question_for_frontend(q))
                if len(next_questions) >= num_questions:
                    break

        return next_questions

    def validate_answers(
        self,
        execution_plan: Dict,
        answers: Dict[str, Any],
        collected_data: Dict[str, Any],
        current_questions: List[Dict] = None
    ) -> Dict:
        """
        Use GPT-4o to validate answers against rules.

        Args:
            execution_plan: The execution plan with validation rules
            answers: The newly submitted answers
            collected_data: All previously collected data
            current_questions: The questions that were asked (with valid options)

        Returns:
            Validation result with errors and warnings
        """
        # Include current questions if provided
        questions_context = ""
        if current_questions:
            questions_context = f"""
## Current Questions Being Answered
```json
{json.dumps(current_questions, indent=2)}
```
"""

        validation_prompt = f"""You are a data validator for a legal document generation system.

## Validation Rules
```json
{json.dumps(execution_plan.get("validation_rules", {}), indent=2)}
```
{questions_context}
## New Answers
```json
{json.dumps(answers, indent=2)}
```

## All Collected Data (for cross-field validation)
```json
{json.dumps(collected_data, indent=2)}
```

## Your Task
Validate ONLY the answers for fields listed in "Current Questions Being Answered".

CRITICAL: Do NOT validate fields that are not in the "Current Questions Being Answered" section.
Only validate the specific fields that were asked in this step.

For each field in "Current Questions Being Answered", check:
1. If the field is marked as "required": true, verify the answer is provided and not empty
2. Data types are correct
3. For SELECT fields: verify the answer matches one of the valid options listed
4. Values meet constraints (length, format, range, etc.)
5. Cross-field validations pass ONLY if both fields are in the current questions (e.g., end date after start date)

IMPORTANT:
- If a field has "options" in the Current Questions, the answer MUST be one of those exact values.
- Ignore any required fields that are NOT in the "Current Questions Being Answered" section.

Respond with JSON:
```json
{{
  "is_valid": true/false,
  "errors": [
    {{
      "field": "field_id",
      "message": "Clear error message for the user",
      "severity": "error"
    }}
  ],
  "warnings": [
    {{
      "field": "field_id",
      "message": "Warning message (non-blocking)",
      "severity": "warning"
    }}
  ]
}}
```

Respond with ONLY the JSON."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": validation_prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        validation_result = json.loads(response.choices[0].message.content)
        return validation_result

    def get_smart_suggestion(
        self,
        question: Dict,
        collected_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Use GPT-4o to provide an intelligent suggestion for a question.

        Args:
            question: The question being asked
            collected_data: Data collected so far for context

        Returns:
            Smart suggestion or None
        """
        if not collected_data:
            return None  # No context yet

        suggestion_prompt = f"""Based on previously collected data, provide a smart suggestion for the current question.

## Collected Data So Far
```json
{json.dumps(collected_data, indent=2)}
```

## Current Question
```json
{json.dumps(question, indent=2)}
```

## Your Task
Provide a helpful suggestion based on:
1. Previously collected data (e.g., if employer is in Ontario, suggest Ontario-specific defaults)
2. Legal best practices
3. Common patterns

Respond with JSON:
```json
{{
  "suggestion": "suggested value or example",
  "reasoning": "why this is suggested (1-2 sentences)",
  "confidence": 0.8
}}
```

If no good suggestion, return:
```json
{{
  "suggestion": null,
  "reasoning": "not enough context",
  "confidence": 0.0
}}
```

Respond with ONLY the JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": suggestion_prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Only return suggestion if confidence is reasonable
            if result.get("confidence", 0) > 0.5:
                return result.get("suggestion")
        except Exception:
            pass  # Suggestions are optional, fail gracefully

        return None

    def is_complete(
        self,
        execution_plan: Dict,
        answered_question_ids: List[str]
    ) -> bool:
        """
        Check if all required questions have been answered.

        Args:
            execution_plan: The execution plan
            answered_question_ids: List of answered question IDs

        Returns:
            True if complete, False otherwise
        """
        question_sequence = execution_plan.get("question_sequence", [])

        # Get all required question IDs
        required_question_ids = set()
        for q in question_sequence:
            if q.get("required", True):  # Default to required
                required_question_ids.add(q["question_id"])

        # Check if all required questions answered
        answered_set = set(answered_question_ids)
        return required_question_ids.issubset(answered_set)

    def calculate_progress(
        self,
        execution_plan: Dict,
        answered_question_ids: List[str],
        current_question: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate progress information.

        Args:
            execution_plan: The execution plan
            answered_question_ids: Questions answered so far
            current_question: The current question being asked

        Returns:
            Progress information dictionary
        """
        question_sequence = execution_plan.get("question_sequence", [])
        total_questions = len(question_sequence)
        answered_count = len(answered_question_ids)

        percent_complete = (answered_count / total_questions * 100) if total_questions > 0 else 0

        # Determine phase name if available
        phase_name = None
        if current_question:
            # Try to extract phase from question metadata or structure analysis
            phase_name = current_question.get("phase_name") or execution_plan.get("structure_analysis", {}).get("description")

        return {
            "current_step": answered_count + 1,
            "total_steps": total_questions,
            "percent_complete": round(percent_complete, 1),
            "phase_name": phase_name
        }

    # Private helper methods

    def _format_question_for_frontend(self, question: Dict) -> Dict:
        """
        Format a question from execution plan for Loveable frontend.

        Args:
            question: Question from execution plan

        Returns:
            Formatted question for frontend
        """
        return {
            "field_id": question["question_id"],
            "label": question["question_text"],
            "input_type": question.get("input_type", "text"),
            "options": question.get("options"),
            "required": question.get("required", True),
            "help_text": question.get("help_text"),
            "placeholder": question.get("placeholder"),
            "current_value": None,  # Will be filled in by endpoint if re-showing
            "suggestion": None,  # Will be filled by get_smart_suggestion
            "validation_pattern": None  # Could add regex patterns here
        }

    def _check_condition(
        self,
        collected_data: Dict[str, Any],
        condition: Dict[str, Any]
    ) -> bool:
        """
        Check if a conditional trigger condition is met.

        Args:
            collected_data: All collected data
            condition: Condition to check (e.g., {"contract_type": "fixed_term"})

        Returns:
            True if condition met, False otherwise
        """
        for field, expected_value in condition.items():
            if collected_data.get(field) != expected_value:
                return False
        return True
