"""
Session archive management.
Creates and manages session directories with logs, reports, and manifests.

Sprint 2: Includes findings.json, incidents.json, and CLARITY summary.
Sprint 3: Adds metrics.json, enhanced manifest, and archive validation.
Sprint 4: Adds ZIP archive creation and Git backup support.
"""

import json
import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from kernicle import __version__
from kernicle.services.timeparse import TimeRange
from kernicle.services.journal import CaptureResult
from kernicle.services.detect import Finding, scan_logs, Severity
from kernicle.services.incidents import (
    Incident,
    group_findings,
    generate_executive_summary,
    generate_incidents_report,
)
from kernicle.services.metrics import MetricsSnapshot, capture_metrics, is_psutil_available
from kernicle.services.ziparchive import ZipResult, create_session_zip
from kernicle.services.gitbackup import GitResult
from kernicle.services import ai_integration


class SessionArchive:
    """Manages a single session archive."""
    
    def __init__(self, session_dir: Path):
        """
        Initialize a session archive.
        
        Args:
            session_dir: Path to the session directory
        """
        self.session_dir = session_dir
        self.sources_dir = session_dir / "sources"
        self.report_path = session_dir / "report.txt"
        self.manifest_path = session_dir / "manifest.json"
        self.findings_path = session_dir / "findings.json"
        self.incidents_path = session_dir / "incidents.json"
        self.metrics_path = session_dir / "metrics.json"  # Sprint 3
        
        self.warnings: list[str] = []
        self.sources: dict[str, str] = {}  # source_name -> filename
        self.source_line_counts: dict[str, int] = {}  # Sprint 3: line counts per source
        
        # Sprint 2: Findings and incidents
        self.all_findings: list[Finding] = []
        self.all_incidents: list[Incident] = []
        
        # Sprint 3: Metrics
        self.metrics_snapshot: Optional[MetricsSnapshot] = None
        
        # Sprint 4: ZIP and Git
        self.zip_result: Optional[ZipResult] = None
        self.git_result: Optional[GitResult] = None
        
        # AI Verdict
        self.ai_verdict_path = session_dir / "ai_verdict.md"
        self.ai_result: Optional[dict] = None
    
    def create_directories(self) -> None:
        """Create session directory structure."""
        self.sources_dir.mkdir(parents=True, exist_ok=True)
    
    def write_source(self, name: str, filename: str, content: str) -> None:
        """
        Write a log source file and scan it for anomalies.
        
        Args:
            name: Source identifier (e.g., "kernel", "system")
            filename: Filename to write (e.g., "journalctl-kernel.log")
            content: Log content to write
        """
        filepath = self.sources_dir / filename
        filepath.write_text(content, encoding="utf-8")
        self.sources[name] = filename
        
        # Sprint 3: Count lines
        self.source_line_counts[name] = len(content.splitlines())
        
        # Sprint 2: Scan for anomalies
        source_name = f"journalctl-{name}"
        findings = scan_logs(content, source=source_name)
        self.all_findings.extend(findings)
    
    def finalize_analysis(self) -> None:
        """Group findings into incidents after all sources are scanned."""
        self.all_incidents = group_findings(self.all_findings)
    
    def add_warning(self, message: str) -> None:
        """Add a warning message to be included in report and manifest."""
        self.warnings.append(message)
    
    def write_findings(self) -> None:
        """Write findings.json with all detected findings."""
        findings_data = {
            "tool": "kernicle",
            "version": __version__,
            "session": self.session_dir.name,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "findings_count": len(self.all_findings),
            "findings": [f.to_dict() for f in self.all_findings],
        }
        
        self.findings_path.write_text(
            json.dumps(findings_data, indent=2),
            encoding="utf-8"
        )
    
    def write_incidents(self) -> None:
        """Write incidents.json with grouped incidents."""
        incidents_data = {
            "tool": "kernicle",
            "version": __version__,
            "session": self.session_dir.name,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "incidents_count": len(self.all_incidents),
            "incidents": [i.to_dict() for i in self.all_incidents],
        }
        
        self.incidents_path.write_text(
            json.dumps(incidents_data, indent=2),
            encoding="utf-8"
        )
    
    def capture_metrics(self) -> None:
        """
        Sprint 3: Capture system metrics snapshot.
        Gracefully handles missing psutil or capture failures.
        """
        try:
            self.metrics_snapshot = capture_metrics()
            if self.metrics_snapshot.warnings:
                for warning in self.metrics_snapshot.warnings:
                    self.add_warning(f"Metrics: {warning}")
        except Exception as e:
            self.add_warning(f"Metrics capture failed: {str(e)}")
            self.metrics_snapshot = None
    
    def write_metrics(self) -> None:
        """
        Sprint 3: Write metrics.json with system snapshot.
        """
        if self.metrics_snapshot is None:
            # Create minimal metrics file indicating failure
            metrics_data = {
                "tool": "kernicle",
                "version": __version__,
                "session": self.session_dir.name,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "error": "Metrics capture failed or psutil not available",
                "psutil_available": is_psutil_available(),
            }
        else:
            metrics_data = {
                "tool": "kernicle",
                "version": __version__,
                "session": self.session_dir.name,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                **self.metrics_snapshot.to_dict(),
            }
        
        self.metrics_path.write_text(
            json.dumps(metrics_data, indent=2),
            encoding="utf-8"
        )
    
    def write_report(
        self,
        time_range: TimeRange,
        kernel_only: bool,
        kernel_result: Optional[CaptureResult] = None,
        system_result: Optional[CaptureResult] = None
    ) -> None:
        """
        Write the human-readable report.txt file.
        Sprint 6: Enhanced with system info (kernel version, uptime, boot time).
        
        Args:
            time_range: The parsed time range
            kernel_only: Whether only kernel logs were captured
            kernel_result: Result of kernel log capture
            system_result: Result of system log capture (if --all)
        """
        from kernicle.services.sysinfo import get_system_info
        
        sysinfo = get_system_info()
        
        lines = [
            "=" * 70,
            "KERNICLE SESSION REPORT",
            "Kernicle reads the CHAOS; shows the CLARITY",
            "=" * 70,
            "",
            f"Tool: Kernicle v{__version__}",
            f"Session: {self.session_dir.name}",
            f"Created: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "-" * 70,
            "SYSTEM INFORMATION",
            "-" * 70,
            f"Hostname: {sysinfo.hostname}",
            f"OS: {sysinfo.os}",
            f"Kernel: {sysinfo.kernel_version}",
            f"Architecture: {sysinfo.architecture}",
            f"Uptime: {sysinfo.uptime_formatted or 'N/A'}",
            f"Boot Time: {sysinfo.boot_time or 'N/A'}",
            "",
            "-" * 70,
            "CAPTURE PARAMETERS",
            "-" * 70,
            f"Range Input: {time_range.range_input}",
            f"Since (UTC): {time_range.since_utc.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Mode: {'Kernel only' if kernel_only else 'Kernel + System'}",
            "",
            "-" * 70,
            "CAPTURED SOURCES",
            "-" * 70,
        ]
        
        if self.sources:
            for source_name, filename in self.sources.items():
                filepath = self.sources_dir / filename
                size_bytes = filepath.stat().st_size if filepath.exists() else 0
                size_kb = size_bytes / 1024
                lines.append(f"  • {source_name}: {filename} ({size_kb:.1f} KB)")
        else:
            lines.append("  (No sources captured)")
        
        lines.append("")
        
        # Sprint 3: Metrics summary
        lines.extend([
            "-" * 70,
            "SYSTEM METRICS SNAPSHOT",
            "-" * 70,
        ])
        if self.metrics_snapshot and self.metrics_snapshot.psutil_available:
            if self.metrics_snapshot.cpu:
                cpu = self.metrics_snapshot.cpu
                lines.append(f"  CPU: {cpu.get('logical_cores', '?')} cores, {cpu.get('cpu_percent_total', '?')}% usage")
                if 'load_avg' in cpu:
                    load = cpu['load_avg']
                    lines.append(f"  Load Average: {load.get('1min', '?'):.2f} / {load.get('5min', '?'):.2f} / {load.get('15min', '?'):.2f}")
            if self.metrics_snapshot.memory:
                mem = self.metrics_snapshot.memory
                total_gb = mem.get('total_bytes', 0) / (1024**3)
                used_pct = mem.get('percent', 0)
                lines.append(f"  Memory: {total_gb:.1f} GB total, {used_pct}% used")
            if self.metrics_snapshot.disk:
                disk = self.metrics_snapshot.disk
                total_gb = disk.get('total_bytes', 0) / (1024**3)
                used_pct = disk.get('percent', 0)
                lines.append(f"  Disk (/): {total_gb:.1f} GB total, {used_pct}% used")
            lines.append("  (Full metrics available in metrics.json)")
        else:
            lines.append("  Metrics capture unavailable (psutil not installed or error occurred)")
        
        lines.append("")
        
        # Warnings and errors
        if self.warnings:
            lines.extend([
                "-" * 70,
                "WARNINGS / ERRORS",
                "-" * 70,
            ])
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")
        
        # Sprint 2: Executive Summary
        lines.append("")
        lines.append(generate_executive_summary(self.all_findings, self.all_incidents))
        
        # Sprint 2: Incidents Detail
        lines.append(generate_incidents_report(self.all_incidents, self.all_findings))
        
        # Sprint status
        lines.extend([
            "-" * 70,
            "SPRINT STATUS",
            "-" * 70,
            "Sprint 1: Log Capture & Archiving ✓",
            "Sprint 2: Anomaly Detection & Incident Grouping ✓",
            "Sprint 3: System Metrics & Enhanced Manifest ✓",
            "Sprint 4: ZIP Archives & Git Integration ✓",
            "Sprint 5: Background Session Mode ✓",
            "Sprint 6: Export Formats & Enhanced Reports ✓",
            "",
            "Features implemented:",
            "  ✓ Flexible time range parsing (relative and ISO datetime)",
            "  ✓ Kernel and system log capture via journalctl",
            "  ✓ Structured session archives",
            "  ✓ Kernel panic/oops/BUG/OOM detection",
            "  ✓ Incident grouping by time/line proximity",
            "  ✓ Executive summary generation",
            "  ✓ findings.json and incidents.json output",
            "  ✓ System metrics snapshot (psutil)",
            "  ✓ Enhanced manifest with host info",
            "  ✓ Archive structure validation",
            "  ✓ ZIP archive creation",
            "  ✓ Git backup integration",
            "  ✓ Background session mode (start/stop/status)",
            "  ✓ Archive retention cleanup",
            "  ✓ Export to JSON/Markdown/HTML",
            "  ✓ Enhanced system info (kernel, uptime, boot time)",
            "",
            "-" * 70,
            "NOTES",
            "-" * 70,
        ])
        
        if kernel_result and not kernel_result.success:
            lines.extend([
                "Kernel log capture failed:",
                f"  {kernel_result.error}",
                "",
            ])
        
        if system_result and not system_result.success:
            lines.extend([
                "System log capture failed:",
                f"  {system_result.error}",
                "",
            ])
        
        if not self.warnings and kernel_result and kernel_result.success:
            lines.extend([
                "Session completed successfully.",
                "Logs are available in the sources/ directory.",
                "",
            ])
        
        lines.append("=" * 70)
        
        self.report_path.write_text("\n".join(lines), encoding="utf-8")
    
    def _get_severity_summary(self) -> dict:
        """Get severity counts for manifest."""
        counts = {"high": 0, "medium": 0, "low": 0}
        for finding in self.all_findings:
            counts[finding.severity.value] += 1
        return counts
    
    def _get_host_info(self) -> dict:
        """
        Sprint 3: Get host information for manifest.
        Sprint 6: Enhanced with uptime, boot time, kernel version.
        """
        from kernicle.services.sysinfo import get_host_info_for_manifest
        return get_host_info_for_manifest()
    
    def write_manifest(
        self,
        time_range: TimeRange,
        kernel_only: bool
    ) -> None:
        """
        Write the machine-readable manifest.json file.
        Sprint 3: Enhanced with host info, line counts, and layout validation.
        
        Args:
            time_range: The parsed time range
            kernel_only: Whether only kernel logs were captured
        """
        severity_summary = self._get_severity_summary()
        host_info = self._get_host_info()
        
        manifest = {
            "tool": "kernicle",
            "version": __version__,
            "sprint": 4,
            "session_name": self.session_dir.name,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            
            # Capture parameters
            "range_input": time_range.range_input,
            "since_utc": time_range.since_utc.isoformat(),
            "capture_mode": "kernel-only" if kernel_only else "all",
            
            # Sprint 3: Host info
            "host": host_info,
            
            # Sources
            "sources": self.sources,
            
            # Sprint 3: Counts section
            "counts": {
                "captured_sources_count": len(self.sources),
                "total_lines_per_source": self.source_line_counts,
                "warnings_count": len(self.warnings),
            },
            
            "warnings": self.warnings,
            
            "analysis": {
                "findings_count": len(self.all_findings),
                "incidents_count": len(self.all_incidents),
                "severity_summary": severity_summary,
                "has_anomalies": len(self.all_findings) > 0,
            },
            
            # Sprint 4: ZIP archive info
            "zip": self.zip_result.to_dict() if self.zip_result else None,
            
            # Sprint 4: Git backup info
            "git": self.git_result.to_dict() if self.git_result else None,
            
            # AI verdict info
            "ai_verdict": self.ai_result,
            
            # Sprint 3: Archive layout validation
            "archive_layout": {
                "session_dir": str(self.session_dir),
                "report_path": str(self.report_path),
                "manifest_path": str(self.manifest_path),
                "metrics_path": str(self.metrics_path),
                "findings_path": str(self.findings_path),
                "incidents_path": str(self.incidents_path),
                "ai_verdict_path": str(self.ai_verdict_path),
                "sources_dir": str(self.sources_dir),
            },
            
            "files": {
                "report": "report.txt",
                "manifest": "manifest.json",
                "metrics": "metrics.json",
                "findings": "findings.json",
                "incidents": "incidents.json",
                "ai_verdict": "ai_verdict.md",
                "sources_dir": "sources/",
            },
            
            "features": {
                "sprint_1": [
                    "time_range_parsing",
                    "journal_capture",
                    "session_archives",
                    "reports_and_manifests"
                ],
                "sprint_2": [
                    "anomaly_detection",
                    "incident_grouping",
                    "executive_summary",
                    "findings_json",
                    "incidents_json"
                ],
                "sprint_3": [
                    "system_metrics",
                    "enhanced_manifest",
                    "archive_validation",
                    "host_info",
                    "line_counts"
                ],
                "sprint_4": [
                    "zip_archives",
                    "git_integration"
                ],
                "ai_features": [
                    "ai_verdict_generation",
                    "groq_provider",
                    "google_provider",
                    "knowledge_base",
                    "fallback_mode"
                ],
                "planned": [
                    "encryption",
                    "background_mode"
                ]
            }
        }
        
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8"
        )
    
    def validate_archive(self) -> tuple[bool, list[str]]:
        """
        Sprint 3: Validate that the archive structure is complete.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Required files and directories
        required_paths = [
            (self.sources_dir, "sources directory"),
            (self.report_path, "report.txt"),
            (self.manifest_path, "manifest.json"),
            (self.metrics_path, "metrics.json"),
        ]
        
        for path, description in required_paths:
            if not path.exists():
                errors.append(f"Missing {description}: {path}")
        
        return len(errors) == 0, errors
    
    def create_zip(self) -> ZipResult:
        """
        Sprint 4: Create ZIP archive of the session.
        
        Returns:
            ZipResult with success status and details
        """
        self.zip_result = create_session_zip(self.session_dir)
        
        if not self.zip_result.success:
            self.add_warning(f"ZIP creation failed: {self.zip_result.error}")
        
        return self.zip_result
    
    def set_git_result(self, result: GitResult) -> None:
        """
        Sprint 4: Store Git backup result.
        
        Args:
            result: GitResult from backup operation
        """
        self.git_result = result
        
        # Add any errors/warnings to archive warnings
        for error in result.errors:
            self.add_warning(f"Git: {error}")
        for warning in result.warnings:
            self.add_warning(f"Git: {warning}")
    
    def write_ai_verdict(self, crash_info=None) -> None:
        """
        Generate AI verdict file after log capture.
        Creates ai_verdict.md with analysis or fallback message if unavailable.
        
        Args:
            crash_info: Optional CrashDumpInfo from crash dump analysis
        """
        import re
        
        # Prepare log content for AI (minimized)
        log_content = self._prepare_logs_for_ai()
        
        # If crash info provided, prepend it to log content
        if crash_info:
            crash_section = f"""
