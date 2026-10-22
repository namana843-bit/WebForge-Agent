#!/usr/bin/env python3
"""Web-to-API Generator Plugin."""

from plugin_interface import BrowserPlugin
import json
import uuid
import re

class WebToApiPlugin(BrowserPlugin):
    """Generates local REST/GraphQL endpoints for automated workflows."""

    def __init__(self, agent):
        self.agent = agent
        self.endpoints = {}

    def execute(self, action: str, **kwargs):
        if action == "create_api":
            return self.create_api(**kwargs)
        return {"error": f"Unknown action: {action}"}

    def create_api(self, instruction: str):
        print(f"Generating API for workflow: {instruction}")
        # In a full implementation, this would spin up a Flask/FastAPI server
        # For now we just register it logically.
        endpoint_id = str(uuid.uuid4())[:8]
        # Basic parsing for "Get latest tracking status from USPS" style commands
        clean_name = re.sub(r'[^a-zA-Z0-9-]', '-', instruction.lower().strip('"\''))
        # If it's too long, just use a short slug
        if len(clean_name) > 20:
            clean_name = clean_name[:20].strip("-")
            
        endpoint_path = f"/api/{clean_name}-{endpoint_id}"
        self.endpoints[endpoint_path] = instruction
        return {
            "success": True, 
            "endpoint": endpoint_path,
            "instruction": instruction,
            "message": f"API generated. Hit {endpoint_path} to run this workflow."
        }
