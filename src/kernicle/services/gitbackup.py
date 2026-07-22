"""
Git backup integration for Kernicle archives.
Sprint 4: Pushes ZIP archives to a private Git repository.

Uses system git command via subprocess - no heavy dependencies.
Handles missing git gracefully.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class GitConfig:
    """Configuration for Git backup."""
    remote_url: Optional[str] = None
    repo_dir: Optional[Path] = None
    branch: str = "main"
    
    @classmethod
    def from_env(cls, base_dir: Path) -> "GitConfig":
        """
        Create GitConfig from environment variables.
        
        Environment variables:
            KERNICLE_GIT_REMOTE: Git remote URL
            KERNICLE_GIT_REPO_DIR: Local repo directory (default: ~/.kernicle/git-backup)
            KERNICLE_GIT_BRANCH: Branch name (default: main)
        """
        remote_url = os.environ.get("KERNICLE_GIT_REMOTE")
        repo_dir_str = os.environ.get("KERNICLE_GIT_REPO_DIR")
        branch = os.environ.get("KERNICLE_GIT_BRANCH", "main")
        
        if repo_dir_str:
            repo_dir = Path(repo_dir_str).expanduser()
        else:
            repo_dir = base_dir / "git-backup"
        
        return cls(
            remote_url=remote_url,
            repo_dir=repo_dir,
            branch=branch,
        )
    
    def is_configured(self) -> bool:
        """Check if Git backup is properly configured."""
        return self.remote_url is not None and len(self.remote_url) > 0


@dataclass
class GitResult:
    """Result of Git backup operation."""
    success: bool
    committed: bool = False
    pushed: bool = False
    commit_hash: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for manifest inclusion."""
        return {
            "success": self.success,
            "committed": self.committed,
            "pushed": self.pushed,
            "commit_hash": self.commit_hash,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def is_git_available() -> bool:
    """Check if git command is available on the system."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _run_git(args: list[str], cwd: Path, timeout: int = 30) -> tuple[bool, str, str]:
    """
    Run a git command.
    
    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def init_repo(config: GitConfig) -> tuple[bool, list[str]]:
    """
    Initialize or verify the Git repository.
    
    Args:
        config: Git configuration
        
    Returns:
        Tuple of (success, list of errors/warnings)
    """
    errors = []
    
    if config.repo_dir is None:
        return False, ["Git repo directory not configured"]
    
    repo_dir = config.repo_dir
    archives_dir = repo_dir / "archives"
    
    # Create directories
    try:
        archives_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, [f"Failed to create repo directory: {e}"]
    
    git_dir = repo_dir / ".git"
    
    # Initialize if not already a git repo
    if not git_dir.exists():
        success, stdout, stderr = _run_git(["init"], repo_dir)
        if not success:
            return False, [f"git init failed: {stderr}"]
        
        # Set initial branch name
        success, _, stderr = _run_git(["checkout", "-b", config.branch], repo_dir)
        if not success and "already exists" not in stderr:
            errors.append(f"Branch setup warning: {stderr}")
        
        # Add remote origin if configured
        if config.remote_url:
            success, _, stderr = _run_git(
                ["remote", "add", "origin", config.remote_url],
                repo_dir
            )
            if not success and "already exists" not in stderr:
                errors.append(f"Remote setup warning: {stderr}")
        
        # Create initial .gitignore
        gitignore_path = repo_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("# Kernicle Git Backup\n*.tmp\n.DS_Store\n")
        
        # Create README
        readme_path = repo_dir / "README.md"
        if not readme_path.exists():
            readme_path.write_text(
                "# Kernicle Archives Backup\n\n"
                "This repository contains ZIP archives from Kernicle log captures.\n\n"
                "Generated automatically by `kernicle push --git`\n"
            )
    else:
        # Verify remote is set correctly
        if config.remote_url:
            success, stdout, _ = _run_git(["remote", "get-url", "origin"], repo_dir)
            if not success:
                # Add remote if missing
                _run_git(["remote", "add", "origin", config.remote_url], repo_dir)
            elif stdout != config.remote_url:
                # Update remote URL
                _run_git(["remote", "set-url", "origin", config.remote_url], repo_dir)
    
    return True, errors


def backup_to_git(zip_path: Path, config: GitConfig) -> GitResult:
    """
    Backup a ZIP archive to Git repository.
    
    Args:
        zip_path: Path to the ZIP file to backup
        config: Git configuration
        
    Returns:
        GitResult with operation status
    """
    result = GitResult(success=False)
    
    # Check prerequisites
    if not is_git_available():
        result.errors.append("Git is not installed or not in PATH")
        return result
    
    if not config.is_configured():
        result.errors.append("Git remote URL not configured. Set KERNICLE_GIT_REMOTE environment variable.")
        return result
    
    if config.repo_dir is None:
        result.errors.append("Git repo directory not configured")
        return result
    
    if not zip_path.exists():
        result.errors.append(f"ZIP file does not exist: {zip_path}")
        return result
    
    # Initialize/verify repo
    init_success, init_errors = init_repo(config)
    if not init_success:
        result.errors.extend(init_errors)
        return result
    result.warnings.extend(init_errors)
    
    # At this point repo_dir is guaranteed to be non-None
    repo_dir: Path = config.repo_dir
    archives_dir = repo_dir / "archives"
    
    # Copy ZIP to repo
    dest_path = archives_dir / zip_path.name
    try:
        shutil.copy2(zip_path, dest_path)
    except Exception as e:
        result.errors.append(f"Failed to copy ZIP to repo: {e}")
        return result
    
    # Stage the file
    success, _, stderr = _run_git(["add", str(dest_path.relative_to(repo_dir))], repo_dir)
    if not success:
        result.errors.append(f"git add failed: {stderr}")
        return result
    
    # Check if there are changes to commit
    success, stdout, _ = _run_git(["status", "--porcelain"], repo_dir)
    if not stdout.strip():
        result.warnings.append("No changes to commit")
        result.success = True
        return result
    
    # Commit
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    commit_msg = f"Kernicle archive {timestamp}"
    
    success, _, stderr = _run_git(["commit", "-m", commit_msg], repo_dir)
    if not success:
        result.errors.append(f"git commit failed: {stderr}")
        return result
    
    result.committed = True
    
    # Get commit hash
    success, stdout, _ = _run_git(["rev-parse", "HEAD"], repo_dir)
    if success:
        result.commit_hash = stdout[:8]  # Short hash
    
    # Pull latest changes first (to avoid push conflicts)
    _run_git(["pull", "--rebase", "origin", config.branch], repo_dir, timeout=30)
    
    # Push to remote
    success, _, stderr = _run_git(
        ["push", "-u", "origin", config.branch],
        repo_dir,
        timeout=60  # Allow more time for push
    )
    
    if success:
        result.pushed = True
        result.success = True
    else:
        # Push failed but commit succeeded - partial success
        result.warnings.append(f"Push failed (commit preserved locally): {stderr}")
        result.success = True  # Still mark as success since local backup exists
    
    return result


def get_git_status(config: GitConfig) -> dict:
    """
    Get current Git repository status.
    
    Args:
        config: Git configuration
        
    Returns:
        Dictionary with status information
    """
    status = {
        "git_available": is_git_available(),
        "configured": config.is_configured(),
        "repo_exists": False,
        "remote_url": config.remote_url,
        "branch": config.branch,
        "repo_dir": str(config.repo_dir) if config.repo_dir else None,
    }
    
    if config.repo_dir and (config.repo_dir / ".git").exists():
        status["repo_exists"] = True
        
        # Get current branch
        success, stdout, _ = _run_git(["branch", "--show-current"], config.repo_dir)
        if success:
            status["current_branch"] = stdout
        
        # Get commit count
        success, stdout, _ = _run_git(["rev-list", "--count", "HEAD"], config.repo_dir)
        if success:
            status["commit_count"] = int(stdout)
    
    return status