=== KERNEL CRASH DETECTED ===
Crash Time: {crash_info.timestamp}
Kernel Version: {crash_info.kernel_version}
Panic Message: {crash_info.panic_message or 'Unknown'}

Call Trace:
{chr(10).join(crash_info.call_trace[:30]) if crash_info.call_trace else 'Not available'}

Last Kernel Messages Before Crash:
{chr(10).join(crash_info.dmesg_tail[-30:]) if crash_info.dmesg_tail else 'Not available'}
=== END CRASH INFO ===

"""
            log_content = crash_section + log_content
            
            # Also save crash report to file
            crash_report_path = self.session_dir / "crash_report.txt"
            crash_report_path.write_text(f"""KERNEL CRASH REPORT
==================

Crash Time: {crash_info.timestamp}
Kernel Version: {crash_info.kernel_version}
Dump Location: {crash_info.dump_path}

PANIC MESSAGE:
{crash_info.panic_message or 'Unable to extract'}

CALL TRACE:
{chr(10).join(crash_info.call_trace) if crash_info.call_trace else 'Not available'}

KERNEL LOG (Last messages before crash):
{chr(10).join(crash_info.dmesg_tail) if crash_info.dmesg_tail else 'Not available'}
""", encoding="utf-8")
        
        # Check if AI is available
        if not ai_integration.is_ai_available():
            self._write_fallback_verdict("kernicle-ai plugin not installed", crash_info)
            self.add_warning("AI verdict unavailable: plugin not installed")
            return
        
        # Get system context
        from kernicle.services.sysinfo import get_system_info
        sysinfo = get_system_info()
        context = f"Host: {sysinfo.hostname}, Kernel: {sysinfo.kernel_version}, OS: {sysinfo.os}"
        
        if crash_info:
            context += f", CRASH DETECTED: {crash_info.panic_message or 'Kernel panic'}"
        
        try:
            # Analyze with AI
            result = ai_integration.analyze_logs(log_content, context, timeout=60.0)
            
            if result is None:
                self._write_fallback_verdict("AI analysis returned no result", crash_info)
                self.add_warning("AI verdict unavailable: no response from AI")
                return
            
            # Format and write verdict (pass log_content for severity explanation)
            verdict_content = ai_integration.format_analysis(result, log_content)
            
            # Add crash warning header if crash detected
            if crash_info:
                crash_header = f"""# 🚨 KERNEL CRASH ANALYSIS

