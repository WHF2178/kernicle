"""
Tests for incidents.py - incident grouping module.
Sprint 2: Tests incident grouping, summaries, and reports.
"""

import pytest
from datetime import datetime, timedelta

from kernicle.services.detect import (
    Finding,
    Severity,
    FindingCategory,
    scan_logs,
)
from kernicle.services.incidents import (
    Incident,
    IncidentGrouper,
    group_findings,
    generate_executive_summary,
    generate_incidents_report,
)

from tests.fixtures.synthetic_logs import (
    CLEAN_KERNEL_LOG,
    KERNEL_PANIC_LOG,
    OOPS_BUG_LOG,
    OOM_KILLER_LOG,
    MIXED_ANOMALIES_LOG,
)


class TestIncidentGrouper:
    """Tests for IncidentGrouper class."""
    
    def test_grouper_default_settings(self):
        """Test grouper initializes with default settings."""
        grouper = IncidentGrouper()
        # time_window is a timedelta of 5 minutes
        assert grouper.time_window == timedelta(minutes=5)
        assert grouper.line_proximity == 80
    
    def test_grouper_custom_settings(self):
        """Test grouper accepts custom settings."""
        grouper = IncidentGrouper(time_window_minutes=10, line_proximity=50)
        assert grouper.time_window == timedelta(minutes=10)
        assert grouper.line_proximity == 50


class TestIncidentGrouping:
    """Tests for incident grouping logic."""
    
    def test_empty_findings_returns_empty_list(self):
        """Test empty findings returns empty incidents."""
        incidents = group_findings([])
        assert incidents == []
    
    def test_groups_findings_into_incidents(self):
        """Test findings are grouped into incidents."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        assert isinstance(incidents, list)
        assert len(incidents) > 0
    
    def test_incident_contains_findings(self):
        """Test each incident contains at least one finding."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        for incident in incidents:
            assert len(incident.findings) >= 1
    
    def test_all_findings_assigned(self):
        """Test all findings are assigned to incidents."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        total_findings_in_incidents = sum(len(inc.findings) for inc in incidents)
        assert total_findings_in_incidents == len(findings)


class TestIncidentSeverity:
    """Tests for incident severity calculation."""
    
    def test_incident_has_severity(self):
        """Test incidents have severity property."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        for incident in incidents:
            assert incident.severity in [Severity.HIGH, Severity.MEDIUM, Severity.LOW]
    
    def test_severity_is_max_of_findings(self):
        """Test incident severity is max of contained findings."""
        # Create findings with known severities
        finding_high = Finding(
            id="test-1",
            category=FindingCategory.PANIC,
            severity=Severity.HIGH,
            rule_name="test",
            matched_line="test line",
            line_number=1,
            timestamp=None,
            source="test",
            evidence_lines=["test"],
        )
        finding_low = Finding(
            id="test-2",
            category=FindingCategory.CALL_TRACE,
            severity=Severity.LOW,
            matched_line="trace line",
            line_number=2,
            rule_name="test",
            timestamp=None,
            source="test",
            evidence_lines=["test"],
        )
        
        incident = Incident(
            incident_id="inc-1",
            findings=[finding_high, finding_low],
        )
        
        assert incident.severity == Severity.HIGH


class TestTimeBasedGrouping:
    """Tests for time-based grouping."""
    
    def test_groups_findings_within_time_window(self):
        """Test findings within time window are grouped."""
        now = datetime.now()
        
        # Create findings close in time (1 minute apart)
        finding1 = Finding(
            id="test-1",
            category=FindingCategory.BUG,
            severity=Severity.MEDIUM,
            rule_name="test",
            matched_line="BUG: test",
            line_number=10,
            timestamp=now,
            source="test",
            evidence_lines=["test"],
        )
        finding2 = Finding(
            id="test-2",
            category=FindingCategory.CALL_TRACE,
            severity=Severity.LOW,
            rule_name="test",
            matched_line="Call Trace:",
            line_number=20,
            timestamp=now + timedelta(minutes=1),
            source="test",
            evidence_lines=["test"],
        )
        
        grouper = IncidentGrouper(time_window_minutes=5)
        incidents = grouper.group([finding1, finding2])
        
        # Should be in same incident (within 5 min window)
        assert len(incidents) == 1
    
    def test_separates_findings_outside_time_window(self):
        """Test findings outside time window are separate."""
        now = datetime.now()
        
        # Create findings far apart in time (10 minutes)
        finding1 = Finding(
            id="test-1",
            category=FindingCategory.BUG,
            severity=Severity.MEDIUM,
            rule_name="test",
            matched_line="BUG: test",
            line_number=10,
            timestamp=now,
            source="test",
            evidence_lines=["test"],
        )
        finding2 = Finding(
            id="test-2",
            category=FindingCategory.BUG,
            severity=Severity.MEDIUM,
            rule_name="test",
            matched_line="BUG: another",
            line_number=20,
            timestamp=now + timedelta(minutes=10),
            source="test",
            evidence_lines=["test"],
        )
        
        grouper = IncidentGrouper(time_window_minutes=5)
        incidents = grouper.group([finding1, finding2])
        
        # Should be in different incidents
        assert len(incidents) == 2


