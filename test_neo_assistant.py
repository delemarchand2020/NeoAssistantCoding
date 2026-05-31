import os
import shutil
import zipfile
import unittest
from src.config import NeoConfig
from src.repo_scanner import scan_repository, parse_gitignore, should_exclude
from src.session_manager import SessionManager

class TestNeoAssistant(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for testing
        self.test_dir = os.path.abspath("test_workspace")
        self.sessions_dir = os.path.abspath("test_sessions")
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        # Create a sample file structure in test_workspace
        self.file1_path = os.path.join(self.test_dir, "main.py")
        with open(self.file1_path, "w") as f:
            f.write("print('Hello World')\n")
            
        self.file2_path = os.path.join(self.test_dir, "README.md")
        with open(self.file2_path, "w") as f:
            f.write("# Project title\nSome description here.\n")
            
        # Create a folder to ignore
        self.ignore_dir = os.path.join(self.test_dir, "node_modules")
        os.makedirs(self.ignore_dir, exist_ok=True)
        with open(os.path.join(self.ignore_dir, "package.json"), "w") as f:
            f.write("{}")
            
        # Create a gitignore file
        self.gitignore_path = os.path.join(self.test_dir, ".gitignore")
        with open(self.gitignore_path, "w") as f:
            f.write("*.log\nnode_modules/\n")
            
        # Create a file that matches gitignore
        self.log_file_path = os.path.join(self.test_dir, "app.log")
        with open(self.log_file_path, "w") as f:
            f.write("Log entries here.\n")

    def tearDown(self):
        # Clean up temporary test files
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.sessions_dir, ignore_errors=True)

    def test_gitignore_parsing_and_scanner(self):
        # Test gitignore parsing
        patterns = parse_gitignore(self.test_dir)
        self.assertIn("*.log", patterns)
        self.assertIn("node_modules/", patterns)
        
        # Test file exclusions
        self.assertTrue(should_exclude("app.log", patterns))
        self.assertTrue(should_exclude("node_modules/package.json", patterns, is_dir=False))
        self.assertFalse(should_exclude("main.py", patterns))
        
        # Test repository scanner
        files_dict, tree_str = scan_repository(self.test_dir)
        
        # main.py and README.md should be in output
        self.assertIn("main.py", files_dict)
        self.assertIn("README.md", files_dict)
        
        # app.log and node_modules contents should be excluded
        self.assertNotIn("app.log", files_dict)
        self.assertNotIn("node_modules/package.json", files_dict)
        
        # Check that main.py has correct content
        self.assertEqual(files_dict["main.py"], "print('Hello World')\n")

    def test_session_backup_and_rollback(self):
        # Initialize session manager
        sm = SessionManager(self.sessions_dir, self.test_dir)
        
        # Test context saving
        sm.save_context("Sample context text")
        self.assertTrue(os.path.exists(os.path.join(sm.session_path, "session_context.txt")))
        
        # Test backup
        sm.backup_repository()
        
        # Check files exist in backup directory
        self.assertTrue(os.path.exists(os.path.join(sm.backup_path, "main.py")))
        self.assertTrue(os.path.exists(os.path.join(sm.backup_path, "README.md")))
        self.assertFalse(os.path.exists(os.path.join(sm.backup_path, "app.log"))) # Excluded
        
        # Simulate script modification/creation
        # 1. Modify main.py
        with open(self.file1_path, "w") as f:
            f.write("print('Modified')\n")
        # 2. Create a new file
        new_file = os.path.join(self.test_dir, "new_module.py")
        with open(new_file, "w") as f:
            f.write("new content\n")
            
        # Assert modifications are present before rollback
        with open(self.file1_path, "r") as f:
            self.assertEqual(f.read(), "print('Modified')\n")
        self.assertTrue(os.path.exists(new_file))
        
        # Perform rollback
        success = sm.rollback_repository()
        self.assertTrue(success)
        
        # Verify main.py is restored to original content
        with open(self.file1_path, "r") as f:
            self.assertEqual(f.read(), "print('Hello World')\n")
            
        # Verify new_module.py is deleted
        self.assertFalse(os.path.exists(new_file))

    def test_session_archiving(self):
        sm = SessionManager(self.sessions_dir, self.test_dir)
        sm.save_context("Context data")
        sm.save_plan("# Plan markdown")
        sm.save_script("echo 'Hello'", "sh")
        sm.save_summary("# Summary markdown")
        
        # Archive session
        zip_path = sm.archive_session()
        self.assertIsNotNone(zip_path)
        self.assertTrue(os.path.exists(zip_path))
        
        # Verify contents of zip file
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            namelist = zipf.namelist()
            self.assertIn("session_context.txt", namelist)
            self.assertIn("plan.md", namelist)
            self.assertIn("script.sh", namelist)
            self.assertIn("summary.md", namelist)

if __name__ == "__main__":
    unittest.main()
