"""
Template Service - Manages loading templates from Azure Blob Storage.

Templates and prompt configurations are stored as JSON files in Azure Blob Storage.
This service handles reading them and caching for performance.
"""
import os
import json
from typing import Dict, Tuple, Optional
from azure.storage.blob import BlobServiceClient


class TemplateService:
    """Service for loading templates from Azure Blob Storage."""

    def __init__(self):
        """Initialize Azure Blob Storage client."""
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "templates")

        # Ensure container exists
        try:
            self.blob_service_client.create_container(self.container_name)
        except Exception:
            # Container already exists
            pass

        # Simple in-memory cache to avoid repeated blob fetches
        # In production, could use Redis or similar
        self._cache: Dict[str, Dict] = {}

    def load_template(self, blob_path: str) -> Dict:
        """
        Load a template JSON from blob storage.

        Args:
            blob_path: Path to blob (e.g., "templates/employment-agreement/template.json")

        Returns:
            Dict containing the parsed JSON
        """
        # Check cache first
        if blob_path in self._cache:
            return self._cache[blob_path]

        # Fetch from blob storage
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_path
        )

        # Download and parse JSON
        blob_data = blob_client.download_blob()
        json_text = blob_data.readall().decode('utf-8')
        parsed_json = json.loads(json_text)

        # Cache it
        self._cache[blob_path] = parsed_json

        return parsed_json

    def load_template_and_prompt(
        self,
        template_blob_path: str,
        prompt_blob_path: str
    ) -> Tuple[Dict, Dict]:
        """
        Load both template and prompt configuration from blob storage.

        Args:
            template_blob_path: Path to template JSON blob
            prompt_blob_path: Path to prompt config JSON blob

        Returns:
            Tuple of (template_json, prompt_config_json)
        """
        template_json = self.load_template(template_blob_path)
        prompt_config_json = self.load_template(prompt_blob_path)

        return template_json, prompt_config_json

    def upload_template(
        self,
        template_name: str,
        template_json: Dict,
        prompt_config_json: Dict
    ) -> Tuple[str, str]:
        """
        Upload a new template and prompt configuration to blob storage.

        This is used by admin tools to add new templates.

        Args:
            template_name: Unique name for the template (e.g., "employment-agreement")
            template_json: The template structure
            prompt_config_json: The conversation configuration

        Returns:
            Tuple of (template_blob_path, prompt_blob_path)
        """
        # Create blob paths
        template_blob_path = f"templates/{template_name}/template.json"
        prompt_blob_path = f"templates/{template_name}/prompt_config.json"

        # Upload template JSON
        template_blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=template_blob_path
        )
        template_blob_client.upload_blob(
            json.dumps(template_json, indent=2),
            overwrite=True
        )

        # Upload prompt config JSON
        prompt_blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=prompt_blob_path
        )
        prompt_blob_client.upload_blob(
            json.dumps(prompt_config_json, indent=2),
            overwrite=True
        )

        # Clear cache for these paths
        self._cache.pop(template_blob_path, None)
        self._cache.pop(prompt_blob_path, None)

        return template_blob_path, prompt_blob_path

    def list_templates_in_blob_storage(self) -> list:
        """
        List all templates available in blob storage.

        Returns:
            List of template names (folder names under templates/)
        """
        container_client = self.blob_service_client.get_container_client(self.container_name)

        # Get all blobs with prefix "templates/"
        blobs = container_client.list_blobs(name_starts_with="templates/")

        # Extract unique template names (folder names)
        template_names = set()
        for blob in blobs:
            # blob.name format: "templates/{template_name}/file.json"
            parts = blob.name.split('/')
            if len(parts) >= 2 and parts[0] == "templates":
                template_names.add(parts[1])

        return sorted(list(template_names))

    def clear_cache(self):
        """Clear the in-memory cache. Useful for testing or manual refresh."""
        self._cache.clear()

    def delete_template(self, template_name: str):
        """
        Delete a template from blob storage.

        Args:
            template_name: Name of the template to delete
        """
        template_blob_path = f"templates/{template_name}/template.json"
        prompt_blob_path = f"templates/{template_name}/prompt_config.json"

        # Delete both blobs
        for blob_path in [template_blob_path, prompt_blob_path]:
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=blob_path
                )
                blob_client.delete_blob()
                self._cache.pop(blob_path, None)
            except Exception:
                # Blob might not exist
                pass
