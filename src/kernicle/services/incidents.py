"""
Incident grouping and summary generation.
Sprint 2: Groups findings into incidents by time/line proximity.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from kernicle.services.detect import Finding, Severity, FindingCategory


@dataclass
class Incident:
    """A grouped incident containing related findings."""
    incident_id: str
    findings: list[Finding] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def severity(self) -> Severity:
        """Return highest severity among findings."""
        if not self.findings:
            return Severity.LOW
        
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        min_order = min(severity_order[f.severity] for f in self.findings)
        return [s for s, o in severity_order.items() if o == min_order][0]
    
    @property
    def categories(self) -> set[FindingCategory]:
        """Return all categories present in this incident."""
        return {f.category for f in self.findings}
    
    @property
    def summary(self) -> str:
        """Generate 1-2 line plain English summary."""
        if not self.findings:
            return "No findings in this incident."
        
        categories = self.categories
        count = len(self.findings)
        
        # Build summary based on categories
        parts = []
        
        if FindingCategory.PANIC in categories:
            parts.append("kernel panic")
        if FindingCategory.OOPS in categories:
            parts.append("kernel oops")
        if FindingCategory.BUG in categories:
            parts.append("kernel BUG")
        if FindingCategory.NOT_SYNCING in categories:
            parts.append("sync failure")
        if FindingCategory.CALL_TRACE in categories:
            parts.append("call trace")
        if FindingCategory.OOM in categories:
            parts.append("out-of-memory condition")
        
        if not parts:
            parts.append("anomaly")
        
        issue_text = ", ".join(parts)
        
        time_text = ""
        if self.start_time:
            time_text = f" at {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return f"Detected {issue_text}{time_text}. {count} related finding(s) identified."
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "incident_id": self.incident_id,
            "severity": self.severity.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "summary": self.summary,
            "finding_count": len(self.findings),
            "categories": [c.value for c in self.categories],
            "finding_ids": [f.id for f in self.findings],
        }


class IncidentGrouper:
    """
    Groups findings into incidents by time or line proximity.
    """
    
    def __init__(
        self,
        time_window_minutes: int = 5,
        line_proximity: int = 80
    ):
        """
        Initialize grouper.
        
        Args:
            time_window_minutes: Group findings within this time window
            line_proximity: Group findings within this many lines (when no timestamps)
        """
        self.time_window = timedelta(minutes=time_window_minutes)
        self.line_proximity = line_proximity
    
    def group(self, findings: list[Finding]) -> list[Incident]:
        """
        Group findings into incidents.
        
        Args:
            findings: List of findings to group
            
        Returns:
            List of incidents
        """
        if not findings:
            return []
        
        # Check if we have timestamps to work with
        has_timestamps = any(f.timestamp for f in findings)
        
        if has_timestamps:
            return self._group_by_time(findings)
        else:
            return self._group_by_proximity(findings)
    
    def _group_by_time(self, findings: list[Finding]) -> list[Incident]:
        """Group findings by timestamp proximity."""
        # Sort by timestamp (None timestamps go last)
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.timestamp is None, f.timestamp or datetime.max.replace(tzinfo=None))
        )
        
        incidents: list[Incident] = []
        current_incident: Optional[Incident] = None
        incident_counter = 0
        
        for finding in sorted_findings:
            if current_incident is None:
                # Start new incident
                incident_counter += 1
                current_incident = Incident(
                    incident_id=f"INC{incident_counter:04d}",
                    findings=[finding],
                    start_time=finding.timestamp,
                    end_time=finding.timestamp,
                )
            else:
                # Check if finding belongs to current incident
                should_group = False
                
                if finding.timestamp and current_incident.end_time:
                    time_diff = finding.timestamp - current_incident.end_time
                    should_group = time_diff <= self.time_window
                elif finding.timestamp is None:
                    # No timestamp, check line proximity
                    last_finding = current_incident.findings[-1]
                    should_group = abs(finding.line_number - last_finding.line_number) <= self.line_proximity
                
                if should_group:
                    current_incident.findings.append(finding)
                    if finding.timestamp:
                        if current_incident.start_time is None or finding.timestamp < current_incident.start_time:
                            current_incident.start_time = finding.timestamp
                        if current_incident.end_time is None or finding.timestamp > current_incident.end_time:
                            current_incident.end_time = finding.timestamp
                else:
                    # Save current and start new
                    incidents.append(current_incident)
                    incident_counter += 1
                    current_incident = Incident(
                        incident_id=f"INC{incident_counter:04d}",
                        findings=[finding],
                        start_time=finding.timestamp,
                        end_time=finding.timestamp,
                    )
        
        # Don't forget last incident
        if current_incident:
            incidents.append(current_incident)
        
        return incidents
    
    def _group_by_proximity(self, findings: list[Finding]) -> list[Incident]:
        """Group findings by line proximity when no timestamps available."""
        # Sort by line number
        sorted_findings = sorted(findings, key=lambda f: f.line_number)
        
        incidents: list[Incident] = []
        current_incident: Optional[Incident] = None
        incident_counter = 0
        
        for finding in sorted_findings:
            if current_incident is None:
                incident_counter += 1
                current_incident = Incident(
                    incident_id=f"INC{incident_counter:04d}",
                    findings=[finding],
                )
            else:
                last_finding = current_incident.findings[-1]
                if abs(finding.line_number - last_finding.line_number) <= self.line_proximity:
                    current_incident.findings.append(finding)
                else:
                    incidents.append(current_incident)
                    incident_counter += 1
                    current_incident = Incident(
                        incident_id=f"INC{incident_counter:04d}",
                        findings=[finding],
                    )
        
        if current_incident:
            incidents.append(current_incident)
        
        return incidents


def group_findings(
    findings: list[Finding],
    time_window_minutes: int = 5,
    line_proximity: int = 80
) -> list[Incident]:
    """
    Convenience function to group findings into incidents.
    
    Args:
        findings: List of findings to group
        time_window_minutes: Time window for grouping
        line_proximity: Line proximity for grouping (when no timestamps)
        
    Returns:
        List of incidents
    """
    grouper = IncidentGrouper(
        time_window_minutes=time_window_minutes,
        line_proximity=line_proximity
    )
    return grouper.group(findings)


def generate_executive_summary(findings: list[Finding], incidents: list[Incident]) -> str:
    """
    Generate executive summary for report.
    
    Args:
        findings: All findings
        incidents: Grouped incidents
        
    Returns:
        Executive summary text
    """
    lines = []
    
    total_findings = len(findings)
    total_incidents = len(incidents)
    
    # Determine highest severity
    if not findings:
        highest_severity = "None"
        status_icon = "✅"
        status_text = "NO ANOMALIES DETECTED"
    else:
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        min_order = min(severity_order[f.severity] for f in findings)
        highest_severity = [s.value.upper() for s, o in severity_order.items() if o == min_order][0]
        
        if highest_severity == "HIGH":
            status_icon = "🔴"
            status_text = "CRITICAL ISSUES DETECTED"
        elif highest_severity == "MEDIUM":
            status_icon = "🟡"
            status_text = "WARNINGS DETECTED"
        else:
            status_icon = "🟢"
            status_text = "MINOR ISSUES DETECTED"
    
    lines.extend([
        "=" * 70,
        "EXECUTIVE SUMMARY",
        "Kernicle reads the CHAOS; shows the CLARITY",
        "=" * 70,
        "",
        f"STATUS: {status_icon} {status_text}",
        "",
        f"Total Findings:    {total_findings}",
        f"Total Incidents:   {total_incidents}",
        f"Highest Severity:  {highest_severity}",
        "",
    ])
    
    # Plain English statement
    if not findings:
        lines.extend([
            "Assessment:",
            "  No kernel panics, oops, bugs, or other anomalies were detected",
            "  in the captured logs. System appears healthy.",
        ])
    else:
        # Determine what was found
        categories = {f.category for f in findings}
        
        if FindingCategory.PANIC in categories:
            lines.extend([
                "Assessment:",
                "  ⚠️  Kernicle found indicators of a KERNEL PANIC in the captured range.",
                "  Immediate investigation is recommended.",
            ])
        elif FindingCategory.OOM in categories:
            lines.extend([
                "Assessment:",
                "  ⚠️  Kernicle found OUT OF MEMORY events in the captured range.",
                "  Review memory usage and consider increasing RAM or swap.",
            ])
        elif FindingCategory.OOPS in categories or FindingCategory.BUG in categories:
            lines.extend([
                "Assessment:",
                "  ⚠️  Kernicle found kernel OOPS or BUG indicators in the captured range.",
                "  System may be unstable. Review the findings below.",
            ])
        else:
            lines.extend([
                "Assessment:",
                "  Kernicle detected anomalies in the captured logs.",
                "  Review the incidents section for details.",
            ])
    
    lines.append("")
    
    return "\n".join(lines)


def generate_incidents_report(incidents: list[Incident], findings: list[Finding]) -> str:
    """
    Generate detailed incidents section for report.
    
    Args:
        incidents: List of incidents
        findings: All findings (for reference)
        
    Returns:
        Incidents report text
    """
    lines = []
    
    lines.extend([
        "=" * 70,
        "INCIDENTS",
        "=" * 70,
        "",
    ])
    
    if not incidents:
        lines.extend([
            "No incidents detected.",
            "",
        ])
        return "\n".join(lines)
    
    for incident in incidents:
        severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(incident.severity.value, "⚪")
        
        lines.extend([
            "-" * 70,
            f"INCIDENT: {incident.incident_id}",
            "-" * 70,
            f"Severity:   {severity_icon} {incident.severity.value.upper()}",
        ])
        
        if incident.start_time:
            lines.append(f"Time:       {incident.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            if incident.end_time and incident.end_time != incident.start_time:
                lines.append(f"            to {incident.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        lines.extend([
            f"Findings:   {len(incident.findings)}",
            "",
            f"Summary: {incident.summary}",
            "",
        ])
        
        # List findings in this incident
        for finding in incident.findings:
            lines.extend([
                f"  [{finding.id}] {finding.category.value.upper()} ({finding.severity.value})",
                f"    Source: {finding.source}, Line {finding.line_number}",
                "",
                "    Evidence:",
            ])
            for evidence_line in finding.evidence_lines:
                lines.append(f"      {evidence_line}")
            lines.append("")
        
        lines.append("")
    
    return "\n".join(lines)
