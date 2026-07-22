"""
Tests for background session management.
Sprint 5: Tests for state file read/write, cleanup logic, and session management.
"""

import json
import os
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from kernicle.services.session import (
    SessionConfig,
    SessionState,
    SessionManager,
    BackgroundSession,
    cleanup_archives_by_count,
    cleanup_archives_by_size,
    get_archives_total_size,
    get_session_status,
)


class TestSessionConfig:
    """Tests for SessionConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = SessionConfig()
        
        assert config.capture_interval == 60
        assert config.push_interval == 600
        assert config.duration is None
        assert config.kernel_only is False
        assert config.git_backup is False
        assert config.max_archives == 20
        assert config.range_spec == "last:5m"
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = SessionConfig(
            capture_interval=30,
            push_interval=300,
            duration=1800,
            kernel_only=True,
            git_backup=True,
            max_archives=10,
            range_spec="last:10m"
        )
        
        assert config.capture_interval == 30
        assert config.push_interval == 300
        assert config.duration == 1800
        assert config.kernel_only is True
        assert config.git_backup is True
        assert config.max_archives == 10
        assert config.range_spec == "last:10m"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = SessionConfig(capture_interval=45)
        d = config.to_dict()
        
        assert d["capture_interval"] == 45
        assert d["push_interval"] == 600
        assert "duration" in d
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "capture_interval": 120,
            "push_interval": 900,
            "max_archives": 5,
        }
        config = SessionConfig.from_dict(data)
        
        assert config.capture_interval == 120
        assert config.push_interval == 900
        assert config.max_archives == 5
        # Defaults should still apply
        assert config.kernel_only is False
    
    def test_from_dict_missing_keys(self):
        """Test from_dict with missing keys uses defaults."""
        config = SessionConfig.from_dict({})
        
        assert config.capture_interval == 60
        assert config.max_archives == 20


class TestSessionState:
    """Tests for SessionState dataclass."""
    
    def test_creation(self):
        """Test creating a session state."""
        config = SessionConfig()
        state = SessionState(
            pid=12345,
            started_utc="2025-01-01T00:00:00+00:00",
            config=config,
        )
        
        assert state.pid == 12345
        assert state.started_utc == "2025-01-01T00:00:00+00:00"
        assert state.capture_count == 0
        assert state.archive_count == 0
        assert state.errors == []
        assert state.stop_requested is False
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = SessionConfig(capture_interval=30)
        state = SessionState(
            pid=12345,
            started_utc="2025-01-01T00:00:00+00:00",
            config=config,
            capture_count=5,
        )
        
        d = state.to_dict()
        
        assert d["pid"] == 12345
        assert d["capture_count"] == 5
        assert d["config"]["capture_interval"] == 30
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "pid": 99999,
            "started_utc": "2025-01-02T10:00:00+00:00",
            "config": {"capture_interval": 90},
            "capture_count": 10,
            "archive_count": 2,
            "errors": ["error1"],
        }
        state = SessionState.from_dict(data)
        
        assert state.pid == 99999
        assert state.capture_count == 10
        assert state.config.capture_interval == 90
        assert len(state.errors) == 1


class TestSessionManager:
    """Tests for SessionManager class."""
    
    @pytest.fixture
    def session_dir(self, tmp_path):
        """Create a temporary session directory."""
        sess_dir = tmp_path / "session"
        sess_dir.mkdir()
        return sess_dir
    
    @pytest.fixture
    def manager(self, session_dir):
        """Create a SessionManager instance."""
        return SessionManager(session_dir)
    
    def test_read_state_no_file(self, manager):
        """Test reading state when file doesn't exist."""
        assert manager.read_state() is None
    
    def test_write_and_read_state(self, manager):
        """Test writing and reading state."""
        config = SessionConfig(capture_interval=45)
        state = SessionState(
            pid=12345,
            started_utc="2025-01-01T00:00:00+00:00",
            config=config,
            capture_count=3,
        )
        
        manager.write_state(state)
        
        loaded = manager.read_state()
        assert loaded is not None
        assert loaded.pid == 12345
        assert loaded.capture_count == 3
        assert loaded.config.capture_interval == 45
    
    def test_read_invalid_state(self, manager, session_dir):
        """Test reading invalid JSON state file."""
        state_path = session_dir / "state.json"
        state_path.write_text("not valid json{{{")
        
        assert manager.read_state() is None
    
    def test_write_and_read_pid(self, manager):
        """Test writing and reading PID."""
        manager.write_pid(12345)
        assert manager.read_pid() == 12345
    
    def test_read_pid_no_file(self, manager):
        """Test reading PID when file doesn't exist."""
        assert manager.read_pid() is None
    
    def test_remove_pid(self, manager):
        """Test removing PID file."""
        manager.write_pid(12345)
        assert manager.read_pid() == 12345
        
        manager.remove_pid()
        assert manager.read_pid() is None
    
    def test_is_process_running_current(self, manager):
        """Test checking if current process is running."""
        assert manager.is_process_running(os.getpid()) is True
    
    def test_is_process_running_invalid(self, manager):
        """Test checking if invalid PID is running."""
        # Use a very high PID that's unlikely to exist
        assert manager.is_process_running(999999999) is False
    
    def test_is_session_running_no_state(self, manager):
        """Test is_session_running with no state."""
        is_running, state = manager.is_session_running()
        assert is_running is False
        assert state is None
    
    def test_is_session_running_stopped(self, manager):
        """Test is_session_running with stopped session."""
        config = SessionConfig()
        state = SessionState(
            pid=12345,
            started_utc="2025-01-01T00:00:00+00:00",
            config=config,
            stop_requested=True,
            stopped_utc="2025-01-01T01:00:00+00:00",
        )
        manager.write_state(state)
        manager.write_pid(12345)
        
        is_running, loaded = manager.is_session_running()
        assert is_running is False
    
    def test_request_stop(self, manager):
        """Test requesting session stop."""
        config = SessionConfig()
        state = SessionState(
            pid=12345,
            started_utc="2025-01-01T00:00:00+00:00",
            config=config,
        )
        manager.write_state(state)
        
        result = manager.request_stop()
        assert result is True
        
        loaded = manager.read_state()
        assert loaded.stop_requested is True
    
    def test_request_stop_no_session(self, manager):
        """Test requesting stop when no session exists."""
        result = manager.request_stop()
        assert result is False