class TestLineProximityGrouping:
    """Tests for line proximity grouping."""
    
    def test_groups_findings_within_line_proximity(self):
        """Test findings within line proximity are grouped."""
        # Create findings close in lines (no timestamp)
        finding1 = Finding(
            id="test-1",
            category=FindingCategory.BUG,
            severity=Severity.MEDIUM,
            rule_name="test",
            matched_line="BUG: test",
            line_number=10,
            timestamp=None,
            source="test",
            evidence_lines=["test"],
        )
        finding2 = Finding(
            id="test-2",
            category=FindingCategory.CALL_TRACE,
            severity=Severity.LOW,
            rule_name="test",
            matched_line="Call Trace:",
            line_number=20,  # Within 80 lines
            timestamp=None,
            source="test",
            evidence_lines=["test"],
        )
        
        grouper = IncidentGrouper(line_proximity=80)
        incidents = grouper.group([finding1, finding2])
        
        # Should be in same incident
        assert len(incidents) == 1
    
    def test_separates_findings_outside_line_proximity(self):
        """Test findings outside line proximity are separate."""
        # Create findings far apart in lines
        finding1 = Finding(
            id="test-1",
            category=FindingCategory.BUG,
            severity=Severity.MEDIUM,
            rule_name="test",
            matched_line="BUG: test",
            line_number=10,
            timestamp=None,
            source="test",
            evidence_lines=["test"],
        )
        finding2 = Finding(
            id="test-2",
            category=FindingCategory.BUG,
            severity=Severity.MEDIUM,
            rule_name="test",
            matched_line="BUG: another",
            line_number=200,  # More than 80 lines apart
            timestamp=None,
            source="test",
            evidence_lines=["test"],
        )
        
        grouper = IncidentGrouper(line_proximity=80)
        incidents = grouper.group([finding1, finding2])
        
        # Should be in different incidents
        assert len(incidents) == 2


class TestIncidentToDict:
    """Tests for Incident.to_dict() serialization."""
    
    def test_to_dict_has_required_fields(self):
        """Test to_dict includes required fields."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        for incident in incidents:
            d = incident.to_dict()
            assert "incident_id" in d
            assert "summary" in d
            assert "severity" in d
            assert "finding_count" in d
            assert "finding_ids" in d
    
    def test_to_dict_severity_is_string(self):
        """Test severity in dict is string value."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        for incident in incidents:
            d = incident.to_dict()
            assert d["severity"] in ["high", "medium", "low"]


class TestExecutiveSummary:
    """Tests for executive summary generation."""
    
    def test_generates_summary_string(self):
        """Test summary is generated as string."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        summary = generate_executive_summary(findings, incidents)
        assert isinstance(summary, str)
    
    def test_summary_mentions_incidents(self):
        """Test summary mentions incident count."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        summary = generate_executive_summary(findings, incidents)
        assert "incident" in summary.lower()
    
    def test_summary_empty_findings(self):
        """Test summary for no incidents."""
        summary = generate_executive_summary([], [])
        assert "no" in summary.lower() or "0" in summary


class TestIncidentsReport:
    """Tests for incidents report generation."""
    
    def test_generates_report_string(self):
        """Test report is generated as string."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        report = generate_incidents_report(incidents, findings)
        assert isinstance(report, str)
    
    def test_report_includes_incidents(self):
        """Test report includes incident details."""
        findings = scan_logs(KERNEL_PANIC_LOG)
        incidents = group_findings(findings)
        
        report = generate_incidents_report(incidents, findings)
        for incident in incidents:
            assert incident.incident_id in report


class TestMixedLog:
    """Tests for logs with mixed anomaly types."""
    
    def test_groups_mixed_anomalies(self):
        """Test grouping of various anomaly types."""
        findings = scan_logs(MIXED_ANOMALIES_LOG)
        incidents = group_findings(findings)
        
        assert len(incidents) >= 1
    
    def test_incidents_have_summary(self):
        """Test all incidents have summary."""
        findings = scan_logs(MIXED_ANOMALIES_LOG)
        incidents = group_findings(findings)
        
        for incident in incidents:
            assert len(incident.summary) > 0
