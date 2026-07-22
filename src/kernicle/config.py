"""
Configuration and settings management for Kernicle.
Handles directory creation and path management.

Sprint 4: Adds Git backup configuration support.
Sprint 5: Adds session management directories.
"""

import os
from pathlib import Path
from typing import Optional


class KernicleConfig:
    """Configuration manager for Kernicle."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            base_dir: Optional base directory. Defaults to ~/.kernicle
        """
        self.base_dir = base_dir or Path.home() / ".kernicle"
        self.archives_dir = self.base_dir / "archives"
        self.git_backup_dir = self.base_dir / "git-backup"
        self.session_dir = self.base_dir / "session"  # Sprint 5
        
    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.archives_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)  # Sprint 5
    
    def get_session_dir(self, session_name: str) -> Path:
        """
        Get path to a session directory.
        
        Args:
            session_name: Name of the session (e.g., session-20251230-120000)
            
        Returns:
            Path to the session directory
        """
        return self.archives_dir / session_name
    
    def list_sessions(self, limit: Optional[int] = None) -> list[Path]:
        """
        List session directories sorted by creation time (newest first).
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session directory paths
        """
        import re
        if not self.archives_dir.exists():
            return []
        
        # Match any directory ending with timestamp pattern: -YYYYMMDD-HHMMSS
        timestamp_pattern = re.compile(r'-\d{8}-\d{6}$')
        
        sessions = [
            d for d in self.archives_dir.iterdir()
            if d.is_dir() and timestamp_pattern.search(d.name)
        ]
        
        # Sort by modification time, newest first
        sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        if limit:
            sessions = sessions[:limit]
        
        return sessions
    
    # Sprint 4: Git configuration from environment
    @property
    def git_remote_url(self) -> Optional[str]:
        """Get Git remote URL from environment."""
        return os.environ.get("KERNICLE_GIT_REMOTE")
    
    @property
    def git_repo_dir(self) -> Path:
        """Get Git repo directory from environment or default."""
        env_dir = os.environ.get("KERNICLE_GIT_REPO_DIR")
        if env_dir:
            return Path(env_dir).expanduser()
        return self.git_backup_dir
    
    @property
    def git_branch(self) -> str:
        """Get Git branch from environment or default."""
        return os.environ.get("KERNICLE_GIT_BRANCH", "main")
    
    def is_git_configured(self) -> bool:
        """Check if Git backup is configured."""
        return self.git_remote_url is not None


# Global config instance
config = KernicleConfig()
