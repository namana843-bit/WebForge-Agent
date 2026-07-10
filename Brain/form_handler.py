#!/usr/bin/env python3
"""Intelligent Form Handler Plugin for auto-filling and validating forms."""

import json
from plugin_interface import BrowserPlugin

class FormHandlerPlugin(BrowserPlugin):
    """Plugin to auto-fill complex web forms using smart field detection and validation."""

    def __init__(self, agent):
        self.agent = agent

    def execute(self, action: str, **kwargs):
        if action == "smart_fill":
            form_data = kwargs.get("form_data", {})
            if isinstance(form_data, str):
                try:
                    form_data = json.loads(form_data)
                except Exception as e:
                    return {"error": f"Failed to parse form data JSON: {e}"}
            return self.smart_fill(form_data)
        elif action == "smart_fill_nl":
            instruction = kwargs.get("instruction")
            if not instruction:
                return {"error": "instruction is required"}
            return self.smart_fill_nl(instruction)
        else:
            return {"error": f"Unknown action: {action}"}

    def smart_fill_nl(self, instruction: str):
        """Converts a natural language instruction into key-value pairs and fills the form."""
        prompt = (
            f"Convert the following instruction into a clean JSON dictionary matching form fields: '{instruction}'. "
            "Return ONLY a valid JSON object. Do not include markdown code block syntax (```json) or conversational text."
        )
        print("Parsing natural language form request...")
        resp = self.agent.page_agent.understand(prompt)
        
        extracted_text = ""
        if isinstance(resp, dict) and "result" in resp:
            extracted_text = resp["result"]
        elif isinstance(resp, str):
            extracted_text = resp
            
        cleaned_text = extracted_text.strip()
        import re
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
            cleaned_text = re.sub(r"\n```$", "", cleaned_text)
            cleaned_text = cleaned_text.strip()
            
        try:
            form_data = json.loads(cleaned_text)
        except Exception as e:
            return {"error": f"Failed to parse extracted JSON from instruction: {e}. Raw response: {extracted_text}"}
            
        return self.smart_fill(form_data)

    def smart_fill(self, form_data: dict):
        """Auto-fills input fields on the page based on keys matching input labels/names/attributes."""
        # Convert form data to escaped JSON string
        data_json = json.dumps(form_data)
        
        js_code = f"""
        (async () => {{
            const data = {data_json};
            const results = {{}};
            const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
            
            for (const input of inputs) {{
                if (['submit', 'button', 'hidden', 'image'].includes(input.type)) continue;
                
                let matchedKey = null;
                const attributes = [
                    input.name,
                    input.id,
                    input.placeholder,
                    input.getAttribute('aria-label'),
                    input.labels ? Array.from(input.labels).map(l => l.innerText).join(' ') : ''
                ].map(val => (val || '').toLowerCase().trim());
                
                for (const key of Object.keys(data)) {{
                    const keyLower = key.toLowerCase();
                    if (attributes.some(attr => attr.includes(keyLower) || keyLower.includes(attr))) {{
                        matchedKey = key;
                        break;
                    }}
                }}
                
                if (matchedKey) {{
                    input.focus();
                    if (input.tagName === 'SELECT') {{
                        const val = String(data[matchedKey]).toLowerCase();
                        const option = Array.from(input.options).find(opt => 
                            opt.value.toLowerCase() === val || opt.text.toLowerCase().includes(val)
                        );
                        if (option) {{
                            input.value = option.value;
                        }} else {{
                            input.value = data[matchedKey];
                        }}
                    }} else if (input.type === 'checkbox') {{
                        input.checked = !!data[matchedKey];
                    }} else if (input.type === 'radio') {{
                        if (input.value.toLowerCase() === String(data[matchedKey]).toLowerCase()) {{
                            input.checked = true;
                        }}
                    }} else {{
                        input.value = data[matchedKey];
                    }}
                    
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    input.blur();
                    
                    results[matchedKey] = {{
                        field: input.name || input.id || input.placeholder || input.type,
                        value: data[matchedKey],
                        valid: input.checkValidity ? input.checkValidity() : true,
                        validationMessage: input.validationMessage || ''
                    }};
                }}
            }}
            return results;
        }})()
        """
        print("Executing smart fill inside active page...")
        res = self.agent.bridge.execute("evaluate", code=js_code)
        return res
