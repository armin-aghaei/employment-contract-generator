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
import re
from typing import Dict, List, Any, Tuple, Optional
from openai import AzureOpenAI
from openai import APITimeoutError, APIConnectionError


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
        analysis_prompt = f"""You are a DIRECT CONVERTER for a legal document generation platform.

CRITICAL: Your job is to FAITHFULLY CONVERT the provided template configuration into a standardized execution plan.
You are NOT an analyzer or summarizer - you are a CONVERTER that preserves EVERY question EXACTLY as defined.

## Prompt Configuration
```json
{json.dumps(prompt_config_json, indent=2)}
```

## Document Template
```json
{json.dumps(template_json, indent=2)}
```

## CRITICAL CONVERSION RULES - READ CAREFULLY:

1. **COMPLETE FIDELITY**: You MUST include EVERY SINGLE question defined in the configuration
   - Do NOT skip questions
   - Do NOT simplify questions
   - Do NOT combine questions
   - Do NOT create new questions not in the template
   - Use the EXACT text from the "prompt" field as the question_text

2. **PRESERVE STRUCTURE**: Follow the exact phase and section order defined in the template
   - Process phases in numerical order (Phase 1, Phase 2, etc.)
   - Within each phase, process sections in the order defined
   - Within each section, process questions in the order defined
   - Assign sequence_number sequentially (1, 2, 3, ...) following this order

3. **QUESTION CONVERSION**: Convert each question exactly as specified:
   - question_id: Use the "id" field from the template
   - question_text: Use the exact "prompt" field text
   - input_type: Use the "type" field (convert "address" and "object" types - see below)
   - options: Use the exact "options" array if present
   - required: Use the section's "required" or question's requirement
   - help_text: Combine "guidance" + "legal_note" if both present
   - validation_rules: Extract from "validation" field

4. **HANDLE COMPLEX TYPES**:
   - For type="address" with fields like ["street", "city", "province", "postal_code"]:
     Create SEPARATE questions for each field (e.g., employer_address_street, employer_address_city)
   - For type="object" with multiple fields:
     Create SEPARATE questions for each property
   - Use text/select/date/number/email/tel for simple types

5. **CONDITIONAL LOGIC (followUp)**:
   - When a question has a "followUp" field, extract ALL questions from followUp.questions array
   - Add them to conditional_questions array
   - Set triggered_by_field to the parent question's ID
   - Set trigger_condition based on the followUp condition

6. **OPTIONAL SECTIONS (required: false)**:
   - If a section is marked required: false, it's typically controlled by a yes/no question
   - The first question in an optional section is usually "Include X?" or similar
   - All subsequent questions in that section should be conditional on the first question's answer

7. **READ THE SYSTEMPROMPT**: The prompt configuration may include a "systemPrompt" field with instructions
   - This field tells you the INTENT and RULES for how to process the template
   - If it says "MUST use the EXACT questions" - you MUST include every question
   - If it says "MUST follow the EXACT sequence" - you MUST preserve the order
   - If it says "MUST NOT skip any questions" - you MUST include all questions
   - Treat the systemPrompt as your PRIMARY directive

## CONVERSION PROCESS:

Step 1: Read the systemPrompt (if present) to understand the template author's intent
Step 2: Identify the structure (look for "phases", "sections", "questions" arrays)
Step 3: Iterate through phases → sections → questions in order
Step 4: For EACH question found, create an entry in question_sequence
Step 5: For questions with followUp logic, add to conditional_questions
Step 6: Extract validation rules from each question
Step 7: Generate a friendly welcome_message

REMEMBER: Your output should have the SAME NUMBER of questions as the input template!
If the template has 50 questions, your execution plan should have 50 questions!

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
      "question_id": "field_name_in_snake_case",
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

  IMPORTANT: For question_id, use the actual field name in snake_case (e.g., "province_territory", "employer_name", "employee_full_name").
  This identifier must be consistent and will be used to track which questions have been answered.
  Do NOT use generic IDs like "Q001" or "question_1" - use descriptive field names that match the data being collected.
  "conditional_questions": [
    {{
      "question_id": "conditional_field_name_in_snake_case",
      "triggered_by_field": "parent_field_name",
      "trigger_condition": {{"field": "value"}},
      "question_text": "What is...",
      "input_type": "text|select|date|number",
      "required": true/false,
      "maps_to_field": "TEMPLATE_FIELD_NAME"
    }}
  ],

  IMPORTANT: For conditional questions, also use actual field names in snake_case for question_id (e.g., "probation_end_date", "commission_rate").
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

CRITICAL - HANDLING PHASES AND OPTIONAL CLAUSES:
- If the prompt configuration has a "Phase 0" or similar phase for "Optional Clause Selection", these questions MUST appear FIRST in the question_sequence
- These are "yes/no" questions asking whether to include optional contract clauses (e.g., "Include probation period?", "Include work location?", "Include benefits?")
- Place ALL Phase 0 questions at the beginning of question_sequence (sequence_number 1, 2, 3, etc.)
- Then follow with other phases in order (Phase 1, Phase 2, etc.)

CRITICAL - CONDITIONAL FOLLOW-UP QUESTIONS (EXTREMELY IMPORTANT):
- For EVERY "yes/no" question about including an optional clause, you MUST create corresponding conditional questions to collect the actual details
- This is MANDATORY for ALL optional clauses without exception
- Examples (you MUST follow this pattern for ALL optional clauses):

  Example 1 - Work Location:
  - Yes/No question: "Include work location?" (field_id: "include_work_location")
  - Conditional detail question: "What is the work location?" (field_id: "work_location", triggered_by: "include_work_location", condition: {{"include_work_location": "yes"}})

  Example 2 - Working Hours:
  - Yes/No question: "Include working hours?" (field_id: "include_working_hours")
  - Conditional detail question: "What are the working hours?" (field_id: "working_hours", triggered_by: "include_working_hours", condition: {{"include_working_hours": "yes"}})

  Example 3 - Benefits (VERY IMPORTANT):
  - Yes/No question: "Include benefits?" (field_id: "include_benefits")
  - Conditional detail question: "What benefits are provided?" (field_id: "benefits_description", triggered_by: "include_benefits", condition: {{"include_benefits": "yes"}})

  Example 4 - Additional Compensation (VERY IMPORTANT):
  - Yes/No question: "Include additional compensation?" (field_id: "include_additional_compensation")
  - Conditional detail question: "What additional compensation is provided?" (field_id: "additional_compensation_details", triggered_by: "include_additional_compensation", condition: {{"include_additional_compensation": "yes"}})

  Example 5 - Probation Period:
  - Yes/No question: "Include probation period?" (field_id: "include_probation_period")
  - Conditional detail questions:
    * "What is the probation duration?" (field_id: "probation_duration")
    * "What are the probation terms?" (field_id: "probation_terms")
    Both triggered by "include_probation_period" with condition {{"include_probation_period": "yes"}}

- The conditional questions MUST be in the conditional_questions array with:
  - triggered_by_field: the question_id of the yes/no question
  - trigger_condition: the exact answer that triggers this question (e.g., {{"include_work_location": "yes"}})

- CRITICAL: DO NOT skip ANY detail questions - EVERY optional clause YES/NO question REQUIRES its corresponding detail question(s)!
- Without the detail questions, we cannot populate the template placeholders and the contract will be incomplete!

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

        # DEBUG: Log what we're checking
        print(f"[DEBUG get_next_questions] answered_question_ids: {answered_question_ids}")
        print(f"[DEBUG get_next_questions] Total questions in sequence: {len(question_sequence)}")
        if question_sequence:
            print(f"[DEBUG get_next_questions] First 5 questions:")
            for i, q in enumerate(question_sequence[:5]):
                print(f"  [{i}] question_id={q.get('question_id')}, depends_on={q.get('depends_on')}")

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
            question_id = q["question_id"]
            is_answered = question_id in answered_question_ids

            print(f"[DEBUG] Checking question_id '{question_id}': answered={is_answered}")

            if not is_answered:
                # Check dependencies
                depends_on = q.get("depends_on")
                if depends_on and depends_on not in answered_question_ids:
                    print(f"[DEBUG] Skipping '{question_id}' - dependency '{depends_on}' not met")
                    continue  # Skip this question, dependency not met

                print(f"[DEBUG] Adding '{question_id}' to next_questions")
                next_questions.append(self._format_question_for_frontend(q))
                if len(next_questions) >= num_questions:
                    break

        print(f"[DEBUG get_next_questions] Returning {len(next_questions)} questions")
        return next_questions

    def _simple_validation(
        self,
        answers: Dict[str, Any],
        current_questions: List[Dict]
    ) -> Dict:
        """
        Fast Python-based validation for simple field types.

        This handles 80% of validation cases instantly without AI:
        - Required field checks
        - Basic type validation
        - Email/phone format validation
        - Select option validation

        IMPORTANT: Only validates fields that are actually in the answers dict.
        Does NOT validate fields that weren't submitted.

        Args:
            answers: The submitted answers
            current_questions: Questions being validated

        Returns:
            Validation result dict with is_valid, errors, warnings
        """
        errors = []
        warnings = []

        for question in current_questions:
            field_id = question.get("field_id")

            # CRITICAL: Only validate fields that were actually submitted
            # Skip fields that aren't in the answers dict
            if field_id not in answers:
                continue

            value = answers.get(field_id)
            required = question.get("required", False)
            input_type = question.get("input_type", "text")
            options = question.get("options")

            # Check required fields
            if required and (value is None or str(value).strip() == ""):
                errors.append({
                    "field": field_id,
                    "message": f"{question.get('label', field_id)} is required",
                    "severity": "error"
                })
                continue

            # Skip validation if field value is empty
            if value is None or str(value).strip() == "":
                continue

            # Validate select options
            if input_type == "select" and options:
                if value not in options:
                    errors.append({
                        "field": field_id,
                        "message": f"Must select one of: {', '.join(options)}",
                        "severity": "error"
                    })

            # Validate email format
            elif input_type == "email":
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, str(value)):
                    errors.append({
                        "field": field_id,
                        "message": "Please enter a valid email address",
                        "severity": "error"
                    })

            # Validate phone format (basic)
            elif input_type == "tel":
                # Remove common separators
                phone_digits = re.sub(r'[\s\-\(\)\.]', '', str(value))
                if not re.match(r'^\+?[0-9]{10,15}$', phone_digits):
                    errors.append({
                        "field": field_id,
                        "message": "Please enter a valid phone number",
                        "severity": "error"
                    })

            # Validate number type
            elif input_type == "number":
                try:
                    float(value)
                except ValueError:
                    errors.append({
                        "field": field_id,
                        "message": "Please enter a valid number",
                        "severity": "error"
                    })

            # Validate date format (basic ISO check)
            elif input_type == "date":
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(value)):
                    errors.append({
                        "field": field_id,
                        "message": "Please enter a valid date (YYYY-MM-DD)",
                        "severity": "error"
                    })

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def validate_answers(
        self,
        execution_plan: Dict,
        answers: Dict[str, Any],
        collected_data: Dict[str, Any],
        current_questions: List[Dict] = None
    ) -> Dict:
        """
        Hybrid validation: Fast Python validation + GPT-4o for complex cases.

        Uses two-tier approach:
        1. Simple Python validation (instant, no AI cost)
        2. GPT-4o validation only if needed (complex rules, cross-field validation)

        Args:
            execution_plan: The execution plan with validation rules
            answers: The newly submitted answers
            collected_data: All previously collected data
            current_questions: The questions that were asked (with valid options)

        Returns:
            Validation result with errors and warnings
        """
        # TIER 1: Try simple Python validation first
        if current_questions:
            print("[Validation] Using fast Python validation")
            simple_result = self._simple_validation(answers, current_questions)

            # If simple validation fails, return immediately
            if not simple_result["is_valid"]:
                print(f"[Validation] Simple validation failed: {simple_result['errors']}")
                return simple_result

            # TEMPORARY FIX: Disable GPT-4o validation entirely
            # GPT-4o keeps validating ALL fields despite explicit scope instructions
            # This causes validation errors for fields not yet submitted
            # Simple Python validation is sufficient for now
            print("[Validation] Simple validation passed, GPT-4o disabled (scope issues)")
            return simple_result

            # TODO: Re-enable GPT-4o validation once we can guarantee field scope
            # validation_rules = execution_plan.get("validation_rules", {})
            # needs_complex = bool(validation_rules and validation_rules != {})
            #
            # if not needs_complex:
            #     print("[Validation] No complex rules, simple validation passed")
            #     return simple_result
            #
            # print("[Validation] Simple validation passed, checking complex rules with GPT-4o")

        # TIER 2: Use GPT-4o for complex validation with timeout handling
        try:
            # Simplified validation prompt - less context, faster processing
            validation_prompt = f"""Validate ONLY the fields in the answers against the rules.

