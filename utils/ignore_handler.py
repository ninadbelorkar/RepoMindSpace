import os
import pathspec

DEFAULT_IGNORES = [
    ".git/",
    ".svn/",
    ".hg/",
    "node_modules/",
    "__pycache__/",
    "*.pyc",
    "venv/",
    "env/",
    ".env",
    ".DS_Store",
    "build/",
    "dist/",
    "*.lock",
    "package-lock.json",
    "yarn.lock"
]

class IgnoreHandler:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.spec = self._load_ignore_spec()

    def _load_ignore_spec(self) -> pathspec.PathSpec:
        """Loads default ignores and parses the repository's .gitignore if it exists."""
        patterns = list(DEFAULT_IGNORES)
        
        gitignore_path = os.path.join(self.repo_path, ".gitignore")
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    patterns.extend(f.readlines())
            except Exception as e:
                print(f"Warning: Failed to read .gitignore at {gitignore_path}: {e}")
                
        return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, patterns)

    def is_ignored(self, file_path: str) -> bool:
        """
        Checks if a given absolute file path should be ignored.
        Converts the absolute path to a relative path against the repo root before checking.
        """
        try:
            rel_path = os.path.relpath(file_path, self.repo_path)
            # pathspec expects POSIX paths even on Windows
            posix_path = rel_path.replace(os.sep, '/')
            return self.spec.match_file(posix_path)
        except ValueError:
            # If relpath fails (e.g. paths on different drives on Windows), default to ignoring it
            return True