class TestCleanupByCount:
    """Tests for cleanup_archives_by_count function."""
    
    @pytest.fixture
    def archives_dir(self, tmp_path):
        """Create archives directory with test sessions."""
        archives = tmp_path / "archives"
        archives.mkdir()
        return archives
    
    def _create_session(self, archives_dir: Path, name: str, age_offset: int = 0):
        """Helper to create a mock session directory."""
        session = archives_dir / name
        session.mkdir()
        (session / "manifest.json").write_text('{"test": true}')
        
        # Create corresponding zip
        zip_path = archives_dir / f"{name}.zip"
        zip_path.write_bytes(b"PK\x03\x04" + b"\x00" * 50)
        
        # Set modification time
        mtime = time.time() - age_offset
        os.utime(session, (mtime, mtime))
        os.utime(zip_path, (mtime, mtime))
    
    def test_no_cleanup_under_limit(self, archives_dir):
        """Test that no cleanup happens when under limit."""
        self._create_session(archives_dir, "session-1", 100)
        self._create_session(archives_dir, "session-2", 50)
        
        deleted = cleanup_archives_by_count(archives_dir, max_count=5)
        
        assert len(deleted) == 0
        assert (archives_dir / "session-1").exists()
        assert (archives_dir / "session-2").exists()
    
    def test_cleanup_oldest(self, archives_dir):
        """Test that oldest sessions are deleted."""
        self._create_session(archives_dir, "session-1", 300)  # oldest
        self._create_session(archives_dir, "session-2", 200)
        self._create_session(archives_dir, "session-3", 100)  # newest
        
        deleted = cleanup_archives_by_count(archives_dir, max_count=2)
        
        # Should have deleted session-1 (oldest)
        assert "session-1" in deleted
        assert not (archives_dir / "session-1").exists()
        assert (archives_dir / "session-2").exists()
        assert (archives_dir / "session-3").exists()
    
    def test_cleanup_zips(self, archives_dir):
        """Test that corresponding ZIP files are also deleted."""
        self._create_session(archives_dir, "session-1", 200)
        self._create_session(archives_dir, "session-2", 100)
        
        deleted = cleanup_archives_by_count(archives_dir, max_count=1)
        
        assert "session-1" in deleted
        # ZIP should also be deleted
        assert not (archives_dir / "session-1.zip").exists()
    
    def test_cleanup_empty_dir(self, archives_dir):
        """Test cleanup on empty directory."""
        deleted = cleanup_archives_by_count(archives_dir, max_count=5)
        assert len(deleted) == 0
    
    def test_cleanup_nonexistent_dir(self, tmp_path):
        """Test cleanup on non-existent directory."""
        nonexistent = tmp_path / "does-not-exist"
        deleted = cleanup_archives_by_count(nonexistent, max_count=5)
        assert len(deleted) == 0