**⚠️ A kernel panic was detected and analyzed!**

- **Crash Time:** {crash_info.timestamp}
- **Kernel:** {crash_info.kernel_version}
- **Panic:** {crash_info.panic_message or 'Unknown'}

---

"""
                verdict_content = crash_header + verdict_content
            
            self.ai_verdict_path.write_text(verdict_content, encoding="utf-8")
            
            # Store AI status for manifest
            self.ai_result = {
                "available": True,
                "provider": getattr(result, 'llm_provider', None),
                "used_llm": getattr(result, 'used_llm', False),
                "used_kb": getattr(result, 'used_knowledge_base', False),
                "severity": getattr(result, 'severity', 'unknown'),
                "crash_detected": crash_info is not None,
            }
            
        except Exception as e:
            self._write_fallback_verdict(str(e), crash_info)
            self.add_warning(f"AI verdict unavailable: {str(e)}")
    
    def _prepare_logs_for_ai(self, max_lines: int = 200) -> str:
        """
        Prepare log content for AI analysis.
        - Limits to last N lines
        - Filters for relevant lines (errors, warnings)
        - Redacts obvious secrets
        """
        import re
        
        all_logs = []
        
        # Read kernel logs
        kernel_log = self.sources_dir / "journalctl-kernel.log"
        if kernel_log.exists():
            content = kernel_log.read_text(encoding="utf-8")
            all_logs.extend(content.splitlines())
        
        # Read system logs
        system_log = self.sources_dir / "journalctl-system.log"
        if system_log.exists():
            content = system_log.read_text(encoding="utf-8")
            all_logs.extend(content.splitlines())
        
        if not all_logs:
            return "No logs captured."
        
        # Filter for relevant lines (errors, warnings, important keywords)
        keywords = [
            'error', 'fail', 'panic', 'oops', 'bug', 'warning', 
            'critical', 'oom', 'killed', 'segfault', 'trace'
        ]
        
        filtered = []
        for i, line in enumerate(all_logs):
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                # Add context: 2 lines before and after
                start = max(0, i - 2)
                end = min(len(all_logs), i + 3)
                for j in range(start, end):
                    if all_logs[j] not in filtered:
                        filtered.append(all_logs[j])
        
        # If no filtered lines, use last N lines
        if not filtered:
            filtered = all_logs[-max_lines:]
        else:
            filtered = filtered[-max_lines:]
        
        # Redact obvious secrets (best effort)
        result = "\n".join(filtered)
        result = self._redact_secrets(result)
        
        return result
    
    def _redact_secrets(self, content: str) -> str:
        """Redact obvious secrets from log content."""
        import re
        
        patterns = [
            (r'(password|passwd|pwd)\s*[:=]\s*\S+', r'\1=<REDACTED>'),
            (r'(api_key|apikey|key)\s*[:=]\s*\S+', r'\1=<REDACTED>'),
            (r'(token|auth|secret)\s*[:=]\s*\S+', r'\1=<REDACTED>'),
            (r'Bearer\s+\S+', 'Bearer <REDACTED>'),
            (r'Basic\s+\S+', 'Basic <REDACTED>'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        return content
    
    def _write_fallback_verdict(self, reason: str, crash_info=None) -> None:
        """Write fallback AI verdict when AI is unavailable."""
        
        # Add crash section if crash detected
        crash_section = ""
        if crash_info:
            crash_section = f"""
