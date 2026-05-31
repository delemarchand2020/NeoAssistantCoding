#!/usr/bin/env python
import os
import sys
import argparse
from src.config import NeoConfig
from src.repo_scanner import scan_repository, format_context_for_llm
from src.llm_client import LLMClient
from src.session_manager import SessionManager
from src.executor import execute_script

def load_skill_file(skills_dir, skill_name):
    path = os.path.join(skills_dir, f"{skill_name}.md")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Skill file not found at: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def clean_script_content(raw_content):
    """Strips markdown codeblock fences if present to get raw script code."""
    content = raw_content.strip()
    lines = content.split('\n')
    if len(lines) >= 2 and lines[0].startswith('```') and lines[-1].startswith('```'):
        return '\n'.join(lines[1:-1]).strip()
    # Sometimes it has a leading ```bash or ```powershell without trailing backticks
    if lines[0].startswith('```'):
        return '\n'.join(lines[1:]).strip()
    return content

def main():
    parser = argparse.ArgumentParser(description="NeoAssistantCoding - Secure AI Coding Assistant")
    parser.add_argument("--mode", required=True, choices=["architect", "developer", "git"], 
                        help="Assistant mode: architect (structure design), developer (coding), git (versioning)")
    parser.add_argument("--repo", required=True, 
                        help="Path to the target repository (can be an empty directory)")
    parser.add_argument("--goal", help="Goal description for the session")
    parser.add_argument("--goal-file", help="Path to a markdown file containing the goal")
    parser.add_argument("--config", default="config.json", help="Path to the JSON configuration file")
    
    args = parser.parse_args()
    
    # 1. Load config
    try:
        config = NeoConfig(args.config)
        config.validate()
    except Exception as e:
        print(f"[-] Configuration Error: {e}")
        sys.exit(1)
        
    # 2. Get goal
    goal = ""
    if args.goal:
        goal = args.goal
    elif args.goal_file:
        if os.path.exists(args.goal_file):
            with open(args.goal_file, 'r', encoding='utf-8') as f:
                goal = f.read()
        else:
            print(f"[-] Goal file not found: {args.goal_file}")
            sys.exit(1)
    else:
        # Prompt interactively
        print("[*] No goal specified. Please enter the goal below:")
        goal = input("> ").strip()
        if not goal:
            print("[-] Goal is empty. Exiting session.")
            sys.exit(1)
            
    # 3. Load skills
    try:
        common_skill = load_skill_file(config.skills_dir, "neo_assistant_coding")
        mode_skill = load_skill_file(config.skills_dir, args.mode)
    except Exception as e:
        print(f"[-] Error loading skill files: {e}")
        sys.exit(1)
        
    system_instruction = f"{common_skill}\n\n{mode_skill}"
    
    # 4. Scan Repository
    print(f"[*] Scanning target repository: {args.repo} ...")
    files_dict, tree_str = scan_repository(args.repo, config.max_file_size_kb)
    repo_context = format_context_for_llm(files_dict, tree_str)
    
    # 5. Initialize session
    print("[*] Initializing session workspace...")
    session = SessionManager(config.sessions_dir, args.repo)
    session.save_context(repo_context)
    
    llm = LLMClient(config)
    
    # Interactive history
    history = []
    
    # --- PHASE 1: GENERATION DU PLAN ---
    print("\n" + "="*50)
    print(f"[*] PHASE 1: ACTION PLAN DESIGN (Mode: {args.mode.upper()})")
    print("="*50)
    
    prompt = (
        f"Here is the current target repository context:\n\n{repo_context}\n\n"
        f"The goal of this session is:\n{goal}\n\n"
        f"Draft a detailed action plan in Markdown format to achieve this goal."
    )
    
    plan_path = ""
    while True:
        print("[*] Requesting action plan generation/update from LLM...")
        try:
            plan_response = llm.generate(system_instruction, history, prompt)
        except Exception as e:
            print(f"[-] LLM API Error: {e}")
            sys.exit(1)
            
        plan_path = session.save_plan(plan_response)
        
        # Windows clickable link format
        clickable_link = f"file:///{plan_path.replace('\\', '/')}"
        print(f"\n[+] Action plan updated.")
        print(f"[+] PLAN FILE LINK: {clickable_link}")
        print("\nEnter 'OK' to approve the plan, 'exit' to quit, or write your feedback to adjust the plan:")
        
        user_input = input("> ").strip()
        if user_input.lower() == 'exit':
            print("[*] Session closed by user. The current plan has been saved.")
            sys.exit(0)
        elif user_input.upper() == 'OK':
            print("[+] Action plan approved by user!")
            # Add to history to keep LLM synced
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": plan_response})
            break
        else:
            # Loop again with user feedback
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": plan_response})
            prompt = f"The user requested to adjust the action plan with the following feedback:\n{user_input}\n\nPlease update the action plan accordingly."

    # --- PHASE 2: GENERATION DU SCRIPT ---
    print("\n" + "="*50)
    print(f"[*] PHASE 2: GENERATION OF EXECUTION SCRIPT ({config.shell.upper()})")
    print("="*50)
    
    script_ext = "ps1" if config.shell in ["powershell", "ps"] else "sh"
    if config.shell == "cmd":
        script_ext = "bat"
        
    prompt = (
        f"The action plan has been approved by the user. "
        f"Now, generate a complete execution script in '{config.shell}' format to implement the planned changes. "
        f"CRITICAL: The script must strictly use shell commands (like New-Item, Set-Content, etc. in PowerShell or mkdir, cat << 'EOF', etc. in Bash) to write files and folders onto the filesystem. Do NOT implement the game or application logic within the shell script itself. "
        f"For example, if you are creating 'hangman.py', write a PowerShell command to create 'hangman.py' with the python content; do NOT implement the game in PowerShell. "
        f"The script must be fully automated and executable. "
        f"CRITICAL RULE: Return ONLY the raw shell script code. Do not include any conversational explanation before or after the code block."
    )
    
    script_path = ""
    while True:
        print("[*] Requesting execution script generation/update from LLM...")
        try:
            script_response = llm.generate(system_instruction, history, prompt)
        except Exception as e:
            print(f"[-] LLM API Error: {e}")
            sys.exit(1)
            
        cleaned_script = clean_script_content(script_response)
        script_path = session.save_script(cleaned_script, script_ext)
        
        clickable_link = f"file:///{script_path.replace('\\', '/')}"
        print(f"\n[+] Execution script updated.")
        print(f"[+] SCRIPT FILE LINK: {clickable_link}")
        print("\nEnter 'OK' to approve and execute the script, 'exit' to quit, or write your feedback to adjust the script:")
        
        user_input = input("> ").strip()
        if user_input.lower() == 'exit':
            print("[*] Session closed by user. The current script has been saved.")
            sys.exit(0)
        elif user_input.upper() == 'OK':
            print("[+] Script approved by user!")
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": script_response})
            break
        else:
            # Loop again with user feedback
            history.append({"role": "user", "text": prompt})
            history.append({"role": "model", "text": script_response})
            prompt = f"The user requested to adjust the execution script with the following feedback:\n{user_input}\n\nPlease update the script accordingly."

    # --- PHASE 3: BACKUP ET EXECUTION ---
    print("\n" + "="*50)
    print("[*] PHASE 3: BACKUP AND EXECUTION")
    print("="*50)
    
    print("[*] Creating a backup of the current target repository files...")
    session.backup_repository()
    print(f"[+] Backup created in: {session.backup_path}")
    
    print(f"[*] Executing script in the target repository ({args.repo})...")
    success, log_output = execute_script(script_path, args.repo, config.shell)
    
    if success:
        print("[+] The script executed successfully (Return code 0)!")
    else:
        print("[-] The script execution failed.")
        
    print("\n--- EXECUTION LOGS ---")
    print(log_output)
    print("----------------------\n")
    
    # Prompt for rollback
    print("Do you want to roll back the changes and restore the initial state? (yes/no - default: no)")
    rollback_choice = input("> ").strip().lower()
    if rollback_choice in ['o', 'oui', 'y', 'yes']:
        print("[*] Restoring repository from backup...")
        if session.rollback_repository():
            print("[+] Restoration completed successfully.")
        else:
            print("[-] Restoration failed.")
    else:
        print("[+] Changes kept.")

    # --- PHASE 4: ARCHIVAGE ---
    print("\n" + "="*50)
    print("[*] PHASE 4: SESSION ARCHIVING")
    print("="*50)
    
    print("[*] Requesting session summary from LLM...")
    summary_prompt = (
        f"The execution is now finished. Write a short summary in Markdown format "
        f"summarizing what was accomplished and the final status relative to the goal: '{goal}'."
    )
    try:
        summary_response = llm.generate(system_instruction, history, summary_prompt)
    except Exception as e:
        print(f"[-] Warning: Failed to generate summary via LLM ({e}). Using a generic summary.")
        summary_response = f"# Session Summary\n\nGoal: {goal}\nStatus: Completed"
        
    summary_path = session.save_summary(summary_response)
    print(f"[+] Summary saved in: {summary_path}")
    
    print("[*] Creating ZIP archive...")
    zip_path = session.archive_session()
    if zip_path:
        clickable_zip = f"file:///{zip_path.replace('\\', '/')}"
        print(f"[+] SESSION ARCHIVED SUCCESSFULLY!")
        print(f"[+] ZIP ARCHIVE LINK: {clickable_zip}")
    else:
        print("[-] Failed to create ZIP archive.")
        
    print("\n[*] NeoAssistantCoding finished. Thank you!")

if __name__ == "__main__":
    main()
