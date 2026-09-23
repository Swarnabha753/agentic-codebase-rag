"""
Clones a GitHub repo to a local temp dir and walks it for supported source files.
Supported languages for v1: Python, JavaScript, TypeScript.
"""
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

import git

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# Directories we never want to parse (deps, build artifacts, vcs internals)
IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".next", "target", "vendor", ".mypy_cache",
    "site-packages", "egg-info",
}


@dataclass
class SourceFile:
    abs_path: str
    rel_path: str
    language: str


def clone_repo(repo_url: str, dest_dir: str | None = None) -> str:
    """Clones repo_url to dest_dir (or a fresh temp dir) and returns the local path."""
    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="coderag_")
    else:
        os.makedirs(dest_dir, exist_ok=True)

    print(f"[clone] cloning {repo_url} -> {dest_dir}")
    git.Repo.clone_from(repo_url, dest_dir, depth=1)  # shallow clone: we only need current snapshot
    return dest_dir


def discover_source_files(root_dir: str) -> list[SourceFile]:
    """Walks root_dir and returns all supported source files, skipping ignored dirs."""
    results: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # prune ignored directories in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]

        for fname in filenames:
            ext = Path(fname).suffix
            if ext in SUPPORTED_EXTENSIONS:
                abs_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(abs_path, root_dir)
                results.append(SourceFile(
                    abs_path=abs_path,
                    rel_path=rel_path,
                    language=SUPPORTED_EXTENSIONS[ext],
                ))
    print(f"[clone] discovered {len(results)} source files under {root_dir}")
    return results


def _force_remove_readonly(func, path, exc_info):
    """shutil.rmtree error handler: clears the read-only bit and retries.
    Needed on Windows because git marks some .git/objects files read-only,
    which the default rmtree can't delete."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def cleanup_repo(local_path: str):
    """Removes the cloned repo directory once indexing is done."""
    shutil.rmtree(local_path, onexc=_force_remove_readonly)