## 🚨 KERNEL CRASH DETECTED

**A kernel panic was detected!**

- **Crash Time:** {crash_info.timestamp}
- **Kernel Version:** {crash_info.kernel_version}
- **Panic Message:** {crash_info.panic_message or 'Unknown'}

### Call Trace:
```
{chr(10).join(crash_info.call_trace[:20]) if crash_info.call_trace else 'Not available'}
```

---

"""
        
        fallback_content = f"""# 🤖 AI Verdict

**Status:** ⚠️ AI verdict unavailable

**Reason:** {reason}

---
{crash_section}
## 📋 Manual Troubleshooting Steps

Since AI analysis is not available, here are general troubleshooting steps:

### 1. Review the Logs
- Check `sources/journalctl-kernel.log` for kernel-specific issues
- Check `sources/journalctl-system.log` for service/system issues
{f'- Check `crash_report.txt` for crash dump analysis' if crash_info else ''}

### 2. Look for Common Patterns
- **Kernel panic**: System crash, check hardware or driver issues
- **OOM (Out of Memory)**: Memory exhaustion, check running processes
- **Segfault**: Application crash, check application logs
- **Call trace**: Kernel stack dump, indicates serious error

### 3. Check System Resources
```bash
free -h          # Check memory usage
df -h            # Check disk space
dmesg | tail -50 # Recent kernel messages
top -bn1         # Process resource usage
```

