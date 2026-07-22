"""
Tests for Git backup functionality.
Sprint 4: Git integration with mocked subprocess.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from kernicle.services.gitbackup import (
    GitConfig,
    GitResult,
    is_git_available,
    init_repo,
    backup_to_git,
    _run_git,
)


class TestGitConfig:
    """Tests for GitConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = GitConfig()
        
        assert config.remote_url is None
        assert config.repo_dir is None
        assert config.branch == "main"
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = GitConfig(
            remote_url="git@github.com:user/repo.git",
            repo_dir=Path("/tmp/git-backup"),
            branch="backups"
        )
        
        assert config.remote_url == "git@github.com:user/repo.git"
        assert config.repo_dir == Path("/tmp/git-backup")
        assert config.branch == "backups"
    
    def test_is_configured_true(self):
        """Test is_configured when remote_url is set."""
        config = GitConfig(
            remote_url="git@github.com:user/repo.git",
            repo_dir=Path("/tmp/repo")
        )
        
        assert config.is_configured() is True
    
    def test_is_configured_false_no_remote(self):
        """Test is_configured when remote_url is missing."""
        config = GitConfig(repo_dir=Path("/tmp/repo"))
        
        assert config.is_configured() is False
    
    def test_is_configured_false_empty_remote(self):
        """Test is_configured when remote_url is empty string."""
        config = GitConfig(remote_url="", repo_dir=Path("/tmp/repo"))
        
        assert config.is_configured() is False
    
    @patch.dict('os.environ', {
        'KERNICLE_GIT_REMOTE': 'git@github.com:test/kernicle-backup.git',
        'KERNICLE_GIT_REPO_DIR': '/home/user/.kernicle/git-backup',
        'KERNICLE_GIT_BRANCH': 'archives'
    })
    def test_from_env(self, tmp_path):
        """Test creating GitConfig from environment variables."""
        config = GitConfig.from_env(tmp_path)
        
        assert config.remote_url == "git@github.com:test/kernicle-backup.git"
        assert config.repo_dir == Path("/home/user/.kernicle/git-backup")
        assert config.branch == "archives"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_from_env_defaults(self, tmp_path):
        """Test from_env with minimal environment variables."""
        # Clear all KERNICLE_GIT_* vars
        import os
        for key in list(os.environ.keys()):
            if key.startswith('KERNICLE_GIT_'):
                del os.environ[key]
        
        config = GitConfig.from_env(tmp_path)
        
        assert config.remote_url is None
        assert config.repo_dir == tmp_path / "git-backup"  # Default
        assert config.branch == "main"  # Default value


class TestGitResult:
    """Tests for GitResult dataclass."""
    
    def test_success_result(self):
        """Test successful GitResult."""
        result = GitResult(
            success=True,
            committed=True,
            pushed=True,
            commit_hash="abc123def"
        )
        
        assert result.success is True
        assert result.committed is True
        assert result.pushed is True
        assert result.commit_hash == "abc123def"
        assert result.errors == []
        assert result.warnings == []
    
    def test_failure_result(self):
        """Test failed GitResult."""
        result = GitResult(
            success=False,
            errors=["Failed to push", "Remote rejected"]
        )
        
        assert result.success is False
        assert result.committed is False
        assert result.pushed is False
        assert len(result.errors) == 2
    
    def test_to_dict(self):
        """Test to_dict conversion."""
        result = GitResult(
            success=True,
            committed=True,
            pushed=True,
            commit_hash="abc123",
            warnings=["Remote slow"]
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["committed"] is True
        assert d["pushed"] is True
        assert d["commit_hash"] == "abc123"
        assert d["errors"] == []
        assert d["warnings"] == ["Remote slow"]


class TestIsGitAvailable:
    """Tests for is_git_available function."""
    
    @patch('subprocess.run')
    def test_git_available(self, mock_run):
        """Test when git is available."""
        mock_run.return_value = MagicMock(returncode=0)
        
        assert is_git_available() is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_git_not_available(self, mock_run):
        """Test when git is not available."""
        mock_run.side_effect = FileNotFoundError()
        
        assert is_git_available() is False
    
    @patch('subprocess.run')
    def test_git_returns_error(self, mock_run):
        """Test when git command returns error."""
        mock_run.return_value = MagicMock(returncode=1)
        
        assert is_git_available() is False


class TestRunGit:
    """Tests for _run_git helper function."""
    
    @patch('subprocess.run')
    def test_run_git_success(self, mock_run):
        """Test successful git command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="success output",
            stderr=""
        )
        
        success, output, error = _run_git(["status"], cwd=Path("/tmp"))
        
        assert success is True
        assert output == "success output"
        assert error == ""
    
    @patch('subprocess.run')
    def test_run_git_failure(self, mock_run):
        """Test failed git command."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository"
        )
        
        success, output, error = _run_git(["status"], cwd=Path("/tmp"))
        
        assert success is False
        assert error == "fatal: not a git repository"
    
    @patch('subprocess.run')
    def test_run_git_exception(self, mock_run):
        """Test git command that raises exception."""
        mock_run.side_effect = FileNotFoundError("git not found")
        
        success, output, error = _run_git(["status"], cwd=Path("/tmp"))
        
        assert success is False
        assert "git not found" in error