CRITICAL: Only validate fields that appear in the answers JSON below. Do NOT validate other fields.

## Answers to Validate
```json
{json.dumps(answers, indent=2)}
```

## Validation Rules (apply only to fields in answers)
```json
{json.dumps(execution_plan.get("validation_rules", {}), indent=2)}
```

Return JSON: {{"is_valid": true/false, "errors": [], "warnings": []}}

For errors/warnings: {{"field": "field_id", "message": "error text", "severity": "error"}}

Remember: ONLY return errors for fields that are in the answers JSON above."""

            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": validation_prompt}],
                temperature=0.1,
                max_tokens=300,
                timeout=10,  # Reduced to 10 seconds
                response_format={"type": "json_object"}
            )

            validation_result = json.loads(response.choices[0].message.content)

            # Normalize field_id to field for Pydantic compatibility
            for error in validation_result.get("errors", []):
                if "field_id" in error and "field" not in error:
                    error["field"] = error.pop("field_id")
            for warning in validation_result.get("warnings", []):
                if "field_id" in warning and "field" not in warning:
                    warning["field"] = warning.pop("field_id")

            print("[Validation] GPT-4o validation completed successfully")
            return validation_result

        except (APITimeoutError, APIConnectionError, Exception) as e:
            # FALLBACK: If GPT-4o validation times out or fails, accept the answers
            # Simple validation already passed, so we know basic constraints are met
            print(f"[Validation] GPT-4o validation failed ({type(e).__name__}: {str(e)}), falling back to simple validation result")
            return {
                "is_valid": True,
                "errors": [],
                "warnings": [{
                    "field": "_system",
                    "message": "Advanced validation temporarily unavailable, using basic validation",
                    "severity": "warning"
                }]
            }

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
        current_question: Optional[Dict] = None,
        collected_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate progress information.

        IMPORTANT: Dynamically calculates total steps including both:
        - Base question_sequence questions
        - Conditional questions that have been triggered based on user answers

        Args:
            execution_plan: The execution plan
            answered_question_ids: Questions answered so far
            current_question: The current question being asked
            collected_data: User answers collected so far (for checking trigger conditions)

        Returns:
            Progress information dictionary
        """
        question_sequence = execution_plan.get("question_sequence", [])
        conditional_questions = execution_plan.get("conditional_questions", [])

        # Start with base questions
        total_questions = len(question_sequence)

        # Count triggered conditional questions
        # A conditional question is triggered if its trigger condition is met
        if collected_data is None:
            collected_data = {}

        for cond_q in conditional_questions:
            trigger_field = cond_q.get("triggered_by_field")
            trigger_condition = cond_q.get("trigger_condition", {})

            # Check if trigger condition is met
            if trigger_field and trigger_field in answered_question_ids:
                # Check if the answer matches the trigger condition
                for field, expected_value in trigger_condition.items():
                    actual_value = collected_data.get(field)
                    # Match if answer equals expected value (case-insensitive for strings)
                    if actual_value and str(actual_value).lower() == str(expected_value).lower():
                        total_questions += 1
                        break

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
