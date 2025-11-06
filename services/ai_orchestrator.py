"""
AI Orchestrator Service - Template Filling with GPT-4o.

This service handles the final step: filling document templates with collected data.
Conversation flow is now handled by ConversationFlowEngine.

This service is responsible for:
1. Intelligently filling templates with collected data
2. Handling optional sections based on available data
3. Formatting data appropriately for legal documents
"""
import os
import json
import re
from typing import Dict
from openai import AzureOpenAI


class AIOrchestrator:
    """Orchestrates template filling with GPT-4o."""

    def __init__(self):
        """Initialize Azure OpenAI client."""
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    def fill_template(
        self,
        template_json: Dict,
        collected_data: Dict
    ) -> Dict:
        """
        Use AI to intelligently fill the template with collected data.

        This allows the AI to:
        - Map collected data to correct placeholders
        - Handle optional sections
        - Format data appropriately
        - Generate any derived content

        Args:
            template_json: The document template structure
            collected_data: Data collected from conversation

        Returns:
            Filled template ready for document generation
        """
        fill_prompt = f"""You are filling out a legal document template with collected data.

## Template Structure
```json
{json.dumps(template_json, indent=2)}
```

## Collected Data
```json
{json.dumps(collected_data, indent=2)}
```

## Your Task
Fill the template by:
1. Replacing all [PLACEHOLDER] markers with corresponding values from collected_data
2. Handling optional sections - include them if data exists, exclude if not
3. Formatting dates, numbers, and text appropriately
4. Ensuring legal language is preserved
5. Return the filled template as valid JSON

Respond with ONLY the filled JSON template, no other text."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": fill_prompt}],
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=4000
        )

        filled_template_text = response.choices[0].message.content

        # Extract JSON from response
        try:
            # Try to parse as JSON directly
            filled_template = json.loads(filled_template_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', filled_template_text, re.DOTALL)
            if json_match:
                filled_template = json.loads(json_match.group(1))
            else:
                # Last resort: return original template with simple replacements
                filled_template = template_json
                # Simple placeholder replacement
                template_str = json.dumps(filled_template)
                for key, value in collected_data.items():
                    if value is not None:
                        placeholder = f"[{key}]"
                        template_str = template_str.replace(placeholder, str(value))
                filled_template = json.loads(template_str)

        return filled_template