class TestInitRepo:
    """Tests for init_repo function."""
    
    @patch('kernicle.services.gitbackup._run_git')
    def test_init_new_repo(self, mock_run_git, tmp_path):
        """Test initializing a new repository."""
        repo_dir = tmp_path / "new-repo"
        mock_run_git.return_value = (True, "Initialized empty Git repository", "")
        
        config = GitConfig(
            remote_url="git@github.com:user/repo.git",
            repo_dir=repo_dir,
            branch="main"
        )
        
        success, errors = init_repo(config)
        
        assert success is True
        assert repo_dir.exists()
    
    @patch('kernicle.services.gitbackup._run_git')
    def test_init_existing_repo(self, mock_run_git, tmp_path):
        """Test with existing repository."""
        repo_dir = tmp_path / "existing-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        
        mock_run_git.return_value = (True, "", "")
        
        config = GitConfig(
            remote_url="git@github.com:user/repo.git",
            repo_dir=repo_dir
        )
        
        success, errors = init_repo(config)
        
        assert success is True
    
    def test_init_no_repo_dir(self):
        """Test init with no repo_dir configured."""
        config = GitConfig(remote_url="git@github.com:user/repo.git")
        
        success, errors = init_repo(config)
        
        assert success is False
        assert any("repo" in e.lower() for e in errors)


class TestBackupToGit:
    """Tests for backup_to_git function."""
    
    @pytest.fixture
    def mock_zip_file(self, tmp_path):
        """Create a mock ZIP file."""
        zip_file = tmp_path / "session-2025-12-30.zip"
        zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)  # Minimal ZIP header
        return zip_file
    
    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock git config."""
        return GitConfig(
            remote_url="git@github.com:user/backup.git",
            repo_dir=tmp_path / "git-repo",
            branch="main"
        )
    
    @patch('kernicle.services.gitbackup._run_git')
    @patch('kernicle.services.gitbackup.init_repo')
    def test_backup_success(self, mock_init, mock_run_git, mock_zip_file, mock_config):
        """Test successful backup to git."""
        mock_init.return_value = (True, [])
        mock_run_git.side_effect = [
            (True, "", ""),  # git add
            (True, "M file.zip", ""),  # git status (check for changes)
            (True, "abc123def", ""),  # git commit
            (True, "abc123def", ""),  # git rev-parse HEAD
            (True, "", ""),  # git push
        ]
        
        # Create the repo dir and archives subdir so copy works
        mock_config.repo_dir.mkdir(parents=True)
        (mock_config.repo_dir / "archives").mkdir()
        
        result = backup_to_git(mock_zip_file, mock_config)
        
        assert result.success is True
    
    @patch('kernicle.services.gitbackup.init_repo')
    def test_backup_init_fails(self, mock_init, mock_zip_file, mock_config):
        """Test backup when repo init fails."""
        mock_init.return_value = (False, ["Init failed"])
        
        result = backup_to_git(mock_zip_file, mock_config)
        
        assert result.success is False
        assert "Init failed" in result.errors
    
    def test_backup_zip_not_found(self, tmp_path, mock_config):
        """Test backup with nonexistent ZIP file."""
        nonexistent = tmp_path / "nonexistent.zip"
        
        result = backup_to_git(nonexistent, mock_config)
        
        assert result.success is False
        assert any("not exist" in e.lower() or "does not exist" in e.lower() for e in result.errors)
    
    def test_backup_not_configured(self, mock_zip_file):
        """Test backup with unconfigured git."""
        config = GitConfig()  # No remote or repo_dir
        
        result = backup_to_git(mock_zip_file, config)
        
        assert result.success is False
        assert any("not configured" in e.lower() for e in result.errors)
    
    @patch('kernicle.services.gitbackup._run_git')
    @patch('kernicle.services.gitbackup.init_repo')
    def test_backup_push_fails_gracefully(self, mock_init, mock_run_git, mock_zip_file, mock_config):
        """Test that push failure doesn't crash."""
        mock_init.return_value = (True, [])
        mock_run_git.side_effect = [
            (True, "", ""),  # git add
            (True, "M file.zip", ""),  # git status shows changes
            (True, "abc123", ""),  # git commit
            (True, "abc123", ""),  # git rev-parse HEAD  
            (False, "", "fatal: could not read from remote"),  # git push fails
        ]
        
        mock_config.repo_dir.mkdir(parents=True)
        (mock_config.repo_dir / "archives").mkdir()
        
        result = backup_to_git(mock_zip_file, mock_config)
        
        # Should not crash, commit was successful even if push failed
        assert result.committed is True


class TestGitIntegration:
    """Integration-style tests (still mocked but testing full flow)."""
    
    @patch('kernicle.services.gitbackup.is_git_available')
    def test_full_backup_flow_when_git_unavailable(self, mock_available, tmp_path):
        """Test backup flow when git is not available."""
        mock_available.return_value = False
        
        zip_file = tmp_path / "test.zip"
        zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 50)
        
        config = GitConfig(
            remote_url="git@github.com:user/repo.git",
            repo_dir=tmp_path / "repo"
        )
        
        # When git isn't available, backup_to_git should fail gracefully
        result = backup_to_git(zip_file, config)
        
        assert result.success is False
        assert any("not installed" in e.lower() or "not in path" in e.lower() for e in result.errors)
