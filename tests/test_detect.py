"""
Tests for detect.py - anomaly detection module.
Sprint 2: Tests detection rules, evidence extraction, categories.
"""

import pytest
from datetime import datetime, timezone

from kernicle.services.detect import (
    Detector,
    Finding,
    Severity,
    FindingCategory,
    scan_logs,
    DETECTION_RULES,
)

from tests.fixtures.synthetic_logs import (
    CLEAN_KERNEL_LOG,
    KERNEL_PANIC_LOG,
    OOPS_BUG_LOG,
    OOM_KILLER_LOG,
    MIXED_ANOMALIES_LOG,
    NO_TIMESTAMP_LOG,
)


class TestDetector:
    """Tests for Detector class."""
    
    def test_detector_default_rules(self):
        """Test detector initializes with default rules."""
        detector = Detector()
        assert len(detector.rules) == len(DETECTION_RULES)
    
    def test_detector_custom_context(self):
        """Test detector accepts custom context settings."""
        detector = Detector(context_before=5, context_after=10)
        assert detector.context_before == 5
        assert detector.context_after == 10


class TestCleanLogs:
    """Tests for logs with no anomalies."""
    
    def test_no_findings_in_clean_log(self):
        """Test clean logs produce no findings."""
        findings = scan_logs(CLEAN_KERNEL_LOG, source="journalctl-kernel")
        assert len(findings) == 0
    
    def test_scan_returns_list(self):
        """Test scan returns a list."""
        findings = scan_logs(CLEAN_KERNEL_LOG)
        assert isinstance(findings, list)


