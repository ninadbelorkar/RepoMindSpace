import os
from typing import List, Dict, Any
from .ignore_handler import IgnoreHandler

MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

class LocalParser:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        if not os.path.isdir(self.repo_path):
            raise ValueError(f"Path is not a valid directory: {self.repo_path}")
        self.ignore_handler = IgnoreHandler(self.repo_path)

    def _is_binary_or_unreadable(self, file_path: str) -> bool:
        """
        Attempts to open the file and read a chunk as UTF-8.
        If it raises a UnicodeDecodeError, we consider it binary/unreadable.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
            return False
        except UnicodeDecodeError:
            return True
        except Exception:
            return True # Fallback for permission errors etc.

    def _get_language(self, ext: str) -> str:
        """Naive extension to language mapper. Can be expanded."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".txt": "text",
            ".sh": "bash",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".ts": "typescript"
        }
        return ext_map.get(ext.lower(), "unknown")

    def parse(self) -> List[Dict[str, Any]]:
        """
        Walks the directory tree, filters files, and extracts content.
        Returns a list of dictionaries representing the parsed files.
        """
        parsed_files = []

        for root, dirs, files in os.walk(self.repo_path):
            # Prune ignored directories from traversal
            dirs[:] = [d for d in dirs if not self.ignore_handler.is_ignored(os.path.join(root, d))]

            for file in files:
                file_path = os.path.join(root, file)
                
                # 1. Check ignore rules
                if self.ignore_handler.is_ignored(file_path):
                    continue

                # 2. Check file size
                try:
                    size = os.path.getsize(file_path)
                    if size > MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue

                # 3. Check if binary
                if self._is_binary_or_unreadable(file_path):
                    continue

                # 4. Extract content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    _, ext = os.path.splitext(file_path)
                    
                    parsed_files.append({
                        "path": rel_path.replace(os.sep, '/'),
                        "extension": ext,
                        "language": self._get_language(ext),
                        "size": size,
                        "content": content
                    })
                except Exception as e:
                    print(f"Skipping {file_path} due to read error: {e}")

        return parsed_files