class TestCleanupBySize:
    """Tests for cleanup_archives_by_size function."""
    
    @pytest.fixture
    def archives_dir(self, tmp_path):
        """Create archives directory."""
        archives = tmp_path / "archives"
        archives.mkdir()
        return archives
    
    def _create_session_with_size(self, archives_dir: Path, name: str, size_kb: int, age_offset: int = 0):
        """Helper to create a mock session with specific size."""
        session = archives_dir / name
        session.mkdir()
        
        # Create file with specified size
        data_file = session / "data.log"
        data_file.write_bytes(b"x" * (size_kb * 1024))
        
        # Set modification time
        mtime = time.time() - age_offset
        os.utime(session, (mtime, mtime))
    
    def test_no_cleanup_under_limit(self, archives_dir):
        """Test no cleanup when under size limit."""
        self._create_session_with_size(archives_dir, "session-1", 100)
        
        deleted = cleanup_archives_by_size(archives_dir, max_size_mb=1)
        
        assert len(deleted) == 0
    
    def test_cleanup_when_over_limit(self, archives_dir):
        """Test cleanup when over size limit."""
        self._create_session_with_size(archives_dir, "session-1", 500, 200)  # oldest
        self._create_session_with_size(archives_dir, "session-2", 500, 100)
        self._create_session_with_size(archives_dir, "session-3", 500, 50)   # newest
        
        # Total is ~1.5MB, limit to 1MB
        deleted = cleanup_archives_by_size(archives_dir, max_size_mb=1)
        
        # Should have deleted oldest first
        assert "session-1" in deleted
        assert not (archives_dir / "session-1").exists()


class TestGetArchivesTotalSize:
    """Tests for get_archives_total_size function."""
    
    def test_empty_dir(self, tmp_path):
        """Test size of empty directory."""
        archives = tmp_path / "archives"
        archives.mkdir()
        
        assert get_archives_total_size(archives) == 0
    
    def test_nonexistent_dir(self, tmp_path):
        """Test size of non-existent directory."""
        assert get_archives_total_size(tmp_path / "missing") == 0
    
    def test_with_files(self, tmp_path):
        """Test size with files."""
        archives = tmp_path / "archives"
        archives.mkdir()
        
        # Create 1KB file
        (archives / "test.txt").write_bytes(b"x" * 1024)
        
        size = get_archives_total_size(archives)
        assert size == 1024


class TestBackgroundSession:
    """Tests for BackgroundSession class."""
    
    @pytest.fixture
    def session_setup(self, tmp_path):
        """Set up session components."""
        archives_dir = tmp_path / "archives"
        archives_dir.mkdir()
        
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        
        config = SessionConfig(
            capture_interval=1,
            push_interval=5,
            duration=10,
            kernel_only=True,
        )
        
        manager = SessionManager(session_dir)
        
        return {
            "archives_dir": archives_dir,
            "session_dir": session_dir,
            "config": config,
            "manager": manager,
        }
    
    def test_should_stop_by_signal(self, session_setup):
        """Test should_stop when signal received."""
        session = BackgroundSession(
            session_setup["config"],
            session_setup["archives_dir"],
            session_setup["manager"],
        )
        
        assert session.should_stop() is False
        session._stop_requested = True
        assert session.should_stop() is True
    
    def test_should_stop_by_state_file(self, session_setup):
        """Test should_stop when state file has stop_requested."""
        session = BackgroundSession(
            session_setup["config"],
            session_setup["archives_dir"],
            session_setup["manager"],
        )
        
        # Write state with stop_requested
        state = SessionState(
            pid=os.getpid(),
            started_utc="2025-01-01T00:00:00+00:00",
            config=session_setup["config"],
            stop_requested=True,
        )
        session_setup["manager"].write_state(state)
        
        assert session.should_stop() is True
    
    def test_should_stop_by_duration(self, session_setup):
        """Test should_stop when duration exceeded."""
        config = SessionConfig(duration=1)  # 1 second duration
        session = BackgroundSession(
            config,
            session_setup["archives_dir"],
            session_setup["manager"],
        )
        
        session.start_time = time.time() - 2  # Started 2 seconds ago
        assert session.should_stop() is True
    
    @patch('kernicle.services.journal.capture_kernel')
    @patch('kernicle.services.timeparse.parse_range')
    def test_capture_logs(self, mock_parse, mock_capture, session_setup):
        """Test capturing logs."""
        mock_parse.return_value = MagicMock(since_arg="test")
        mock_capture.return_value = MagicMock(success=True, output="kernel logs")
        
        session = BackgroundSession(
            session_setup["config"],
            session_setup["archives_dir"],
            session_setup["manager"],
        )
        
        kernel, system = session.capture_logs()
        
        assert kernel == "kernel logs"
        assert system is None  # kernel_only=True


class TestGetSessionStatus:
    """Tests for get_session_status function."""
    
    def test_no_session(self, tmp_path):
        """Test status when no session exists."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        
        status = get_session_status(session_dir)
        
        assert status["running"] is False
        assert "No session state found" in status["message"]
    
    def test_with_session(self, tmp_path):
        """Test status with active session."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        
        manager = SessionManager(session_dir)
        config = SessionConfig(capture_interval=30)
        state = SessionState(
            pid=os.getpid(),
            started_utc="2025-01-01T00:00:00+00:00",
            config=config,
            capture_count=5,
            archive_count=1,
        )
        manager.write_state(state)
        manager.write_pid(os.getpid())
        
        status = get_session_status(session_dir)
        
        assert status["running"] is True
        assert status["pid"] == os.getpid()
        assert status["capture_count"] == 5
        assert status["config"]["capture_interval"] == 30
