import os
import shutil
import zipfile
from datetime import datetime
from src.repo_scanner import parse_gitignore, should_exclude

class SessionManager:
    def __init__(self, sessions_dir, repo_path):
        self.sessions_dir = sessions_dir
        self.repo_path = os.path.abspath(repo_path)
        self.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.session_path = os.path.join(sessions_dir, self.session_id)
        self.backup_path = os.path.join(self.session_path, "backup")
        
        # Ensure directories exist
        os.makedirs(self.session_path, exist_ok=True)
        
    def save_context(self, context_str):
        path = os.path.join(self.session_path, "session_context.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(context_str)
        return path

    def save_plan(self, plan_str):
        path = os.path.join(self.session_path, "plan.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(plan_str)
        return path

    def save_script(self, script_str, extension):
        filename = f"script.{extension}"
        path = os.path.join(self.session_path, filename)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(script_str)
        return path

    def save_summary(self, summary_str):
        path = os.path.join(self.session_path, "summary.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(summary_str)
        return path

    def backup_repository(self):
        """Backs up all files in the target repository to the session backup dir, respecting exclusions."""
        if not os.path.exists(self.repo_path):
            return
            
        os.makedirs(self.backup_path, exist_ok=True)
        gitignore_patterns = parse_gitignore(self.repo_path)
        
        # Walk and copy files
        for root, dirs, files in os.walk(self.repo_path):
            # Prune excluded directories
            for d in list(dirs):
                full_dir_path = os.path.join(root, d)
                rel_dir_path = os.path.relpath(full_dir_path, self.repo_path)
                if should_exclude(rel_dir_path, gitignore_patterns, is_dir=True):
                    dirs.remove(d)
                    
            for file in files:
                full_file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(full_file_path, self.repo_path)
                
                if should_exclude(rel_file_path, gitignore_patterns, is_dir=False):
                    continue
                    
                # Create destination directory structure
                dest_file_path = os.path.join(self.backup_path, rel_file_path)
                os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                
                # Copy file
                try:
                    shutil.copy2(full_file_path, dest_file_path)
                except Exception as e:
                    print(f"Warning: Failed to backup {rel_file_path}: {e}")

    def rollback_repository(self):
        """Restores files from backup and removes any files created during the session."""
        if not os.path.exists(self.backup_path):
            print("No backup found to restore.")
            return False
            
        gitignore_patterns = parse_gitignore(self.repo_path)
        
        # 1. Identify files currently in the repo (not excluded)
        current_files = set()
        for root, dirs, files in os.walk(self.repo_path):
            for d in list(dirs):
                full_dir_path = os.path.join(root, d)
                rel_dir_path = os.path.relpath(full_dir_path, self.repo_path)
                if should_exclude(rel_dir_path, gitignore_patterns, is_dir=True):
                    dirs.remove(d)
            for file in files:
                full_file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(full_file_path, self.repo_path)
                if not should_exclude(rel_file_path, gitignore_patterns, is_dir=False):
                    current_files.add(rel_file_path.replace('\\', '/'))
                    
        # 2. Identify files in the backup
        backup_files = set()
        for root, dirs, files in os.walk(self.backup_path):
            for file in files:
                full_file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(full_file_path, self.backup_path)
                backup_files.add(rel_file_path.replace('\\', '/'))
                
        # 3. Restore all backed up files (overwrite modifications)
        for rel_file in backup_files:
            src = os.path.join(self.backup_path, rel_file)
            dest = os.path.join(self.repo_path, rel_file)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                shutil.copy2(src, dest)
            except Exception as e:
                print(f"Error restoring {rel_file}: {e}")
                
        # 4. Remove files that were created by the script (exist in repo but not in backup)
        created_files = current_files - backup_files
        for rel_file in created_files:
            file_to_delete = os.path.join(self.repo_path, rel_file)
            try:
                if os.path.exists(file_to_delete):
                    os.remove(file_to_delete)
                    # Clean up empty parent directories if any
                    parent = os.path.dirname(file_to_delete)
                    while parent != self.repo_path:
                        if not os.listdir(parent):
                            os.rmdir(parent)
                            parent = os.path.dirname(parent)
                        else:
                            break
            except Exception as e:
                print(f"Error removing created file {rel_file}: {e}")
                
        return True

    def archive_session(self):
        """Archives the session folder into a zip file."""
        zip_filename = f"{self.session_id}.zip"
        zip_path = os.path.join(self.sessions_dir, zip_filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.session_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.session_path)
                        zipf.write(full_path, rel_path)
            return zip_path
        except Exception as e:
            print(f"Error creating zip archive: {e}")
            return None
