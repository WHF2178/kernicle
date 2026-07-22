"""
Background session management for Kernicle.
Sprint 5: Implements start/status/stop commands and background capture loop.

Design:
- Uses a simple PID file + state.json for coordination
- Background process runs capture loop
- Stop command sets a flag in state.json, process checks and exits cleanly
"""

import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import subprocess


@dataclass
class SessionConfig:
    """Configuration for a background session."""
    capture_interval: int = 60  # seconds between log captures
    push_interval: int = 600  # seconds between archive creations
    duration: Optional[int] = None  # total duration, None = run until stopped
    kernel_only: bool = False  # False = --all
    git_backup: bool = False  # whether to push to git
    max_archives: int = 20  # retention: keep only N most recent archives
    range_spec: str = "last:5m"  # time range for each capture
    name: Optional[str] = None  # custom session name prefix
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionConfig":
        """Create from dictionary."""
        return cls(
            capture_interval=data.get("capture_interval", 60),
            push_interval=data.get("push_interval", 600),
            duration=data.get("duration"),
            kernel_only=data.get("kernel_only", False),
            git_backup=data.get("git_backup", False),
            max_archives=data.get("max_archives", 20),
            range_spec=data.get("range_spec", "last:5m"),
            name=data.get("name"),
        )


@dataclass
class SessionState:
    """State of a running background session."""
    pid: int
    started_utc: str
    config: SessionConfig
    current_session_id: Optional[str] = None
    last_capture_utc: Optional[str] = None
    last_archive_utc: Optional[str] = None
    capture_count: int = 0
    archive_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stop_requested: bool = False
    stopped_utc: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pid": self.pid,
            "started_utc": self.started_utc,
            "config": self.config.to_dict(),
            "current_session_id": self.current_session_id,
            "last_capture_utc": self.last_capture_utc,
            "last_archive_utc": self.last_archive_utc,
            "capture_count": self.capture_count,
            "archive_count": self.archive_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "stop_requested": self.stop_requested,
            "stopped_utc": self.stopped_utc,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """Create from dictionary."""
        return cls(
            pid=data["pid"],
            started_utc=data["started_utc"],
            config=SessionConfig.from_dict(data.get("config", {})),
            current_session_id=data.get("current_session_id"),
            last_capture_utc=data.get("last_capture_utc"),
            last_archive_utc=data.get("last_archive_utc"),
            capture_count=data.get("capture_count", 0),
            archive_count=data.get("archive_count", 0),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            stop_requested=data.get("stop_requested", False),
            stopped_utc=data.get("stopped_utc"),
        )


