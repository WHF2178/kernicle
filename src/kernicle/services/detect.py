"""
Detection engine for kernel anomalies.
Sprint 2: Scans captured log text for panic/anomaly patterns.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class Severity(Enum):
    """Severity levels for findings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCategory(Enum):
    """Categories of detected anomalies."""
    PANIC = "panic"
    OOPS = "oops"
    BUG = "bug"
    NOT_SYNCING = "not_syncing"
    CALL_TRACE = "call_trace"
    OOM = "oom"
    OTHER = "other"


@dataclass
class DetectionRule:
    """A detection rule definition."""
    name: str
    pattern: str
    category: FindingCategory
    severity: Severity
    description: str
    
    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE)


# Detection rules for Sprint 2
DETECTION_RULES: list[DetectionRule] = [
    DetectionRule(
        name="kernel_panic",
        pattern=r"kernel\s*panic",
        category=FindingCategory.PANIC,
        severity=Severity.HIGH,
        description="Kernel panic - system crash requiring reboot"
    ),
    DetectionRule(
        name="oops",
        pattern=r"oops[:\s]",
        category=FindingCategory.OOPS,
        severity=Severity.HIGH,
        description="Kernel oops - severe kernel error"
    ),
    DetectionRule(
        name="bug",
        pattern=r"BUG:\s",
        category=FindingCategory.BUG,
        severity=Severity.HIGH,
        description="Kernel BUG - software bug in kernel code"
    ),
    DetectionRule(
        name="not_syncing",
        pattern=r"not\s+syncing",
        category=FindingCategory.NOT_SYNCING,
        severity=Severity.HIGH,
        description="Kernel not syncing - often follows panic"
    ),
    DetectionRule(
        name="call_trace",
        pattern=r"call\s*trace:",
        category=FindingCategory.CALL_TRACE,
        severity=Severity.MEDIUM,
        description="Call trace - stack trace dump indicates error"
    ),
    DetectionRule(
        name="oom_killer",
        pattern=r"out\s+of\s+memory|oom-killer|oom_killer",
        category=FindingCategory.OOM,
        severity=Severity.HIGH,
        description="Out of memory - OOM killer invoked"
    ),
]


@dataclass
class Finding:
    """A single detection finding."""
    id: str
    category: FindingCategory
    severity: Severity
    rule_name: str
    matched_line: str
    line_number: int
    timestamp: Optional[datetime] = None
    source: str = "unknown"
    evidence_lines: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "rule_name": self.rule_name,
            "matched_line": self.matched_line,
            "line_number": self.line_number,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source,
            "evidence_lines": self.evidence_lines,
        }


class Detector:
    """
    Scans log content for anomaly patterns.
    """
    
    def __init__(
        self,
        rules: Optional[list[DetectionRule]] = None,
        context_before: int = 2,
        context_after: int = 3
    ):
        """
        Initialize detector.
        
        Args:
            rules: Detection rules to use (defaults to DETECTION_RULES)
            context_before: Lines of context before match
            context_after: Lines of context after match
        """
        self.rules = rules or DETECTION_RULES
        self.context_before = context_before
        self.context_after = context_after
    
    def scan(self, log_content: str, source: str = "unknown") -> list[Finding]:
        """
        Scan log content for anomalies.
        
        Args:
            log_content: The log text to scan
            source: Source identifier (e.g., "journalctl-kernel")
            
        Returns:
            List of Finding objects
        """
        lines = log_content.splitlines()
        findings: list[Finding] = []
        finding_counter = 0
        
        for line_idx, line in enumerate(lines):
            for rule in self.rules:
                if rule.compiled.search(line):
                    finding_counter += 1
                    finding_id = f"F{finding_counter:04d}-{uuid.uuid4().hex[:8]}"
                    
                    finding = Finding(
                        id=finding_id,
                        category=rule.category,
                        severity=rule.severity,
                        rule_name=rule.name,
                        matched_line=line,
                        line_number=line_idx + 1,
                        timestamp=self._parse_timestamp(line),
                        source=source,
                        evidence_lines=self._get_evidence(lines, line_idx),
                    )
                    findings.append(finding)
                    break  # One finding per line (first match wins)
        
        return findings
    
    def _get_evidence(self, lines: list[str], match_idx: int) -> list[str]:
        """Get evidence lines around the match."""
        start = max(0, match_idx - self.context_before)
        end = min(len(lines), match_idx + self.context_after + 1)
        
        evidence = []
        for i in range(start, end):
            prefix = ">>>" if i == match_idx else "   "
            evidence.append(f"{prefix} [{i+1}] {lines[i]}")
        
        return evidence
    
    def _parse_timestamp(self, line: str) -> Optional[datetime]:
        """
        Parse timestamp from short-iso format log line.
        Example: 2025-12-30T12:00:00+0000
        """
        # ISO format with timezone: YYYY-MM-DDTHH:MM:SS+ZZZZ
        pattern = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4})"
        match = re.search(pattern, line)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                pass
        
        # ISO format without timezone
        pattern = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
        match = re.search(pattern, line)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        
        return None


def scan_logs(
    log_content: str,
    source: str = "unknown",
    context_before: int = 2,
    context_after: int = 3
) -> list[Finding]:
    """
    Convenience function to scan logs for anomalies.
    
    Args:
        log_content: Log text to scan
        source: Source identifier
        context_before: Lines before match for evidence
        context_after: Lines after match for evidence
        
    Returns:
        List of findings
    """
    detector = Detector(
        context_before=context_before,
        context_after=context_after
    )
    return detector.scan(log_content, source)
