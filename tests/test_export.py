"""
Tests for Sprint 6: Export functionality.
Tests JSON, Markdown, and HTML export formats.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from kernicle.services.export import (
    SessionExporter,
    ExportResult,
    export_session,
    find_session,
)
from kernicle.services.sysinfo import (
    get_kernel_version,
    get_uptime,
    get_boot_time,
    get_os_info,
    get_system_info,
    get_host_info_for_manifest,
    SystemInfo,
)


class TestExportResult:
    """Tests for ExportResult dataclass."""
    
    def test_success_result(self):
        """Test successful export result."""
        result = ExportResult(
            success=True,
            output_path=Path("/tmp/report.html"),
            format="html"
        )
        assert result.success is True
        assert result.format == "html"
        assert result.error is None
    
    def test_failure_result(self):
        """Test failed export result."""
        result = ExportResult(
            success=False,
            format="json",
            error="File not found"
        )
        assert result.success is False
        assert result.error == "File not found"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ExportResult(
            success=True,
            output_path=Path("/tmp/report.md"),
            format="md"
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["format"] == "md"
        assert "/tmp/report.md" in d["output_path"]


class TestSessionExporter:
    """Tests for SessionExporter class."""
    
    @pytest.fixture
    def mock_session(self, tmp_path):
        """Create a mock session directory with test data."""
        session_dir = tmp_path / "session-20260103-120000"
        session_dir.mkdir()
        
        sources_dir = session_dir / "sources"
        sources_dir.mkdir()
        
        # Create manifest
        manifest = {
            "tool": "kernicle",
            "version": "0.6.0",
            "session_name": "session-20260103-120000",
            "host": {
                "hostname": "testhost",
                "os": "Ubuntu 22.04 LTS",
                "kernel_version": "6.5.0-test",
                "architecture": "x86_64",
                "uptime_formatted": "2d 3h 45m",
                "boot_time": "2026-01-01 10:00:00 UTC",
            },
            "capture": {
                "range_input": "last:5m",
                "since_utc": "2026-01-03T11:55:00+00:00",
                "kernel_only": False,
            },
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest))
        
        # Create findings
        findings = {
            "findings": [
                {
                    "severity": "critical",
                    "rule_name": "kernel_panic",
                    "line_number": 100,
                    "matched_text": "Kernel panic - not syncing",
                    "message": "Kernel panic detected",
                },
                {
                    "severity": "warning",
                    "rule_name": "oom_killer",
                    "line_number": 50,
                    "matched_text": "Out of memory: Killed process",
                    "message": "OOM killer invoked",
                },
            ]
        }
        (session_dir / "findings.json").write_text(json.dumps(findings))
        
        # Create incidents
        incidents = {
            "incidents": [
                {
                    "title": "Kernel Panic Event",
                    "severity": "critical",
                    "first_seen": "2026-01-03T12:00:00Z",
                    "last_seen": "2026-01-03T12:00:01Z",
                    "finding_count": 1,
                    "summary": "A kernel panic occurred causing system crash.",
                },
            ]
        }
        (session_dir / "incidents.json").write_text(json.dumps(incidents))
        
        # Create metrics
        metrics = {
            "cpu": {"percent": 45, "count": 8},
            "memory": {"percent": 60, "total": 16 * 1024 * 1024 * 1024, "available": 6 * 1024 * 1024 * 1024},
        }
        (session_dir / "metrics.json").write_text(json.dumps(metrics))
        
        # Create log files
        (sources_dir / "journalctl-kernel.log").write_text("kernel log line 1\nkernel log line 2\n")
        (sources_dir / "journalctl-system.log").write_text("system log line 1\n")
        
        return session_dir
    
    def test_load_session_data(self, mock_session):
        """Test loading session data."""
        exporter = SessionExporter(mock_session)
        success, error = exporter.load_session_data()
        
        assert success is True
        assert error == ""
        assert exporter.manifest["tool"] == "kernicle"
        assert len(exporter.findings) == 2
        assert len(exporter.incidents) == 1
    
    def test_load_nonexistent_session(self, tmp_path):
        """Test loading from nonexistent directory."""
        exporter = SessionExporter(tmp_path / "nonexistent")
        success, error = exporter.load_session_data()
        
        assert success is False
        assert "not found" in error.lower()
    
    def test_export_json(self, mock_session, tmp_path):
        """Test JSON export."""
        exporter = SessionExporter(mock_session)
        output_path = tmp_path / "export.json"
        
        result = exporter.export_json(output_path)
        
        assert result.success is True
        assert output_path.exists()
        
        data = json.loads(output_path.read_text())
        assert "export_info" in data
        assert data["export_info"]["format"] == "json"
        assert "manifest" in data
        assert "findings" in data
        assert "incidents" in data
        assert "summary" in data
    
    def test_export_markdown(self, mock_session, tmp_path):
        """Test Markdown export."""
        exporter = SessionExporter(mock_session)
        output_path = tmp_path / "export.md"
        
        result = exporter.export_markdown(output_path)
        
        assert result.success is True
        assert output_path.exists()
        
        content = output_path.read_text()
        assert "# Kernicle Session Report" in content
        assert "## System Information" in content
        assert "## Summary" in content
        assert "🔴 Critical" in content
        assert "testhost" in content
    
    def test_export_html(self, mock_session, tmp_path):
        """Test HTML export."""
        exporter = SessionExporter(mock_session)
        output_path = tmp_path / "export.html"
        
        result = exporter.export_html(output_path)
        
        assert result.success is True
        assert output_path.exists()
        
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Kernicle Report" in content
        assert "testhost" in content
        assert "Critical" in content
        assert "</html>" in content
    
    def test_generate_summary(self, mock_session):
        """Test summary generation."""
        exporter = SessionExporter(mock_session)
        exporter.load_session_data()
        
        summary = exporter._generate_summary()
        
        assert summary["total_findings"] == 2
        assert summary["critical_count"] == 1
        assert summary["warning_count"] == 1
        assert summary["total_incidents"] == 1
    
    def test_format_bytes(self, mock_session):
        """Test bytes formatting helper."""
        exporter = SessionExporter(mock_session)
        
        assert exporter._format_bytes(0) == "0 B"
        assert exporter._format_bytes(512) == "512.0 B"
        assert exporter._format_bytes(1024) == "1.0 KB"
        assert exporter._format_bytes(1024 * 1024) == "1.0 MB"
        assert exporter._format_bytes(1024 * 1024 * 1024) == "1.0 GB"


class TestExportSession:
    """Tests for export_session function."""
    
    @pytest.fixture
    def mock_session(self, tmp_path):
        """Create minimal session for testing."""
        session_dir = tmp_path / "session-test"
        session_dir.mkdir()
        
        manifest = {"tool": "kernicle", "version": "0.6.0", "host": {}, "capture": {}}
        (session_dir / "manifest.json").write_text(json.dumps(manifest))
        
        return session_dir
    
    def test_export_json_format(self, mock_session, tmp_path):
        """Test export with json format."""
        output = tmp_path / "out.json"
        result = export_session(mock_session, output, "json")
        
        assert result.success is True
        assert result.format == "json"
    
    def test_export_md_format(self, mock_session, tmp_path):
        """Test export with md format."""
        output = tmp_path / "out.md"
        result = export_session(mock_session, output, "md")
        
        assert result.success is True
        assert result.format == "md"
    
    def test_export_html_format(self, mock_session, tmp_path):
        """Test export with html format."""
        output = tmp_path / "out.html"
        result = export_session(mock_session, output, "html")
        
        assert result.success is True
        assert result.format == "html"
    
    def test_export_invalid_format(self, mock_session, tmp_path):
        """Test export with invalid format."""
        output = tmp_path / "out.pdf"
        result = export_session(mock_session, output, "pdf")
        
        assert result.success is False
        assert result.error is not None
        assert "Unsupported format" in result.error


class TestFindSession:
    """Tests for find_session function."""
    
    @pytest.fixture
    def archives_dir(self, tmp_path):
        """Create archives directory with sessions."""
        archives = tmp_path / "archives"
        archives.mkdir()
        
        (archives / "session-20260101-100000").mkdir()
        (archives / "session-20260102-120000").mkdir()
        (archives / "session-20260103-150000").mkdir()
        
        return archives
    
    def test_find_exact_match(self, archives_dir):
        """Test finding session with exact name."""
        result = find_session(archives_dir, "session-20260101-100000")
        
        assert result is not None
        assert result.name == "session-20260101-100000"
    
    def test_find_with_prefix(self, archives_dir):
        """Test finding session without session- prefix."""
        result = find_session(archives_dir, "20260102-120000")
        
        assert result is not None
        assert "20260102" in result.name
    
    def test_find_partial_match(self, archives_dir):
        """Test finding session with partial match."""
        result = find_session(archives_dir, "20260103")
        
        assert result is not None
        assert "20260103" in result.name
    
    def test_find_not_found(self, archives_dir):
        """Test when session not found."""
        result = find_session(archives_dir, "nonexistent")
        
        assert result is None
    
    def test_find_ambiguous_match(self, archives_dir):
        """Test when multiple sessions match."""
        # "202601" matches multiple sessions
        result = find_session(archives_dir, "202601")
        
        # Should return None when ambiguous
        assert result is None
    
    def test_find_nonexistent_archives(self, tmp_path):
        """Test with nonexistent archives directory."""
        result = find_session(tmp_path / "nonexistent", "anything")
        
        assert result is None


class TestSystemInfo:
    """Tests for system info functions."""
    
    def test_get_kernel_version(self):
        """Test getting kernel version."""
        version = get_kernel_version()
        
        assert version is not None
        assert len(version) > 0
        assert version != "unknown"
    
    def test_get_uptime(self):
        """Test getting uptime."""
        seconds, formatted = get_uptime()
        
        # On Linux, should return values
        # May be None on non-Linux or in restricted environments
        if seconds is not None:
            assert seconds > 0
            assert formatted is not None
            assert any(c in formatted for c in ['d', 'h', 'm'])
    
    def test_get_boot_time(self):
        """Test getting boot time."""
        boot_time = get_boot_time()
        
        # May be None in some environments
        if boot_time is not None:
            assert len(boot_time) > 0
    
    def test_get_os_info(self):
        """Test getting OS info."""
        os_info = get_os_info()
        
        assert os_info is not None
        assert len(os_info) > 0
        assert os_info != "Unknown"
    
    def test_get_system_info(self):
        """Test getting full system info."""
        info = get_system_info()
        
        assert isinstance(info, SystemInfo)
        assert info.hostname is not None
        assert info.kernel_version is not None
        assert info.architecture is not None
    
    def test_system_info_to_dict(self):
        """Test SystemInfo to_dict method."""
        info = get_system_info()
        d = info.to_dict()
        
        assert isinstance(d, dict)
        assert "hostname" in d
        assert "kernel_version" in d
        assert "os" in d
    
    def test_get_host_info_for_manifest(self):
        """Test getting host info for manifest."""
        info = get_host_info_for_manifest()
        
        assert isinstance(info, dict)
        assert "hostname" in info
        assert "kernel_version" in info
        assert "uptime_formatted" in info
        assert "boot_time" in info


class TestExportIntegration:
    """Integration tests for export functionality."""
    
    @pytest.fixture
    def full_session(self, tmp_path):
        """Create a comprehensive mock session."""
        session_dir = tmp_path / "session-20260103-120000"
        session_dir.mkdir()
        sources_dir = session_dir / "sources"
        sources_dir.mkdir()
        
        # Manifest with all fields
        manifest = {
            "tool": "kernicle",
            "version": "0.6.0",
            "sprint": 6,
            "session_name": "session-20260103-120000",
            "created_utc": "2026-01-03T12:00:00+00:00",
            "host": {
                "hostname": "production-server-01",
                "os": "Ubuntu 22.04.3 LTS",
                "kernel_version": "6.5.0-44-generic",
                "architecture": "x86_64",
                "platform": "Linux-6.5.0-44-generic-x86_64-with-glibc2.35",
                "uptime_seconds": 345600,
                "uptime_formatted": "4d 0h 0m",
                "boot_time": "2025-12-30 12:00:00 UTC",
                "cpu_model": "AMD Ryzen 9 5900X 12-Core Processor",
            },
            "capture": {
                "range_input": "last:30m",
                "since_utc": "2026-01-03T11:30:00+00:00",
                "kernel_only": False,
            },
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        
        # Findings with various severities
        findings = {
            "findings": [
                {
                    "severity": "critical",
                    "rule_name": "kernel_panic",
                    "line_number": 1234,
                    "matched_text": "Kernel panic - not syncing: Fatal exception in interrupt",
                    "message": "Critical kernel panic detected - system crash imminent",
                },
                {
                    "severity": "critical",
                    "rule_name": "kernel_oops",
                    "line_number": 1200,
                    "matched_text": "Oops: 0002 [#1] SMP NOPTI",
                    "message": "Kernel oops detected - memory corruption possible",
                },
                {
                    "severity": "warning",
                    "rule_name": "oom_killer",
                    "line_number": 800,
                    "matched_text": "Out of memory: Killed process 12345 (python3)",
                    "message": "OOM killer terminated a process due to memory pressure",
                },
                {
                    "severity": "info",
                    "rule_name": "usb_device",
                    "line_number": 500,
                    "matched_text": "usb 1-2: New USB device found",
                    "message": "USB device connected",
                },
            ]
        }
        (session_dir / "findings.json").write_text(json.dumps(findings, indent=2))
        
        # Incidents
        incidents = {
            "incidents": [
                {
                    "id": "inc-001",
                    "title": "System Crash Event",
                    "severity": "critical",
                    "first_seen": "2026-01-03T11:45:00Z",
                    "last_seen": "2026-01-03T11:45:05Z",
                    "finding_count": 2,
                    "summary": "A critical kernel panic occurred following a kernel oops, indicating a serious system stability issue that caused a complete system crash.",
                },
                {
                    "id": "inc-002",
                    "title": "Memory Pressure Event",
                    "severity": "warning",
                    "first_seen": "2026-01-03T11:40:00Z",
                    "last_seen": "2026-01-03T11:40:00Z",
                    "finding_count": 1,
                    "summary": "The system experienced memory pressure, triggering the OOM killer to terminate processes.",
                },
            ]
        }
        (session_dir / "incidents.json").write_text(json.dumps(incidents, indent=2))
        
        # Metrics
        metrics = {
            "cpu": {
                "percent": 85,
                "count": 24,
                "logical_cores": 24,
                "physical_cores": 12,
            },
            "memory": {
                "percent": 92,
                "total": 64 * 1024 * 1024 * 1024,
                "available": 5 * 1024 * 1024 * 1024,
                "used": 59 * 1024 * 1024 * 1024,
            },
            "disk": {
                "percent": 75,
                "total": 1000 * 1024 * 1024 * 1024,
                "free": 250 * 1024 * 1024 * 1024,
            },
        }
        (session_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        
        # Log files
        kernel_log = """Jan 03 11:40:00 production-server-01 kernel: Out of memory: Killed process 12345 (python3)
