import os
import fnmatch

DEFAULT_EXCLUDES = {
    '.git', '.svn', '.hg', '__pycache__', 'node_modules', '.gemini', 
    'sessions', '.idea', '.vscode', '.pytest_cache', '.venv', 'venv'
}

def parse_gitignore(repo_path):
    """Parses .gitignore file if it exists and returns a list of patterns."""
    gitignore_path = os.path.join(repo_path, '.gitignore')
    patterns = []
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                patterns.append(line)
    return patterns

def should_exclude(rel_path, patterns, is_dir=False):
    """Checks if a relative path (file or dir) matches any exclude pattern or defaults."""
    # Normalize to forward slashes
    rel_path_norm = rel_path.replace('\\', '/')
    parts = rel_path_norm.split('/')
    
    # Check default excludes against any part of the path
    for part in parts:
        if part in DEFAULT_EXCLUDES:
            return True
            
    # Check gitignore patterns
    for pattern in patterns:
        # Normalize pattern
        pat = pattern.replace('\\', '/')
        
        # Handle trailing slash indicating directory match
        pat_is_dir_only = pat.endswith('/')
        if pat_is_dir_only:
            pat = pat[:-1]
            if not is_dir:
                # If the pattern is directory-only, and this is a file, skip
                # (Unless a parent directory was already matched)
                pass
                
        # Matching logic
        if '/' not in pat:
            # Matches filename in any directory
            for part in parts:
                if fnmatch.fnmatch(part, pat):
                    return True
        else:
            # Matches relative to root
            # Strip leading slash for matching
            match_pat = pat.lstrip('/')
            # If the pattern is a direct prefix or matches the full path
            if fnmatch.fnmatch(rel_path_norm, match_pat) or fnmatch.fnmatch(rel_path_norm, match_pat + '/*'):
                return True
                
    return False

def scan_repository(repo_path, max_file_size_kb=100):
    """
    Scans the repository directory recursively.
    Returns:
        files_dict: dict of {relative_path: file_content_or_truncated}
        tree_str: formatted string of directory tree structure
    """
    if not os.path.exists(repo_path):
        return {}, "Repository path does not exist."
        
    gitignore_patterns = parse_gitignore(repo_path)
    files_dict = {}
    tree_lines = []
    
    # Simple tree builder
    def build_tree(current_dir, prefix=""):
        try:
            entries = sorted(os.listdir(current_dir))
        except Exception as e:
            return
            
        # Filter entries
        filtered_entries = []
        for entry in entries:
            full_path = os.path.join(current_dir, entry)
            rel_path = os.path.relpath(full_path, repo_path)
            is_entry_dir = os.path.isdir(full_path)
            if not should_exclude(rel_path, gitignore_patterns, is_entry_dir):
                filtered_entries.append((entry, full_path, is_entry_dir))
                
        for i, (entry, full_path, is_entry_dir) in enumerate(filtered_entries):
            is_last = (i == len(filtered_entries) - 1)
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{entry}{'/' if is_entry_dir else ''}")
            
            if is_entry_dir:
                next_prefix = prefix + ("    " if is_last else "│   ")
                build_tree(full_path, next_prefix)

    build_tree(repo_path)
    tree_str = "\n".join(tree_lines)
    
    # Read file contents
    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to avoid walking down excluded directories
        for d in list(dirs):
            full_dir_path = os.path.join(root, d)
            rel_dir_path = os.path.relpath(full_dir_path, repo_path)
            if should_exclude(rel_dir_path, gitignore_patterns, is_dir=True):
                dirs.remove(d)
                
        for file in files:
            full_file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(full_file_path, repo_path)
            
            if should_exclude(rel_file_path, gitignore_patterns, is_dir=False):
                continue
                
            try:
                # Read content
                size_kb = os.path.getsize(full_file_path) / 1024.0
                if size_kb > max_file_size_kb:
                    # Truncate
                    with open(full_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = []
                        # Read first 300 lines or up to max size roughly
                        for _ in range(300):
                            l = f.readline()
                            if not l:
                                break
                            lines.append(l)
                        content = "".join(lines) + f"\n\n[... TRUNCATED: File size is {size_kb:.1f}KB, exceeding limit of {max_file_size_kb}KB ...]\n"
                else:
                    with open(full_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                files_dict[rel_file_path.replace('\\', '/')] = content
            except Exception as e:
                files_dict[rel_file_path.replace('\\', '/')] = f"[ERROR READING FILE: {e}]"
                
    return files_dict, tree_str

def format_context_for_llm(files_dict, tree_str):
    """Formats the scanned repository context as a markdown block."""
    context = []
    context.append("## Repository Tree Structure")
    context.append("```")
    context.append(tree_str if tree_str else "[Empty Directory]")
    context.append("```\n")
    
    context.append("## Repository File Contents")
    if not files_dict:
        context.append("(No files found or all excluded)\n")
    else:
        for rel_path, content in files_dict.items():
            context.append(f"### File: `{rel_path}`")
            # Determine appropriate markdown codeblock language if possible
            ext = os.path.splitext(rel_path)[1].lower().replace('.', '')
            lang = ext if ext in ['py', 'sh', 'ps1', 'json', 'md', 'yml', 'yaml', 'html', 'css', 'js'] else ''
            context.append(f"```{lang}")
            context.append(content)
            context.append("```\n")
            
    return "\n".join(context)
