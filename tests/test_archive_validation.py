"""
Tests for archive validation - Sprint 3.
Tests archive structure validation and enhanced manifest.
"""

import pytest
import json
import tempfile
from pathlib import Path

from kernicle.services.archive import SessionArchive, create_session_archive
from kernicle.services.timeparse import TimeRange
from datetime import datetime, timezone


class TestArchiveValidation:
    """Tests for archive structure validation."""
    
    def test_validate_complete_archive(self):
        """Test validation passes for complete archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            # Create time range for manifest
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            # Write all required files
            archive.write_source("kernel", "test.log", "test log content\n")
            archive.finalize_analysis()
            archive.capture_metrics()
            archive.write_findings()
            archive.write_incidents()
            archive.write_metrics()
            archive.write_report(time_range, kernel_only=True)
            archive.write_manifest(time_range, kernel_only=True)
            
            # Validate
            is_valid, errors = archive.validate_archive()
            
            assert is_valid is True
            assert len(errors) == 0
    
    def test_validate_missing_metrics(self):
        """Test validation fails when metrics.json missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            # Write everything except metrics
            archive.write_source("kernel", "test.log", "test content")
            archive.finalize_analysis()
            archive.write_findings()
            archive.write_incidents()
            archive.write_report(time_range, kernel_only=True)
            archive.write_manifest(time_range, kernel_only=True)
            
            # Validate - should fail
            is_valid, errors = archive.validate_archive()
            
            assert is_valid is False
            assert any("metrics.json" in e for e in errors)
    
    def test_validate_missing_report(self):
        """Test validation fails when report.txt missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            # Write everything except report
            archive.write_source("kernel", "test.log", "test content")
            archive.finalize_analysis()
            archive.capture_metrics()
            archive.write_findings()
            archive.write_incidents()
            archive.write_metrics()
            archive.write_manifest(time_range, kernel_only=True)
            
            # Validate - should fail
            is_valid, errors = archive.validate_archive()
            
            assert is_valid is False
            assert any("report.txt" in e for e in errors)


class TestEnhancedManifest:
    """Tests for Sprint 3 enhanced manifest."""
    
    def test_manifest_has_host_info(self):
        """Test manifest contains host information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            archive.write_source("kernel", "test.log", "line1\nline2\nline3\n")
            archive.finalize_analysis()
            archive.write_manifest(time_range, kernel_only=True)
            
            # Read manifest
            manifest = json.loads(archive.manifest_path.read_text())
            
            assert 'host' in manifest
            assert 'hostname' in manifest['host']
            # Sprint 6: Enhanced host info uses kernel_version instead of kernel_release
            assert 'kernel_version' in manifest['host']
            assert 'architecture' in manifest['host']
            # Sprint 6: New fields
            assert 'uptime_formatted' in manifest['host']
            assert 'boot_time' in manifest['host']
    
    def test_manifest_has_capture_mode(self):
        """Test manifest contains capture_mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            archive.write_manifest(time_range, kernel_only=True)
            manifest = json.loads(archive.manifest_path.read_text())
            
            assert manifest['capture_mode'] == "kernel-only"
            
            # Test "all" mode
            archive.write_manifest(time_range, kernel_only=False)
            manifest = json.loads(archive.manifest_path.read_text())
            
            assert manifest['capture_mode'] == "all"
    
    def test_manifest_has_line_counts(self):
        """Test manifest contains line counts per source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            # Write source with 5 lines
            archive.write_source("kernel", "test.log", "line1\nline2\nline3\nline4\nline5")
            archive.finalize_analysis()
            archive.write_manifest(time_range, kernel_only=True)
            
            manifest = json.loads(archive.manifest_path.read_text())
            
            assert 'counts' in manifest
            assert 'total_lines_per_source' in manifest['counts']
            assert manifest['counts']['total_lines_per_source']['kernel'] == 5
    
    def test_manifest_has_archive_layout(self):
        """Test manifest contains archive layout paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            archive.write_manifest(time_range, kernel_only=True)
            manifest = json.loads(archive.manifest_path.read_text())
            
            assert 'archive_layout' in manifest
            assert 'session_dir' in manifest['archive_layout']
            assert 'report_path' in manifest['archive_layout']
            assert 'manifest_path' in manifest['archive_layout']
            assert 'metrics_path' in manifest['archive_layout']
            assert 'sources_dir' in manifest['archive_layout']
    
    def test_manifest_sprint_3_features(self):
        """Test manifest lists Sprint 3 features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            time_range = TimeRange(
                since_utc=datetime.now(timezone.utc),
                since_arg="--since '2025-01-01'",
                range_input="last:5m"
            )
            
            archive.write_manifest(time_range, kernel_only=True)
            manifest = json.loads(archive.manifest_path.read_text())
            
            assert manifest['sprint'] == 4
            assert 'sprint_3' in manifest['features']
            assert 'system_metrics' in manifest['features']['sprint_3']
            assert 'sprint_4' in manifest['features']
            assert 'zip_archives' in manifest['features']['sprint_4']


class TestMetricsJson:
    """Tests for metrics.json output."""
    
    def test_metrics_json_created(self):
        """Test metrics.json is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            archive.capture_metrics()
            archive.write_metrics()
            
            assert archive.metrics_path.exists()
    
    def test_metrics_json_has_required_fields(self):
        """Test metrics.json contains required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            archive.capture_metrics()
            archive.write_metrics()
            
            metrics = json.loads(archive.metrics_path.read_text())
            
            assert 'tool' in metrics
            assert 'version' in metrics
            assert 'session' in metrics
            assert 'timestamp_utc' in metrics
            assert 'hostname' in metrics
            assert 'platform' in metrics
    
    def test_metrics_json_without_capture(self):
        """Test metrics.json handles missing capture gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            # Write metrics without capturing first
            archive.write_metrics()
            
            metrics = json.loads(archive.metrics_path.read_text())
            
            assert 'error' in metrics
            assert archive.metrics_path.exists()


class TestSourceLineCounts:
    """Tests for source line counting."""
    
    def test_line_count_single_source(self):
        """Test line counting for single source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            content = "line1\nline2\nline3\nline4\n"
            archive.write_source("kernel", "test.log", content)
            
            assert archive.source_line_counts['kernel'] == 4
    
    def test_line_count_multiple_sources(self):
        """Test line counting for multiple sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            archive.write_source("kernel", "kernel.log", "k1\nk2\nk3\n")
            archive.write_source("system", "system.log", "s1\ns2\n")
            
            assert archive.source_line_counts['kernel'] == 3
            assert archive.source_line_counts['system'] == 2
    
    def test_line_count_empty_content(self):
        """Test line counting for empty content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            archive = create_session_archive(base_dir)
            
            archive.write_source("kernel", "test.log", "")
            
            assert archive.source_line_counts['kernel'] == 0
