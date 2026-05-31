# NeoAssistantCoding

**NeoAssistantCoding** is a secure, autonomous local AI coding assistant built in plain Python (standard library only, no agentic frameworks) enforcing a "Human-in-the-Loop" validation mechanism for every critical file or command operation.

## Architecture

The project is structured as follows:
- `neo_assistant.py`: Command Line Interface (CLI) entry point and interactive orchestration loops.
- `config.json`: Configuration settings for LLMs, shell preferences, and file scanning constraints.
- `skills/`: System markdown prompts/instructions (`neo_assistant_coding.md`, `architect.md`, `developer.md`, `git.md`).
- `src/`: Core Python modules:
  - `config.py`: Loads and parses configurations.
  - `repo_scanner.py`: Scans the target workspace recursively while respecting `.gitignore`.
  - `llm_client.py`: Calls Gemini or OpenAI API over direct `urllib.request` (zero dependencies).
  - `session_manager.py`: Handles session workspace setups, target backups, rollbacks, and ZIP archiving.
  - `executor.py`: Safely runs generated shell scripts.

---

## Configuration

1. Open [config.json](file:///c:/Users/delem/ProjetsAntigravity/NeoAssistantCoding/config.json).
2. Configure settings:
   - `llm.provider`: `"gemini"` or `"openai"`
   - `llm.api_key`: Your API key (or `"ENV"` to automatically resolve from environment variables `GEMINI_API_KEY` / `OPENAI_API_KEY`).
   - `llm.model`: Model name (e.g. `"gemini-2.5-flash"`).
   - `shell`: Shell environment to run scripts (`"powershell"` or `"bash"`).

To run with a **Local LLM** (e.g. Qwen2.5-Coder-1.5B):
1. Run the local model (see [LocalLLM/README_LOCAL.md](file:///c:/Users/delem/ProjetsAntigravity/LocalLLM/README_LOCAL.md)).
2. Launch the assistant using `--config config_local.json`.

---

## Usage

Run the assistant from your terminal by specifying the mode, target repository directory, and config file:

```bash
python neo_assistant.py --mode [architect|developer|git] --repo [target_directory]
```

### Options

- `--mode` (Required): Mode to operate:
  - `architect`: Design directory layouts, empty file structures, module interfaces, and skeletons (no implementation logic).
  - `developer`: Write, modify, and implement functional code.
  - `git`: Manage branch checkouts, commits, and status checkups.
- `--repo` (Required): Path to the target repository. Use the `projects/` directory to avoid workspace pollution.
- `--goal` (Optional): Session goal description (e.g. `"Design a modular calculator"`). If omitted, you will be prompted.
- `--goal-file` (Optional): Path to a markdown file containing the goal description.
- `--config` (Optional): Path to a custom config JSON file (defaults to `config.json`).

---

## Safety Features (Human-in-the-Loop)

1. **Phase 1: Action Plan Approval**: The LLM writes a markdown plan (`plan.md`). You can review it, comment to request modifications, or type `OK` to approve.
2. **Phase 2: Script Approval**: The LLM writes an installation script (`script.ps1` or `script.sh`). The script MUST consist of file-writing commands (not program logic itself). Review it, comment to update, or type `OK` to approve.
3. **Phase 3: Backup and Execute**: The target repository is backed up. The script is executed.
4. **Phase 4: Rollback Prompt**: You are prompted to keep modifications or roll back to the original backup state.
5. **Phase 5: Archive**: A ZIP archive containing context logs, the plan, the script, the backup, and a session summary is saved in `sessions/`.

---

## Testing

Run the automated test suite to verify code integrations:

```bash
python -m unittest test_neo_assistant.py
```
