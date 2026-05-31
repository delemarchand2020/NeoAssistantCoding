import os
import json

DEFAULT_CONFIG_PATH = "config.json"

class NeoConfig:
    def __init__(self, config_path=None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.data = {}
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found at: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            try:
                self.data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in config file: {e}")
        
        # Resolve key attributes with sensible defaults
        self.llm = self.data.get("llm", {})
        self.provider = self.llm.get("provider", "gemini").lower()
        
        # API Key Resolution
        api_key = self.llm.get("api_key", "ENV")
        if api_key == "ENV" or not api_key:
            env_var = "GEMINI_API_KEY" if self.provider == "gemini" else "OPENAI_API_KEY"
            self.api_key = os.environ.get(env_var, "")
        else:
            self.api_key = api_key
            
        self.model = self.llm.get("model", "gemini-2.5-flash")
        self.api_url = self.llm.get("api_url", "https://generativelanguage.googleapis.com/v1beta/models")
        
        # Shell preferences: default to powershell on Windows, bash on others, or use config
        self.shell = self.data.get("shell")
        if not self.shell:
            self.shell = "powershell" if os.name == 'nt' else "bash"
        self.shell = self.shell.lower()
        
        # Direct paths and constraints
        self.skills_dir = self.data.get("skills_dir", "./skills")
        self.sessions_dir = self.data.get("sessions_dir", "./sessions")
        self.max_file_size_kb = self.data.get("max_file_size_kb", 100)
        self.max_context_chars = self.data.get("max_context_chars", 50000)

    def validate(self):
        if not self.api_key:
            raise ValueError(
                f"LLM API key is missing. Please set it in {self.config_path} or "
                f"via environment variables (GEMINI_API_KEY / OPENAI_API_KEY)."
            )
        if self.shell not in ["powershell", "bash", "cmd", "ps"]:
            raise ValueError(f"Unsupported shell option: {self.shell}. Must be 'powershell' or 'bash'.")