class TestKernelPanicDetection:
    """Tests for kernel panic detection."""
    
    def test_detects_kernel_panic(self):
        """Test detection of kernel panic."""
        findings = scan_logs(KERNEL_PANIC_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.PANIC in categories
    
    def test_detects_oops(self):
        """Test detection of Oops."""
        findings = scan_logs(KERNEL_PANIC_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.OOPS in categories
    
    def test_detects_bug(self):
        """Test detection of BUG."""
        findings = scan_logs(KERNEL_PANIC_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.BUG in categories
    
    def test_detects_call_trace(self):
        """Test detection of Call Trace."""
        findings = scan_logs(KERNEL_PANIC_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.CALL_TRACE in categories
    
    def test_detects_not_syncing(self):
        """Test detection of not syncing (when on separate line from panic)."""
        # NOT_SYNCING on same line as "Kernel panic" won't be separately detected
        # because first match wins. Test with explicit log containing standalone message
        log_with_not_syncing = """2025-12-30T12:15:31+0000 myhost kernel: Rebooting in 10 seconds
2025-12-30T12:15:32+0000 myhost kernel: VFS: Busy inodes after unmount. Self-destruct in 5 seconds.  Have a nice day.
2025-12-30T12:15:33+0000 myhost kernel: not syncing: attempted to kill init!
2025-12-30T12:15:34+0000 myhost kernel: System halted.
"""
        findings = scan_logs(log_with_not_syncing, source="journalctl-kernel")
        categories = {f.category for f in findings}
        assert FindingCategory.NOT_SYNCING in categories
    
    def test_kernel_panic_severity_is_high(self):
        """Test kernel panic findings have HIGH severity."""
        findings = scan_logs(KERNEL_PANIC_LOG, source="journalctl-kernel")
        
        panic_findings = [f for f in findings if f.category == FindingCategory.PANIC]
        assert len(panic_findings) >= 1
        assert panic_findings[0].severity == Severity.HIGH


class TestOopsBugDetection:
    """Tests for Oops/BUG detection."""
    
    def test_detects_bug_in_oops_log(self):
        """Test BUG detection in oops log."""
        findings = scan_logs(OOPS_BUG_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.BUG in categories
    
    def test_detects_oops_in_oops_log(self):
        """Test Oops detection in oops log."""
        findings = scan_logs(OOPS_BUG_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.OOPS in categories
    
    def test_detects_call_trace_in_oops_log(self):
        """Test Call Trace detection in oops log."""
        findings = scan_logs(OOPS_BUG_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.CALL_TRACE in categories


class TestOOMDetection:
    """Tests for OOM (Out of Memory) detection."""
    
    def test_detects_oom(self):
        """Test OOM detection."""
        findings = scan_logs(OOM_KILLER_LOG, source="journalctl-kernel")
        
        categories = {f.category for f in findings}
        assert FindingCategory.OOM in categories
    
    def test_oom_severity_is_high(self):
        """Test OOM findings have HIGH severity."""
        findings = scan_logs(OOM_KILLER_LOG, source="journalctl-kernel")
        
        oom_findings = [f for f in findings if f.category == FindingCategory.OOM]
        assert len(oom_findings) >= 1
        assert oom_findings[0].severity == Severity.HIGH


class TestFindingProperties:
    """Tests for Finding object properties."""
    
    def test_finding_has_id(self):
        """Test findings have unique IDs."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        ids = [f.id for f in findings]
        assert len(ids) == len(set(ids))  # All unique
    
    def test_finding_has_line_number(self):
        """Test findings have line numbers."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            assert finding.line_number >= 1
    
    def test_finding_has_matched_line(self):
        """Test findings have matched line content."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            assert len(finding.matched_line) > 0
    
    def test_finding_has_source(self):
        """Test findings have source."""
        findings = scan_logs(KERNEL_PANIC_LOG, source="test-source")
        
        for finding in findings:
            assert finding.source == "test-source"


class TestEvidenceContext:
    """Tests for evidence context extraction."""
    
    def test_evidence_lines_included(self):
        """Test evidence lines are included in findings."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            assert len(finding.evidence_lines) > 0
    
    def test_evidence_contains_matched_line(self):
        """Test evidence contains the matched line marked with >>>."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            has_marker = any(">>>" in line for line in finding.evidence_lines)
            assert has_marker
    
    def test_custom_context_size(self):
        """Test custom context window sizes."""
        detector = Detector(context_before=1, context_after=1)
        findings = detector.scan(KERNEL_PANIC_LOG)
        
        # With 1 before + matched + 1 after = max 3 lines
        for finding in findings:
            assert len(finding.evidence_lines) <= 3


class TestTimestampParsing:
    """Tests for timestamp parsing."""
    
    def test_parses_iso_timestamp(self):
        """Test parsing ISO timestamps from log lines."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        # At least some findings should have timestamps
        timestamps = [f.timestamp for f in findings if f.timestamp]
        assert len(timestamps) > 0
    
    def test_timestamp_is_datetime(self):
        """Test parsed timestamp is datetime object."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            if finding.timestamp:
                assert isinstance(finding.timestamp, datetime)
    
    def test_no_timestamp_logs_return_none(self):
        """Test logs without timestamps return None for timestamp."""
        findings = scan_logs(NO_TIMESTAMP_LOG)
        
        for finding in findings:
            assert finding.timestamp is None


class TestFindingToDict:
    """Tests for Finding.to_dict() serialization."""
    
    def test_to_dict_has_required_fields(self):
        """Test to_dict includes all required fields."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            d = finding.to_dict()
            assert "id" in d
            assert "category" in d
            assert "severity" in d
            assert "rule_name" in d
            assert "matched_line" in d
            assert "line_number" in d
            assert "timestamp" in d
            assert "source" in d
            assert "evidence_lines" in d
    
    def test_to_dict_category_is_string(self):
        """Test category in dict is string value."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        
        for finding in findings:
            d = finding.to_dict()
            assert isinstance(d["category"], str)
            assert d["category"] in ["panic", "oops", "bug", "not_syncing", "call_trace", "oom", "other"]


class TestMixedAnomalies:
    """Tests for logs with multiple types of anomalies."""
    
    def test_detects_multiple_categories(self):
        """Test detection of multiple anomaly categories."""
        findings = scan_logs(MIXED_ANOMALIES_LOG)
        
        categories = {f.category for f in findings}
        # Should detect BUG, OOM, panic, etc.
        assert len(categories) >= 3
    
    def test_multiple_findings(self):
        """Test multiple findings are returned."""
        findings = scan_logs(MIXED_ANOMALIES_LOG)
        
        assert len(findings) >= 5