### 4. Consult Documentation
- [Kernel Documentation](https://www.kernel.org/doc/html/latest/)
- [Arch Wiki](https://wiki.archlinux.org/)
- [Ubuntu Help](https://help.ubuntu.com/)

---

*Generated by Kernicle v{__version__}*

**To enable AI analysis:**
1. Install kernicle-ai: `pip install kernicle-ai`
2. Set API key: `export GROQ_API_KEY=your_key` or `export GOOGLE_API_KEY=your_key`
"""
        self.ai_verdict_path.write_text(fallback_content, encoding="utf-8")
        
        # Store AI unavailable status for manifest
        self.ai_result = {
            "available": False,
            "reason": reason,
            "crash_detected": crash_info is not None,
        }


def create_session_archive(base_dir: Path, name: Optional[str] = None) -> SessionArchive:
    """
    Create a new session archive with timestamp-based directory name.
    
    Args:
        base_dir: Base directory for archives (e.g., ~/.kernicle/archives)
        name: Optional custom name prefix (default: "session")
              Format: {name}-{timestamp}
        
    Returns:
        SessionArchive instance
    """
    import re
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    
    # Sanitize custom name if provided
    if name:
        # Remove invalid characters, replace spaces with dashes
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '-', name.strip())
        sanitized = re.sub(r'-+', '-', sanitized).strip('-').lower()
        prefix = sanitized if sanitized else "session"
    else:
        prefix = "session"
    
    session_name = f"{prefix}-{timestamp}"
    session_dir = base_dir / session_name
    
    archive = SessionArchive(session_dir)
    archive.create_directories()
    
    return archive
