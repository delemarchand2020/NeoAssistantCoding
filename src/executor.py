import os
import subprocess

def execute_script(script_path, repo_path, shell_type="powershell"):
    """
    Executes a script in the target repository path using the specified shell.
    Returns:
        success (bool)
        output (str)
    """
    script_path = os.path.abspath(script_path)
    repo_path = os.path.abspath(repo_path)
    
    # Define execution commands
    shell_type = shell_type.lower()
    if shell_type in ["powershell", "ps"]:
        # PowerShell command with bypass for policy execution
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path]
    elif shell_type == "bash":
        # Bash command
        cmd = ["bash", script_path]
    elif shell_type == "cmd":
        cmd = ["cmd.exe", "/c", script_path]
    else:
        # Fallback to direct execution or default subprocess execution
        cmd = [script_path]

    try:
        # Run subprocess with repository as cwd
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            shell=True if shell_type == "bash" and os.name == 'nt' else False # bash on Windows needs shell=True sometimes
        )
        
        success = (result.returncode == 0)
        output = f"Stdout:\n{result.stdout}\n\nStderr:\n{result.stderr}"
        return success, output
    except Exception as e:
        return False, f"Failed to execute script: {e}"