class SessionManager:
    """Manages background session state and coordination."""
    
    def __init__(self, session_dir: Path):
        """
        Initialize session manager.
        
        Args:
            session_dir: Directory for session state files (e.g., ~/.kernicle/session)
        """
        self.session_dir = session_dir
        self.state_path = session_dir / "state.json"
        self.pid_path = session_dir / "kernicle.pid"
    
    def ensure_directory(self) -> None:
        """Create session directory if it doesn't exist."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def read_state(self) -> Optional[SessionState]:
        """
        Read current session state from file.
        
        Returns:
            SessionState if file exists and is valid, None otherwise
        """
        if not self.state_path.exists():
            return None
        
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return SessionState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def write_state(self, state: SessionState) -> None:
        """
        Write session state to file.
        
        Args:
            state: Session state to write
        """
        self.ensure_directory()
        self.state_path.write_text(
            json.dumps(state.to_dict(), indent=2),
            encoding="utf-8"
        )
    
    def read_pid(self) -> Optional[int]:
        """
        Read PID from pid file.
        
        Returns:
            PID if file exists and contains valid int, None otherwise
        """
        if not self.pid_path.exists():
            return None
        
        try:
            return int(self.pid_path.read_text().strip())
        except (ValueError, IOError):
            return None
    
    def write_pid(self, pid: int) -> None:
        """Write PID to pid file."""
        self.ensure_directory()
        self.pid_path.write_text(str(pid))
    
    def remove_pid(self) -> None:
        """Remove PID file if it exists."""
        if self.pid_path.exists():
            self.pid_path.unlink()
    
    def is_process_running(self, pid: int) -> bool:
        """
        Check if a process with given PID is running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is running, False otherwise
        """
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def is_session_running(self) -> tuple[bool, Optional[SessionState]]:
        """
        Check if a background session is currently running.
        
        Returns:
            Tuple of (is_running, state if running else None)
        """
        state = self.read_state()
        pid = self.read_pid()
        
        if state is None or pid is None:
            return False, None
        
        if state.stop_requested and state.stopped_utc:
            # Session was stopped
            return False, state
        
        if not self.is_process_running(pid):
            # Process died unexpectedly
            return False, state
        
        return True, state
    
    def request_stop(self) -> bool:
        """
        Request the running session to stop.
        
        Returns:
            True if stop was requested, False if no session running
        """
        state = self.read_state()
        if state is None:
            return False
        
        state.stop_requested = True
        self.write_state(state)
        return True
    
    def cleanup_stale(self) -> None:
        """Clean up stale state/pid files from crashed sessions."""
        pid = self.read_pid()
        if pid is not None and not self.is_process_running(pid):
            # Process is not running, clean up files
            self.remove_pid()
            # Keep state.json for debugging, but mark as not running


def get_archives_total_size(archives_dir: Path) -> int:
    """
    Calculate total size of all archives in bytes.
    
    Args:
        archives_dir: Path to archives directory
        
    Returns:
        Total size in bytes
    """
    total = 0
    if not archives_dir.exists():
        return 0
    
    for item in archives_dir.iterdir():
        if item.is_file():
            total += item.stat().st_size
        elif item.is_dir():
            for f in item.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
    return total


def cleanup_archives_by_count(archives_dir: Path, max_count: int) -> list[str]:
    """
    Delete oldest archives to keep only max_count most recent.
    
    Args:
        archives_dir: Path to archives directory
        max_count: Maximum number of archives to keep
        
    Returns:
        List of deleted archive names
    """
    import shutil
    
    if not archives_dir.exists() or max_count <= 0:
        return []
    
    deleted = []
    
    # Get all session directories and zip files
    sessions = []
    zips = []
    
    for item in archives_dir.iterdir():
        if item.is_dir() and item.name.startswith("session-"):
            sessions.append(item)
        elif item.is_file() and item.suffix == ".zip" and item.stem.startswith("session-"):
            zips.append(item)
    
    # Sort by modification time, oldest first
    sessions.sort(key=lambda p: p.stat().st_mtime)
    zips.sort(key=lambda p: p.stat().st_mtime)
    
    # Delete excess sessions
    while len(sessions) > max_count:
        oldest = sessions.pop(0)
        try:
            shutil.rmtree(oldest)
            deleted.append(oldest.name)
        except Exception:
            pass
    
    # Delete excess zips (keep same count as sessions)
    while len(zips) > max_count:
        oldest = zips.pop(0)
        try:
            oldest.unlink()
            deleted.append(oldest.name)
        except Exception:
            pass
    
    return deleted


def cleanup_archives_by_size(archives_dir: Path, max_size_mb: int) -> list[str]:
    """
    Delete oldest archives until total size is under max_size_mb.
    
    Args:
        archives_dir: Path to archives directory
        max_size_mb: Maximum total size in megabytes
        
    Returns:
        List of deleted archive names
    """
    import shutil
    
    if not archives_dir.exists() or max_size_mb <= 0:
        return []
    
    deleted = []
    max_bytes = max_size_mb * 1024 * 1024
    
    while get_archives_total_size(archives_dir) > max_bytes:
        # Find oldest session
        sessions = [
            d for d in archives_dir.iterdir()
            if d.is_dir() and d.name.startswith("session-")
        ]
        
        if not sessions:
            break
        
        sessions.sort(key=lambda p: p.stat().st_mtime)
        oldest = sessions[0]
        
        # Delete session and its zip
        try:
            shutil.rmtree(oldest)
            deleted.append(oldest.name)
        except Exception:
            break
        
        # Also delete corresponding zip if exists
        zip_path = archives_dir / f"{oldest.name}.zip"
        if zip_path.exists():
            try:
                zip_path.unlink()
                deleted.append(zip_path.name)
            except Exception:
                pass
    
    return deleted


class BackgroundSession:
    """
    Runs the background capture loop.
    
    This class encapsulates the loop logic for testability.
    """
    
    def __init__(
        self,
        config: SessionConfig,
        archives_dir: Path,
        session_manager: SessionManager,
    ):
        """
        Initialize background session.
        
        Args:
            config: Session configuration
            archives_dir: Directory to store archives
            session_manager: Session manager for state coordination
        """
        self.config = config
        self.archives_dir = archives_dir
        self.session_manager = session_manager
        self.state: Optional[SessionState] = None
        
        # Accumulated logs between archives
        self.accumulated_kernel_logs: list[str] = []
        self.accumulated_system_logs: list[str] = []
        
        # Timing
        self.start_time: Optional[float] = None
        self.last_capture_time: float = 0
        self.last_archive_time: float = 0
        
        # Signal handling
        self._stop_requested = False
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def handle_signal(signum, frame):
            self._stop_requested = True
        
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    
    def should_stop(self) -> bool:
        """
        Check if the session should stop.
        
        Returns:
            True if stop is requested or duration exceeded
        """
        if self._stop_requested:
            return True
        
        # Check state file for stop request
        state = self.session_manager.read_state()
        if state and state.stop_requested:
            return True
        
        # Check duration
        if self.config.duration and self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed >= self.config.duration:
                return True
        
        return False
    
    def capture_logs(self) -> tuple[Optional[str], Optional[str]]:
        """
        Capture kernel and optionally system logs.
        
        Returns:
            Tuple of (kernel_logs, system_logs) or (None, None) on error
        """
        from kernicle.services.timeparse import parse_range
        from kernicle.services.journal import capture_kernel, capture_system
        
        try:
            time_range = parse_range(self.config.range_spec)
            
            kernel_result = capture_kernel(time_range.since_arg)
            kernel_logs = kernel_result.output if kernel_result.success else None
            
            system_logs = None
            if not self.config.kernel_only:
                system_result = capture_system(time_range.since_arg)
                system_logs = system_result.output if system_result.success else None
            
            return kernel_logs, system_logs
            
        except Exception as e:
            if self.state:
                self.state.errors.append(f"Capture error: {str(e)}")
                self.session_manager.write_state(self.state)
            return None, None
    
    def do_capture(self) -> None:
        """Perform a single log capture and accumulate."""
        kernel_logs, system_logs = self.capture_logs()
        
        if kernel_logs:
            self.accumulated_kernel_logs.append(kernel_logs)
        if system_logs:
            self.accumulated_system_logs.append(system_logs)
        
        if self.state:
            self.state.capture_count += 1
            self.state.last_capture_utc = datetime.now(timezone.utc).isoformat()
            self.session_manager.write_state(self.state)
        
        self.last_capture_time = time.time()
    
    def do_archive(self) -> Optional[Path]:
        """
        Create an archive from accumulated logs.
        
        Returns:
            Path to created archive, or None on failure
        """
        from kernicle.services.archive import create_session_archive
        from kernicle.services.timeparse import TimeRange
        from kernicle.services.gitbackup import is_git_available, backup_to_git, GitConfig
        from kernicle.config import config as kernicle_config
        
        if not self.accumulated_kernel_logs:
            return None
        
        try:
            # Create archive with custom name if configured
            archive = create_session_archive(self.archives_dir, name=self.config.name)
            
            # Combine accumulated logs
            kernel_content = "\n".join(self.accumulated_kernel_logs)
            archive.write_source("kernel", "journalctl-kernel.log", kernel_content)
            
            if self.accumulated_system_logs:
                system_content = "\n".join(self.accumulated_system_logs)
                archive.write_source("system", "journalctl-system.log", system_content)
            
            # Finalize analysis
            archive.finalize_analysis()
            archive.capture_metrics()
            
            # Write outputs
            archive.write_findings()
            archive.write_incidents()
            archive.write_metrics()
            
            # Create time range info for report
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg=self.config.range_spec,
                range_input=f"background-session ({self.config.range_spec})"
            )
            
            archive.write_report(
                time_range,
                kernel_only=self.config.kernel_only,
                kernel_result=None,
                system_result=None
            )
            archive.write_manifest(time_range, kernel_only=self.config.kernel_only)
            
            # Validate
            is_valid, errors = archive.validate_archive()
            if not is_valid and self.state:
                self.state.warnings.extend(errors)
            
            # Create ZIP
            zip_result = archive.create_zip()
            
            # Git backup if enabled and ZIP succeeded
            if self.config.git_backup and zip_result.success and zip_result.zip_path:
                if is_git_available():
                    # GitConfig uses default ~/.kernicle/git-backup/ if KERNICLE_GIT_REPO_DIR not set
                    git_config = GitConfig.from_env(kernicle_config.base_dir)
                    if git_config.is_configured():
                        git_result = backup_to_git(zip_result.zip_path, git_config)
                        # Log git result (archive already zipped, can't update manifest)
                        if not git_result.success and self.state:
                            self.state.errors.extend(git_result.errors)
                        if git_result.warnings and self.state:
                            self.state.warnings.extend(git_result.warnings)
                    else:
                        if self.state:
                            self.state.warnings.append(
                                "Git backup enabled but KERNICLE_GIT_REMOTE not set. "
                                "Set it to enable git backup: export KERNICLE_GIT_REMOTE=<your-repo-url>"
                            )
                else:
                    if self.state:
                        self.state.warnings.append("Git backup enabled but git is not available on system")
            
            # Update state
            if self.state:
                self.state.archive_count += 1
                self.state.last_archive_utc = datetime.now(timezone.utc).isoformat()
                self.state.current_session_id = archive.session_dir.name
                self.session_manager.write_state(self.state)
            
            # Clear accumulated logs
            self.accumulated_kernel_logs = []
            self.accumulated_system_logs = []
            
            self.last_archive_time = time.time()
            
            # Cleanup old archives
            cleanup_archives_by_count(self.archives_dir, self.config.max_archives)
            
            return archive.session_dir
            
        except Exception as e:
            if self.state:
                self.state.errors.append(f"Archive error: {str(e)}")
                self.session_manager.write_state(self.state)
            return None
    
    def run_loop(self) -> None:
        """
        Run the main capture/archive loop.
        
        This is the main entry point for the background process.
        """
        self.setup_signal_handlers()
        self.start_time = time.time()
        self.last_capture_time = self.start_time
        self.last_archive_time = self.start_time
        
        # Initialize state
        self.state = SessionState(
            pid=os.getpid(),
            started_utc=datetime.now(timezone.utc).isoformat(),
            config=self.config,
        )
        self.session_manager.write_state(self.state)
        self.session_manager.write_pid(os.getpid())
        
        # Initial capture
        self.do_capture()
        
        try:
            while not self.should_stop():
                current_time = time.time()
                
                # Check if capture is due
                if current_time - self.last_capture_time >= self.config.capture_interval:
                    self.do_capture()
                
                # Check if archive is due
                if current_time - self.last_archive_time >= self.config.push_interval:
                    self.do_archive()
                
                # Sleep a bit to avoid busy-waiting
                time.sleep(1)
            
            # Final archive before exit
            if self.accumulated_kernel_logs:
                self.do_archive()
            
        finally:
            # Mark as stopped
            if self.state:
                self.state.stopped_utc = datetime.now(timezone.utc).isoformat()
                self.session_manager.write_state(self.state)
            self.session_manager.remove_pid()
    
    def run_single_iteration(self) -> bool:
        """
        Run a single iteration of the loop (for testing).
        
        Returns:
            True if should continue, False if should stop
        """
        if self.start_time is None:
            self.start_time = time.time()
            self.last_capture_time = self.start_time
            self.last_archive_time = self.start_time
        
        if self.should_stop():
            return False
        
        current_time = time.time()
        
        if current_time - self.last_capture_time >= self.config.capture_interval:
            self.do_capture()
        
        if current_time - self.last_archive_time >= self.config.push_interval:
            self.do_archive()
        
        return True


def start_background_session(
    config: SessionConfig,
    archives_dir: Path,
    session_dir: Path,
) -> tuple[bool, str]:
    """
    Start a background session as a detached process.
    
    Args:
        config: Session configuration
        archives_dir: Directory to store archives
        session_dir: Directory for session state files
        
    Returns:
        Tuple of (success, message)
    """
    manager = SessionManager(session_dir)
    
    # Check if already running
    is_running, existing_state = manager.is_session_running()
    if is_running:
        return False, f"Session already running (PID: {existing_state.pid if existing_state else 'unknown'})"
    
    # Clean up any stale files
    manager.cleanup_stale()
    
    # Fork to create background process
    try:
        pid = os.fork()
    except OSError as e:
        return False, f"Failed to fork: {e}"
    
    if pid > 0:
        # Parent process - return success
        time.sleep(0.5)  # Give child time to start
        return True, f"Background session started (PID: {pid})"
    
    # Child process - become a daemon
    try:
        # Create new session
        os.setsid()
        
        # Fork again to prevent zombie
        pid2 = os.fork()
        if pid2 > 0:
            os._exit(0)
        
        # Close standard file descriptors
        sys.stdin.close()
        sys.stdout.close()
        sys.stderr.close()
        
        # Redirect to /dev/null
        null_fd = os.open(os.devnull, os.O_RDWR)
        os.dup2(null_fd, 0)
        os.dup2(null_fd, 1)
        os.dup2(null_fd, 2)
        
        # Run the background session
        session = BackgroundSession(config, archives_dir, manager)
        session.run_loop()
        
    except Exception:
        pass
    finally:
        os._exit(0)


def stop_background_session(session_dir: Path, timeout: int = 10) -> tuple[bool, str]:
    """
    Stop a running background session.
    
    Args:
        session_dir: Directory containing session state files
        timeout: Seconds to wait for graceful shutdown
        
    Returns:
        Tuple of (success, message)
    """
    manager = SessionManager(session_dir)
    
    is_running, state = manager.is_session_running()
    if not is_running:
        return False, "No session is currently running"
    
    pid = manager.read_pid()
    if pid is None:
        return False, "Cannot read session PID"
    
    # Request stop via state file
    manager.request_stop()
    
    # Wait for graceful shutdown
    for _ in range(timeout):
        if not manager.is_process_running(pid):
            return True, "Session stopped successfully"
        time.sleep(1)
    
    # Force kill if still running
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        manager.remove_pid()
        return True, "Session forcefully terminated"
    except OSError:
        return True, "Session stopped"


def get_session_status(session_dir: Path) -> dict:
    """
    Get current session status.
    
    Args:
        session_dir: Directory containing session state files
        
    Returns:
        Dictionary with session status information
    """
    manager = SessionManager(session_dir)
    
    is_running, state = manager.is_session_running()
    
    if state is None:
        return {
            "running": False,
            "message": "No session state found",
        }
    
    return {
        "running": is_running,
        "pid": state.pid,
        "started_utc": state.started_utc,
        "stopped_utc": state.stopped_utc,
        "last_capture_utc": state.last_capture_utc,
        "last_archive_utc": state.last_archive_utc,
        "capture_count": state.capture_count,
        "archive_count": state.archive_count,
        "current_session_id": state.current_session_id,
        "config": state.config.to_dict(),
        "errors": state.errors,
        "warnings": state.warnings,
        "stop_requested": state.stop_requested,
    }
