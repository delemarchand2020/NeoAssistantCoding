import urllib.request
import urllib.error
import json
import ssl

class LLMClient:
    def __init__(self, config):
        self.config = config
        self.provider = config.provider
        self.api_key = config.api_key
        self.model = config.model
        self.api_url = config.api_url

    def generate(self, system_instruction, history, prompt):
        """
        Sends a request to the LLM API.
        system_instruction: str (global instructions/skills)
        history: list of dicts {"role": "user"|"assistant"|"model", "text": "..."}
        prompt: str (the latest user message/input)
        Returns:
            The text response from the model.
        """
        # Allow running without API key if it's explicitly set to "none" for local endpoints
        is_none_key = self.api_key and self.api_key.lower() == "none"
        if (not self.api_key or not self.api_key.strip()) and not is_none_key:
            raise ValueError("API Key is missing. Please set it in config.json or environment variables.")
            
        if self.provider == "gemini":
            return self._call_gemini(system_instruction, history, prompt)
        elif self.provider == "openai":
            return self._call_openai(system_instruction, history, prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _call_gemini(self, system_instruction, history, prompt):
        # Build contents array with history
        contents = []
        for h in history:
            role = "user" if h["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": h["text"]}]
            })
            
        # Add current prompt
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Build request body
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2
            }
        }
        
        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
            
        # Call API
        url = f"{self.api_url}/{self.model}:generateContent?key={self.api_key}"
        
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        # Disable SSL verify issues in case user is on an enterprise network with intercepting certs (optional but helpful)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(req, context=ctx) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                
                # Check structure
                candidates = res_data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"Gemini API returned no candidates. Response: {res_data}")
                    
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    # Check if finishReason is safety/other
                    finish_reason = candidates[0].get("finishReason")
                    if finish_reason:
                        raise ValueError(f"Gemini API finished with reason: {finish_reason}")
                    raise ValueError(f"Gemini API returned empty parts. Response: {res_data}")
                    
                return parts[0].get("text", "")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"Gemini API Error (HTTP {e.code}): {error_body}")
        except Exception as e:
            raise RuntimeError(f"Error communicating with Gemini API: {e}")

    def _call_openai(self, system_instruction, history, prompt):
        # Build messages array
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
            
        for h in history:
            role = "user" if h["role"] == "user" else "assistant"
            messages.append({"role": role, "content": h["text"]})
            
        messages.append({"role": "user", "content": prompt})
        
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }
        
        headers = {'Content-Type': 'application/json'}
        if self.api_key and self.api_key.lower() != "none":
            headers['Authorization'] = f'Bearer {self.api_key}'
            
        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(body).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(req, context=ctx) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                choices = res_data.get("choices", [])
                if not choices:
                    raise ValueError(f"OpenAI API returned no choices. Response: {res_data}")
                return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"OpenAI API Error (HTTP {e.code}): {error_body}")
        except Exception as e:
            raise RuntimeError(f"Error communicating with OpenAI API: {e}")
