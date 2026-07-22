"""
Tests for ZIP archive functionality.
Sprint 4: ZIP archive creation and verification.
"""

import pytest
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from kernicle.services.ziparchive import (
    ZipResult,
    create_session_zip,
    verify_zip_contents,
    extract_zip,
)


class TestZipResult:
    """Tests for ZipResult dataclass."""
    
    def test_success_result(self):
        """Test creating a successful ZipResult."""
        result = ZipResult(
            success=True,
            zip_path=Path("/tmp/test.zip"),
            zip_size_bytes=1024,
            zip_created_utc="2025-12-30T12:00:00+00:00"
        )
        
        assert result.success is True
        assert result.zip_path == Path("/tmp/test.zip")
        assert result.zip_size_bytes == 1024
        assert result.error is None
    
    def test_failure_result(self):
        """Test creating a failed ZipResult."""
        result = ZipResult(
            success=False,
            error="Directory not found"
        )
        
        assert result.success is False
        assert result.zip_path is None
        assert result.zip_size_bytes == 0
        assert result.error == "Directory not found"
    
    def test_to_dict_success(self):
        """Test to_dict for successful result."""
        result = ZipResult(
            success=True,
            zip_path=Path("/tmp/test.zip"),
            zip_size_bytes=2048,
            zip_created_utc="2025-12-30T14:30:00+00:00"
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["zip_path"] == "/tmp/test.zip"
        assert d["zip_size_bytes"] == 2048
        assert d["zip_created_utc"] == "2025-12-30T14:30:00+00:00"
    
    def test_to_dict_failure(self):
        """Test to_dict for failed result."""
        result = ZipResult(
            success=False,
            error="Some error"
        )
        
        d = result.to_dict()
        
        assert d["success"] is False
        assert d["error"] == "Some error"


class TestCreateSessionZip:
    """Tests for create_session_zip function."""
    
    @pytest.fixture
    def mock_session_dir(self, tmp_path):
        """Create a mock session directory structure."""
        session_dir = tmp_path / "session-2025-12-30T12-00-00"
        session_dir.mkdir()
        
        # Create sources directory with logs
        sources_dir = session_dir / "sources"
        sources_dir.mkdir()
        (sources_dir / "journalctl-kernel.log").write_text("kernel log content")
        (sources_dir / "journalctl-system.log").write_text("system log content")
        
        # Create manifest.json
        (session_dir / "manifest.json").write_text('{"sprint": 4}')
        
        # Create report.txt
        (session_dir / "report.txt").write_text("Session report content")
        
        # Create findings.json
        (session_dir / "findings.json").write_text('[]')
        
        # Create incidents.json
        (session_dir / "incidents.json").write_text('[]')
        
        # Create metrics.json
        (session_dir / "metrics.json").write_text('{}')
        
        return session_dir
    
    def test_create_zip_success(self, mock_session_dir):
        """Test successful ZIP creation."""
        result = create_session_zip(mock_session_dir)
        
        assert result.success is True
        assert result.zip_path is not None
        assert result.zip_path.exists()
        assert result.zip_path.suffix == ".zip"
        assert result.zip_size_bytes > 0
        assert result.zip_created_utc is not None
        assert result.error is None
        
        # Verify ZIP is valid
        assert zipfile.is_zipfile(result.zip_path)
    
    def test_create_zip_contents(self, mock_session_dir):
        """Test that ZIP contains all expected files."""
        result = create_session_zip(mock_session_dir)
        
        assert result.success is True
        assert result.zip_path is not None
        
        with zipfile.ZipFile(result.zip_path, 'r') as zf:
            names = zf.namelist()
            
            # Check for key files
            assert any("manifest.json" in n for n in names)
            assert any("report.txt" in n for n in names)
            assert any("journalctl-kernel.log" in n for n in names)
            assert any("journalctl-system.log" in n for n in names)
    
    def test_create_zip_nonexistent_directory(self, tmp_path):
        """Test ZIP creation with nonexistent directory."""
        nonexistent = tmp_path / "does-not-exist"
        result = create_session_zip(nonexistent)
        
        assert result.success is False
        assert result.error is not None
        assert "does not exist" in result.error.lower()
    
    def test_create_zip_empty_directory(self, tmp_path):
        """Test ZIP creation with empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        result = create_session_zip(empty_dir)
        
        # Should still succeed, just with a small ZIP
        assert result.success is True
        assert result.zip_path is not None
        assert result.zip_path.exists()


class TestVerifyZipContents:
    """Tests for verify_zip_contents function."""
    
    @pytest.fixture
    def valid_zip(self, tmp_path):
        """Create a valid ZIP file for testing."""
        zip_path = tmp_path / "valid.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("session/manifest.json", '{"sprint": 4}')
            zf.writestr("session/report.txt", "Report content")
            zf.writestr("session/sources/kernel.log", "Kernel logs")
        
        return zip_path
    
    def test_verify_valid_zip(self, valid_zip):
        """Test verification of a valid ZIP."""
        expected = ["manifest.json", "report.txt"]
        is_valid, missing = verify_zip_contents(valid_zip, expected)
        
        assert is_valid is True
        assert len(missing) == 0
    
    def test_verify_missing_files(self, valid_zip):
        """Test verification with missing expected files."""
        expected = ["manifest.json", "nonexistent.txt"]
        is_valid, missing = verify_zip_contents(valid_zip, expected)
        
        assert is_valid is False
        assert "nonexistent.txt" in missing
    
    def test_verify_nonexistent_zip(self, tmp_path):
        """Test verification of nonexistent ZIP."""
        nonexistent = tmp_path / "nonexistent.zip"
        is_valid, missing = verify_zip_contents(nonexistent, ["manifest.json"])
        
        assert is_valid is False
    
    def test_verify_invalid_zip(self, tmp_path):
        """Test verification of invalid (corrupted) ZIP."""
        invalid_zip = tmp_path / "invalid.zip"
        invalid_zip.write_text("This is not a ZIP file")
        
        is_valid, missing = verify_zip_contents(invalid_zip, ["manifest.json"])
        
        assert is_valid is False


class TestExtractZip:
    """Tests for extract_zip function."""
    
    @pytest.fixture
    def test_zip(self, tmp_path):
        """Create a test ZIP file."""
        zip_path = tmp_path / "test.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("session/manifest.json", '{"test": true}')
            zf.writestr("session/report.txt", "Test report")
        
        return zip_path
    
    def test_extract_success(self, test_zip, tmp_path):
        """Test successful extraction."""
        extract_dir = tmp_path / "extracted"
        success, error = extract_zip(test_zip, extract_dir)
        
        assert success is True
        assert error is None
        assert extract_dir.exists()
        assert (extract_dir / "session" / "manifest.json").exists()
        assert (extract_dir / "session" / "report.txt").exists()
    
    def test_extract_creates_directory(self, test_zip, tmp_path):
        """Test that extraction creates the target directory."""
        extract_dir = tmp_path / "new" / "nested" / "dir"
        success, error = extract_zip(test_zip, extract_dir)
        
        assert success is True
        assert extract_dir.exists()
    
    def test_extract_nonexistent_zip(self, tmp_path):
        """Test extraction of nonexistent ZIP."""
        nonexistent = tmp_path / "nonexistent.zip"
        extract_dir = tmp_path / "extracted"
        
        success, error = extract_zip(nonexistent, extract_dir)
        
        assert success is False
        assert error is not None


class TestZipIntegration:
    """Integration tests for ZIP workflow."""
    
    @pytest.fixture
    def full_session_dir(self, tmp_path):
        """Create a complete mock session directory."""
        session_dir = tmp_path / "session-2025-12-30T15-00-00"
        session_dir.mkdir()
        
        # Sources
        sources = session_dir / "sources"
        sources.mkdir()
        (sources / "journalctl-kernel.log").write_text("Dec 30 15:00:00 host kernel: Test log line\n" * 100)
        (sources / "journalctl-system.log").write_text("Dec 30 15:00:00 host systemd: Test system log\n" * 100)
        
        # Output files
        (session_dir / "manifest.json").write_text('{"sprint": 4, "version": "0.4.0"}')
        (session_dir / "report.txt").write_text("=" * 70 + "\nKERNICLE REPORT\n" + "=" * 70)
        (session_dir / "findings.json").write_text('[{"type": "warning", "message": "test"}]')
        (session_dir / "incidents.json").write_text('[{"id": 1, "findings": []}]')
        (session_dir / "metrics.json").write_text('{"cpu_percent": 25.5}')
        
        return session_dir
    
    def test_full_zip_workflow(self, full_session_dir, tmp_path):
        """Test complete ZIP create -> verify -> extract workflow."""
        # Create ZIP
        zip_result = create_session_zip(full_session_dir)
        assert zip_result.success is True
        assert zip_result.zip_path is not None
        
        # Verify ZIP
        expected = ["manifest.json", "report.txt"]
        is_valid, missing = verify_zip_contents(zip_result.zip_path, expected)
        assert is_valid is True
        assert len(missing) == 0
        
        # Extract ZIP
        extract_dir = tmp_path / "restored"
        success, error = extract_zip(zip_result.zip_path, extract_dir)
        assert success is True
        
        # Verify extracted contents match original
        session_name = full_session_dir.name
        extracted_session = extract_dir / session_name
        
        assert (extracted_session / "manifest.json").exists()
        assert (extracted_session / "report.txt").exists()
        assert (extracted_session / "sources" / "journalctl-kernel.log").exists()
