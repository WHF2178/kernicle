"""
Export functionality for Kernicle session archives.
Sprint 6: Export to JSON, Markdown, and HTML formats.

Provides professional, shareable reports from captured session data.
Automatically includes AI analysis when kernicle-ai plugin is installed.
"""

import json
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from kernicle.services.sysinfo import get_system_info, SystemInfo
from kernicle.services import ai_integration


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    output_path: Optional[Path] = None
    format: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output_path": str(self.output_path) if self.output_path else None,
            "format": self.format,
            "error": self.error,
        }


class SessionExporter:
    """Exports session archives to various formats."""
    
    def __init__(self, session_dir: Path):
        """
        Initialize exporter with session directory.
        
        Args:
            session_dir: Path to session-<timestamp> directory
        """
        self.session_dir = session_dir
        self.manifest_path = session_dir / "manifest.json"
        self.findings_path = session_dir / "findings.json"
        self.incidents_path = session_dir / "incidents.json"
        self.metrics_path = session_dir / "metrics.json"
        self.report_path = session_dir / "report.txt"
        self.sources_dir = session_dir / "sources"
        
        # Loaded data
        self.manifest: dict = {}
        self.findings: list = []
        self.incidents: list = []
        self.metrics: dict = {}
        self.kernel_logs: str = ""
        self.system_logs: str = ""
    
    def load_session_data(self) -> tuple[bool, str]:
        """
        Load all session data from files.
        
        Returns:
            Tuple of (success, error_message)
        """
        if not self.session_dir.exists():
            return False, f"Session directory not found: {self.session_dir}"
        
        if not self.manifest_path.exists():
            return False, f"Manifest not found: {self.manifest_path}"
        
        try:
            # Load manifest (required)
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            
            # Load findings (optional)
            if self.findings_path.exists():
                data = json.loads(self.findings_path.read_text(encoding="utf-8"))
                self.findings = data.get("findings", [])
            
            # Load incidents (optional)
            if self.incidents_path.exists():
                data = json.loads(self.incidents_path.read_text(encoding="utf-8"))
                self.incidents = data.get("incidents", [])
            
            # Load metrics (optional)
            if self.metrics_path.exists():
                self.metrics = json.loads(self.metrics_path.read_text(encoding="utf-8"))
            
            # Load log sources (optional)
            kernel_log_path = self.sources_dir / "journalctl-kernel.log"
            if kernel_log_path.exists():
                self.kernel_logs = kernel_log_path.read_text(encoding="utf-8")
            
            system_log_path = self.sources_dir / "journalctl-system.log"
            if system_log_path.exists():
                self.system_logs = system_log_path.read_text(encoding="utf-8")
            
            return True, ""
            
        except json.JSONDecodeError as e:
            return False, f"JSON parse error: {e}"
        except Exception as e:
            return False, f"Failed to load session data: {e}"
    
    def export_json(self, output_path: Path) -> ExportResult:
        """
        Export session data as JSON.
        
        Args:
            output_path: Path to write JSON file
            
        Returns:
            ExportResult
        """
        success, error = self.load_session_data()
        if not success:
            return ExportResult(success=False, format="json", error=error)
        
        try:
            export_data = {
                "export_info": {
                    "exported_utc": datetime.now(timezone.utc).isoformat(),
                    "format": "json",
                    "session_id": self.session_dir.name,
                },
                "manifest": self.manifest,
                "findings": self.findings,
                "incidents": self.incidents,
                "metrics": self.metrics,
                "summary": self._generate_summary(),
            }
            
            # Add AI analysis if available
            if ai_integration.is_ai_available():
                log_content = self.kernel_logs or self.system_logs
                if log_content:
                    system_context = self._get_system_context()
                    export_data = ai_integration.enhance_export_data(
                        export_data, log_content, system_context
                    )
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(export_data, indent=2, default=str),
                encoding="utf-8"
            )
            
            return ExportResult(success=True, output_path=output_path, format="json")
            
        except Exception as e:
            return ExportResult(success=False, format="json", error=str(e))
    
    def export_markdown(self, output_path: Path) -> ExportResult:
        """
        Export session data as Markdown.
        
        Args:
            output_path: Path to write Markdown file
            
        Returns:
            ExportResult
        """
        success, error = self.load_session_data()
        if not success:
            return ExportResult(success=False, format="md", error=error)
        
        try:
            md = self._generate_markdown()
            
            # Add AI analysis if available
            if ai_integration.is_ai_available():
                log_content = self.kernel_logs or self.system_logs
                if log_content:
                    system_context = self._get_system_context()
                    result = ai_integration.analyze_logs(log_content, system_context)
                    if result:
                        ai_md = ai_integration.format_analysis(result)
                        if ai_md:
                            md = md + "\n\n" + ai_md
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(md, encoding="utf-8")
            
            return ExportResult(success=True, output_path=output_path, format="md")
            
        except Exception as e:
            return ExportResult(success=False, format="md", error=str(e))
    
    def export_html(self, output_path: Path) -> ExportResult:
        """
        Export session data as styled HTML.
        
        Args:
            output_path: Path to write HTML file
            
        Returns:
            ExportResult
        """
        success, error = self.load_session_data()
        if not success:
            return ExportResult(success=False, format="html", error=error)
        
        try:
            # Get AI analysis first (if available) so we can include it in HTML
            ai_html = ""
            if ai_integration.is_ai_available():
                log_content = self.kernel_logs or self.system_logs
                if log_content:
                    system_context = self._get_system_context()
                    result = ai_integration.analyze_logs(log_content, system_context)
                    if result:
                        ai_html = ai_integration.get_html_analysis(result)
            
            html_content = self._generate_html(ai_html)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding="utf-8")
            
            return ExportResult(success=True, output_path=output_path, format="html")
            
        except Exception as e:
            return ExportResult(success=False, format="html", error=str(e))
    
    def _get_system_context(self) -> str:
        """Get system context for AI analysis."""
        host = self.manifest.get("host", {})
        return f"""System: {host.get('os', 'Unknown')}
Kernel: {host.get('kernel_version', 'Unknown')}
Architecture: {host.get('architecture', 'Unknown')}
Hostname: {host.get('hostname', 'Unknown')}"""
    
    def _generate_summary(self) -> dict:
        """Generate summary statistics."""
        critical_count = sum(1 for f in self.findings if f.get("severity") == "critical")
        warning_count = sum(1 for f in self.findings if f.get("severity") == "warning")
        info_count = sum(1 for f in self.findings if f.get("severity") == "info")
        
        return {
            "total_findings": len(self.findings),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "total_incidents": len(self.incidents),
            "kernel_log_lines": len(self.kernel_logs.splitlines()) if self.kernel_logs else 0,
            "system_log_lines": len(self.system_logs.splitlines()) if self.system_logs else 0,
        }
    
    def _generate_markdown(self) -> str:
        """Generate Markdown report content."""
        summary = self._generate_summary()
        host = self.manifest.get("host", {})
        capture = self.manifest.get("capture", {})
        
        lines = [
            "# Kernicle Session Report",
            "",
            f"> **Session ID:** `{self.session_dir.name}`",
            f"> **Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "---",
            "",
            "## System Information",
            "",
            "| Property | Value |",
            "|----------|-------|",
            f"| Hostname | `{host.get('hostname', 'N/A')}` |",
            f"| OS | {host.get('os', 'N/A')} |",
            f"| Kernel | `{host.get('kernel_version', 'N/A')}` |",
            f"| Architecture | {host.get('architecture', 'N/A')} |",
            f"| Uptime | {host.get('uptime_formatted', 'N/A')} |",
            f"| Boot Time | {host.get('boot_time', 'N/A')} |",
            "",
            "## Capture Details",
            "",
            f"- **Time Range:** `{capture.get('range_input', 'N/A')}`",
            f"- **Since:** {capture.get('since_utc', 'N/A')}",
            f"- **Mode:** {'Kernel only' if capture.get('kernel_only') else 'All logs'}",
            "",
            "## Summary",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| 🔴 Critical | {summary['critical_count']} |",
            f"| 🟡 Warning | {summary['warning_count']} |",
            f"| 🔵 Info | {summary['info_count']} |",
            f"| 📊 Total Findings | {summary['total_findings']} |",
            f"| 📁 Incidents | {summary['total_incidents']} |",
            "",
        ]
        
        # Incidents section
        if self.incidents:
            lines.extend([
                "## Incidents",
                "",
            ])
            for i, incident in enumerate(self.incidents, 1):
                severity = incident.get("severity", "info")
                severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
                lines.extend([
                    f"### {severity_icon} Incident {i}: {incident.get('title', 'Unknown')}",
                    "",
                    f"**Severity:** {severity.upper()}  ",
                    f"**Time:** {incident.get('first_seen', 'N/A')} - {incident.get('last_seen', 'N/A')}  ",
                    f"**Finding Count:** {incident.get('finding_count', 0)}",
                    "",
                    "**Summary:**",
                    f"> {incident.get('summary', 'No summary available')}",
                    "",
                ])
        
        # Findings section (collapsed in MD)
        if self.findings:
            lines.extend([
                "## Findings Detail",
                "",
                "<details>",
                "<summary>Click to expand all findings</summary>",
                "",
            ])
            for finding in self.findings:
                severity = finding.get("severity", "info")
                lines.extend([
                    f"#### [{severity.upper()}] {finding.get('rule_name', 'Unknown')}",
                    "",
                    f"**Line {finding.get('line_number', '?')}:** `{finding.get('matched_text', '')[:100]}`",
                    "",
                    f"**Message:** {finding.get('message', 'N/A')}",
                    "",
                    "---",
                    "",
                ])
            lines.extend([
                "</details>",
                "",
            ])
        
        # Metrics section
        if self.metrics:
            cpu = self.metrics.get("cpu", {})
            memory = self.metrics.get("memory", {})
            lines.extend([
                "## System Metrics",
                "",
                "### CPU",
                f"- Usage: {cpu.get('percent', 'N/A')}%",
                f"- Cores: {cpu.get('count', 'N/A')}",
                "",
                "### Memory",
                f"- Used: {memory.get('percent', 'N/A')}%",
                f"- Total: {self._format_bytes(memory.get('total', 0))}",
                f"- Available: {self._format_bytes(memory.get('available', 0))}",
                "",
            ])
        
        lines.extend([
            "---",
            "",
            "*Report generated by [Kernicle](https://github.com/kernicle) - \"reads the CHAOS; shows the CLARITY\"*",
        ])
        
        return "\n".join(lines)
    
    def _generate_html(self, ai_html: str = "") -> str:
        """Generate styled HTML report.
        
        Args:
            ai_html: Optional AI analysis HTML section to include
        """
        summary = self._generate_summary()
        host = self.manifest.get("host", {})
        capture = self.manifest.get("capture", {})
        
        # CSS styles
        css = """
        :root {
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --text-primary: #eaeaea;
            --text-secondary: #a0a0a0;
            --accent: #0f3460;
            --critical: #e94560;
            --warning: #f39c12;
            --info: #3498db;
            --success: #27ae60;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, var(--bg-card), var(--accent));
            border-radius: 12px;
            margin-bottom: 2rem;
        }
        header h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        header .slogan { color: var(--text-secondary); font-style: italic; }
        header .session-id { 
            font-family: monospace; 
            background: rgba(255,255,255,0.1); 
            padding: 0.25rem 0.75rem; 
            border-radius: 4px;
            display: inline-block;
            margin-top: 1rem;
        }
        .card {
            background: var(--bg-card);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .card h2 {
            color: var(--text-primary);
            border-bottom: 2px solid var(--accent);
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
        }
        .stat-box {
            background: var(--accent);
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }
        .stat-box .value {
            font-size: 2rem;
            font-weight: bold;
        }
        .stat-box.critical .value { color: var(--critical); }
        .stat-box.warning .value { color: var(--warning); }
        .stat-box.info .value { color: var(--info); }
        .stat-box.success .value { color: var(--success); }
        .stat-box .label { color: var(--text-secondary); font-size: 0.875rem; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: left;
            padding: 0.75rem;
            border-bottom: 1px solid var(--accent);
        }
        th { color: var(--text-secondary); font-weight: 500; }
        td code {
            background: rgba(255,255,255,0.1);
            padding: 0.125rem 0.375rem;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
        }
        .incident {
            border-left: 4px solid var(--info);
            padding-left: 1rem;
            margin-bottom: 1.5rem;
        }
        .incident.critical { border-color: var(--critical); }
        .incident.warning { border-color: var(--warning); }
        .incident h3 { margin-bottom: 0.5rem; }
        .incident .meta { color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 0.5rem; }
        .incident .summary { 
            background: rgba(255,255,255,0.05); 
            padding: 0.75rem; 
            border-radius: 4px;
            font-style: italic;
        }
        .severity-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        .severity-badge.critical { background: var(--critical); }
        .severity-badge.warning { background: var(--warning); color: #000; }
        .severity-badge.info { background: var(--info); }
        details {
            background: rgba(255,255,255,0.02);
            border-radius: 4px;
            margin-bottom: 0.5rem;
        }
        details summary {
            padding: 0.75rem;
            cursor: pointer;
            user-select: none;
        }
        details summary:hover { background: rgba(255,255,255,0.05); }
        details .content { padding: 0 1rem 1rem; }
        .finding-line {
            font-family: monospace;
            font-size: 0.875rem;
            background: rgba(0,0,0,0.3);
            padding: 0.5rem;
            border-radius: 4px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
        }
        footer a { color: var(--info); text-decoration: none; }
        @media (max-width: 768px) {
            body { padding: 1rem; }
            header h1 { font-size: 1.75rem; }
        }
        /* AI Analysis styles */
        .ai-analysis {
            background: linear-gradient(135deg, #1a1a3e, #16214e);
            border: 1px solid #3498db;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .ai-analysis h2 { color: #3498db; margin-bottom: 1rem; }
        .ai-analysis h3 { color: var(--text-primary); margin-top: 1rem; margin-bottom: 0.5rem; }
        .ai-analysis ol, .ai-analysis ul { margin-left: 1.5rem; }
        .ai-analysis li { margin-bottom: 0.5rem; }
        .ai-analysis a { color: #3498db; }
        .ai-footer { margin-top: 1rem; color: var(--text-secondary); font-size: 0.875rem; }
        """
        
        # Build HTML
        incidents_html = ""
        if self.incidents:
            for incident in self.incidents:
                severity = incident.get("severity", "info")
                incidents_html += f"""
                <div class="incident {severity}">
                    <h3><span class="severity-badge {severity}">{severity}</span> {html.escape(incident.get('title', 'Unknown'))}</h3>
                    <div class="meta">
                        {incident.get('first_seen', 'N/A')} — {incident.get('finding_count', 0)} findings
                    </div>
                    <div class="summary">{html.escape(incident.get('summary', 'No summary'))}</div>
                </div>
                """
        else:
            incidents_html = "<p>No incidents detected.</p>"
        
        findings_html = ""
        if self.findings:
            for finding in self.findings:
                severity = finding.get("severity", "info")
                findings_html += f"""
                <details>
                    <summary>
                        <span class="severity-badge {severity}">{severity}</span>
                        Line {finding.get('line_number', '?')}: {html.escape(finding.get('rule_name', 'Unknown'))}
                    </summary>
                    <div class="content">
                        <p><strong>Message:</strong> {html.escape(finding.get('message', 'N/A'))}</p>
                        <div class="finding-line">{html.escape(finding.get('matched_text', '')[:200])}</div>
                    </div>
                </details>
                """
        else:
            findings_html = "<p>No findings.</p>"
        
        metrics_html = ""
        if self.metrics:
            cpu = self.metrics.get("cpu", {})
            memory = self.metrics.get("memory", {})
            metrics_html = f"""
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="value">{cpu.get('percent', 'N/A')}%</div>
                    <div class="label">CPU Usage</div>
                </div>
                <div class="stat-box">
                    <div class="value">{memory.get('percent', 'N/A')}%</div>
                    <div class="label">Memory Usage</div>
                </div>
                <div class="stat-box">
                    <div class="value">{cpu.get('count', 'N/A')}</div>
                    <div class="label">CPU Cores</div>
                </div>
                <div class="stat-box">
                    <div class="value">{self._format_bytes(memory.get('total', 0))}</div>
                    <div class="label">Total Memory</div>
                </div>
            </div>
            """
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kernicle Report - {html.escape(self.session_dir.name)}</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 Kernicle Report</h1>
            <p class="slogan">"reads the CHAOS; shows the CLARITY"</p>
            <div class="session-id">{html.escape(self.session_dir.name)}</div>
        </header>
        
        <div class="card">
            <h2>📊 Summary</h2>
            <div class="stats-grid">
                <div class="stat-box critical">
                    <div class="value">{summary['critical_count']}</div>
                    <div class="label">Critical</div>
                </div>
                <div class="stat-box warning">
                    <div class="value">{summary['warning_count']}</div>
                    <div class="label">Warnings</div>
                </div>
                <div class="stat-box info">
                    <div class="value">{summary['info_count']}</div>
                    <div class="label">Info</div>
                </div>
                <div class="stat-box success">
                    <div class="value">{summary['total_incidents']}</div>
                    <div class="label">Incidents</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>🖥️ System Information</h2>
            <table>
                <tr><th>Hostname</th><td><code>{html.escape(host.get('hostname', 'N/A'))}</code></td></tr>
                <tr><th>OS</th><td>{html.escape(host.get('os', 'N/A'))}</td></tr>
                <tr><th>Kernel</th><td><code>{html.escape(host.get('kernel_version', 'N/A'))}</code></td></tr>
                <tr><th>Architecture</th><td>{html.escape(host.get('architecture', 'N/A'))}</td></tr>
                <tr><th>Uptime</th><td>{html.escape(host.get('uptime_formatted', 'N/A'))}</td></tr>
                <tr><th>Boot Time</th><td>{html.escape(host.get('boot_time', 'N/A'))}</td></tr>
            </table>
        </div>
        
        <div class="card">
            <h2>📅 Capture Details</h2>
            <table>
                <tr><th>Time Range</th><td><code>{html.escape(capture.get('range_input', 'N/A'))}</code></td></tr>
                <tr><th>Since</th><td>{html.escape(capture.get('since_utc', 'N/A'))}</td></tr>
                <tr><th>Mode</th><td>{'Kernel only' if capture.get('kernel_only') else 'All logs'}</td></tr>
                <tr><th>Kernel Lines</th><td>{summary['kernel_log_lines']}</td></tr>
                <tr><th>System Lines</th><td>{summary['system_log_lines']}</td></tr>
            </table>
        </div>
        
        <div class="card">
            <h2>⚠️ Incidents</h2>
            {incidents_html}
        </div>
        
        <div class="card">
            <h2>🔎 Findings</h2>
            {findings_html}
        </div>
        
        {"<div class='card'><h2>📈 Metrics</h2>" + metrics_html + "</div>" if metrics_html else ""}
        
        {ai_html if ai_html else ""}
        
        <footer>
            <p>Generated by <a href="https://github.com/kernicle">Kernicle</a> on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html_content
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human-readable string."""
        if bytes_val == 0:
            return "0 B"
        value = float(bytes_val)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(value) < 1024:
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} PB"


def export_session(
    session_dir: Path,
    output_path: Path,
    format: str,
) -> ExportResult:
    """
    Export a session to the specified format.
    
    Args:
        session_dir: Path to session directory
        output_path: Path to write output file
        format: Export format (json, md, html)
        
    Returns:
        ExportResult
    """
    exporter = SessionExporter(session_dir)
    
    if format == "json":
        return exporter.export_json(output_path)
    elif format == "md":
        return exporter.export_markdown(output_path)
    elif format == "html":
        return exporter.export_html(output_path)
    else:
        return ExportResult(
            success=False,
            format=format,
            error=f"Unsupported format: {format}. Use json, md, or html."
        )


def find_session(archives_dir: Path, session_id: str) -> Optional[Path]:
    """
    Find a session directory by ID or partial match.
    
    Args:
        archives_dir: Path to archives directory
        session_id: Full or partial session ID
        
    Returns:
        Path to session directory or None if not found
    """
    if not archives_dir.exists():
        return None
    
    # Try exact match first
    exact_match = archives_dir / session_id
    if exact_match.is_dir():
        return exact_match
    
    # Try with session- prefix
    if not session_id.startswith("session-"):
        prefixed = archives_dir / f"session-{session_id}"
        if prefixed.is_dir():
            return prefixed
    
    # Try partial match (find sessions containing the ID)
    matches = [
        d for d in archives_dir.iterdir()
        if d.is_dir() and session_id in d.name
    ]
    
    if len(matches) == 1:
        return matches[0]
    
    return None