Jan 03 11:45:00 production-server-01 kernel: Oops: 0002 [#1] SMP NOPTI
Jan 03 11:45:01 production-server-01 kernel: CPU: 5 PID: 9876 Comm: kworker/5:0 Tainted: G
Jan 03 11:45:02 production-server-01 kernel: RIP: 0010:native_queued_spin_lock_slowpath+0x1c2/0x1d0
Jan 03 11:45:03 production-server-01 kernel: Call Trace:
Jan 03 11:45:04 production-server-01 kernel:  _raw_spin_lock+0x30/0x40
Jan 03 11:45:05 production-server-01 kernel: Kernel panic - not syncing: Fatal exception in interrupt
"""
        (sources_dir / "journalctl-kernel.log").write_text(kernel_log)
        
        system_log = """Jan 03 11:30:00 production-server-01 systemd[1]: Started Daily Cleanup of Temporary Directories.
Jan 03 11:35:00 production-server-01 sshd[5678]: Accepted publickey for admin
Jan 03 11:40:00 production-server-01 systemd[1]: memory.service: A]ctivating...
"""
        (sources_dir / "journalctl-system.log").write_text(system_log)
        
        return session_dir
    
    def test_full_json_export(self, full_session, tmp_path):
        """Test complete JSON export with all data."""
        output = tmp_path / "full_export.json"
        result = export_session(full_session, output, "json")
        
        assert result.success is True
        
        data = json.loads(output.read_text())
        
        # Verify structure
        assert data["manifest"]["host"]["hostname"] == "production-server-01"
        assert data["summary"]["critical_count"] == 2
        assert data["summary"]["warning_count"] == 1
        assert data["summary"]["info_count"] == 1
        assert len(data["incidents"]) == 2
    
    def test_full_html_export(self, full_session, tmp_path):
        """Test complete HTML export with styling."""
        output = tmp_path / "full_export.html"
        result = export_session(full_session, output, "html")
        
        assert result.success is True
        
        content = output.read_text()
        
        # Verify HTML structure
        assert "<!DOCTYPE html>" in content
        assert "production-server-01" in content
        assert "6.5.0-44-generic" in content
        assert "4d 0h 0m" in content  # uptime
        assert "Critical" in content
        assert "kernel_panic" in content
        assert "85%" in content  # CPU
        assert "</html>" in content
    
    def test_full_markdown_export(self, full_session, tmp_path):
        """Test complete Markdown export."""
        output = tmp_path / "full_export.md"
        result = export_session(full_session, output, "md")
        
        assert result.success is True
        
        content = output.read_text()
        
        # Verify Markdown structure
        assert "# Kernicle Session Report" in content
        assert "| Hostname | `production-server-01`" in content
        assert "| Kernel | `6.5.0-44-generic`" in content
        assert "🔴 Critical" in content
        assert "## Incidents" in content
        assert "System Crash Event" in content
