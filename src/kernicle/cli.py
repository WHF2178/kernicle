"""
CLI interface for Kernicle.
Implements commands using Typer and Rich for beautiful terminal output.
Sprint 4: Added ZIP archive creation and optional Git backup.
Sprint 5: Added background session mode (start/status/stop).
"""

import os
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from kernicle import __version__
from kernicle.config import config
from kernicle.services.timeparse import parse_range
from kernicle.services.journal import capture_kernel, capture_system
from kernicle.services.archive import create_session_archive
from kernicle.services.gitbackup import is_git_available, backup_to_git, GitConfig


app = typer.Typer(
    name="kernicle",
    help="Kernicle reads the CHAOS; shows the CLARITY - Linux journal log analyzer",
    add_completion=False,
)

console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"Kernicle v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    )
):
    """Kernicle - Linux journal log analyzer."""
    pass


@app.command()
def push(
    range_spec: str = typer.Option(
        ...,
        "--range",
        "-r",
        help="Time range: 'last:5m', 'last:30m', 'last:2h', 'last:1d' or ISO datetime"
    ),
    kernel_only: bool = typer.Option(
        False,
        "--kernel-only",
        "-k",
        help="Capture kernel logs only"
    ),
    all_logs: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Capture both kernel and system logs"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-N",
        help="Custom session name (e.g., 'nginx-crash' creates nginx-crash-20260104-120000)"
    ),
    git_backup: bool = typer.Option(
        False,
        "--git/--no-git",
        help="Backup session ZIP to Git repository (requires KERNICLE_GIT_* env vars)"
    ),
):
    """
    Capture journal logs and create a session archive.
    
    Examples:
        kernicle push --range "last:5m" --kernel-only
        kernicle push --range "last:30m" --all
        kernicle push -r "last:10m" -k -N "nginx-crash"
        kernicle push --range "last:10m" --all --name "prod-incident"
        kernicle push --range "last:10m" --all --git
    """
    # Ensure config directories exist
    config.ensure_directories()
    
    # Validate options
    if not kernel_only and not all_logs:
        console.print("[red]Error:[/red] Must specify either --kernel-only or --all")
        raise typer.Exit(1)
    
    if kernel_only and all_logs:
        console.print("[yellow]Warning:[/yellow] Both --kernel-only and --all specified. Using --all.")
        kernel_only = False
    
    # Parse time range
    try:
        time_range = parse_range(range_spec)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)
    
    # Show capture info
    console.print(Panel.fit(
        f"[bold cyan]Kernicle v{__version__}[/bold cyan]\n"
        f"Range: [yellow]{time_range.range_input}[/yellow]\n"
        f"Since: [green]{time_range.since_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}[/green]\n"
        f"Mode: [magenta]{'Kernel + System' if all_logs else 'Kernel only'}[/magenta]",
        title="📝 Capturing Logs",
        border_style="cyan"
    ))
    
    # ==========================================================================
    # AUTO-DETECT AND ANALYZE CRASH DUMPS
    # ==========================================================================
    from kernicle.services.crashdump import CrashDumpManager
    
    crash_manager = CrashDumpManager()
    crash_dumps = crash_manager.list_crash_dumps()
    unanalyzed_crashes = [d for d in crash_dumps if not d.get("analyzed", False)]
    
    # Store crash info for later inclusion in AI analysis
    detected_crash_info = None
    
    if unanalyzed_crashes:
        console.print(Panel.fit(
            f"[bold red]🚨 {len(unanalyzed_crashes)} UNANALYZED CRASH DUMP(S) DETECTED![/bold red]\n"
            f"Your system experienced kernel panic(s).\n"
            f"Analyzing automatically...",
            title="⚠️ Crash Detected",
            border_style="red"
        ))
        
        for crash in unanalyzed_crashes:
            crash_path = Path(crash["vmcore"])
            console.print(f"\n[yellow]Analyzing crash: {crash_path.parent.name}[/yellow]")
            
            with console.status("[bold green]Extracting crash information..."):
                crash_info = crash_manager.analyze_crash_dump(crash_path)
            
            if crash_info:
                console.print(f"[green]✓[/green] Crash analyzed: {crash_info.panic_message or 'Kernel panic'}")
                detected_crash_info = crash_info  # Save for AI analysis
                
                # Mark as analyzed
                import json
                analysis_marker = crash_path.parent / "kernicle_analysis.json"
                analysis_marker.write_text(json.dumps({
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                    "panic_message": crash_info.panic_message,
                }), encoding="utf-8")
            else:
                console.print(f"[yellow]⚠[/yellow] Could not fully analyze crash dump")
        
        console.print("")  # Blank line before continuing
    
    # ==========================================================================
    # NORMAL LOG CAPTURE
    # ==========================================================================
    
    # Create session archive
    archive = create_session_archive(config.archives_dir, name=name)
    console.print(f"Session: [cyan]{archive.session_dir.name}[/cyan]")
    
    # Capture kernel logs
    with console.status("[bold green]Capturing kernel logs..."):
        kernel_result = capture_kernel(time_range.since_arg)
    
    if kernel_result.success:
        archive.write_source("kernel", "journalctl-kernel.log", kernel_result.output)
        console.print("[green]✓[/green] Kernel logs captured")
    else:
        console.print(f"[red]✗[/red] Kernel log capture failed")
        archive.add_warning(f"Kernel capture failed: {kernel_result.error}")
    
    # Capture system logs if --all
    system_result = None
    if all_logs:
        with console.status("[bold green]Capturing system logs..."):
            system_result = capture_system(time_range.since_arg)
        
        if system_result.success:
            archive.write_source("system", "journalctl-system.log", system_result.output)
            console.print("[green]✓[/green] System logs captured")
        else:
            console.print(f"[red]✗[/red] System log capture failed")
            archive.add_warning(f"System capture failed: {system_result.error}")
    
    # Sprint 2: Finalize analysis (group findings into incidents)
    with console.status("[bold green]Analyzing logs for anomalies..."):
        archive.finalize_analysis()
    
    findings_count = len(archive.all_findings)
    incidents_count = len(archive.all_incidents)
    
    if findings_count > 0:
        console.print(f"[yellow]⚠[/yellow] Detected [bold]{findings_count}[/bold] finding(s) in [bold]{incidents_count}[/bold] incident(s)")
    else:
        console.print("[green]✓[/green] No anomalies detected")
    
    # Sprint 3: Capture system metrics
    with console.status("[bold green]Capturing system metrics..."):
        archive.capture_metrics()
    
    if archive.metrics_snapshot and archive.metrics_snapshot.psutil_available:
        console.print("[green]✓[/green] System metrics captured")
    else:
        console.print("[yellow]⚠[/yellow] Metrics capture limited (psutil unavailable)")
    
    # Write Sprint 2 output files
    archive.write_findings()
    archive.write_incidents()
    
    # Sprint 3: Write metrics
    archive.write_metrics()
    
    # Generate AI verdict (always runs, gracefully handles unavailability)
    # Pass crash info if a crash was detected
    with console.status("[bold green]Generating AI verdict..."):
        archive.write_ai_verdict(crash_info=detected_crash_info)
    
    if archive.ai_result and archive.ai_result.get("available"):
        provider = archive.ai_result.get("provider", "AI")
        crash_note = " (includes crash analysis)" if archive.ai_result.get("crash_detected") else ""
        console.print(f"[green]✓[/green] AI verdict generated ({provider}){crash_note}")
    else:
        reason = archive.ai_result.get("reason", "unknown") if archive.ai_result else "not configured"
        console.print(f"[yellow]⚠[/yellow] AI verdict: fallback mode ({reason})")
    
    # Write report and manifest (after AI verdict so AI status is included)
    archive.write_report(time_range, kernel_only, kernel_result, system_result)
    archive.write_manifest(time_range, kernel_only)
    
    # Sprint 3: Validate archive structure
    is_valid, validation_errors = archive.validate_archive()
    if not is_valid:
        console.print("\n[red]Archive validation failed![/red]")
        for error in validation_errors:
            console.print(f"  [red]✗[/red] {error}")
        raise typer.Exit(1)
    
    # Sprint 4: Create ZIP archive
    with console.status("[bold green]Creating ZIP archive..."):
        zip_result = archive.create_zip()
    
    if zip_result.success:
        size_kb = zip_result.zip_size_bytes / 1024
        if size_kb > 1024:
            size_str = f"{size_kb/1024:.1f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"
        console.print(f"[green]✓[/green] ZIP archive created ({size_str})")
    else:
        console.print(f"[red]✗[/red] ZIP creation failed: {zip_result.error}")
        archive.add_warning(f"ZIP creation failed: {zip_result.error}")
    
    # Sprint 4: Git backup (if requested)
    if git_backup:
        if not is_git_available():
            console.print("[yellow]⚠[/yellow] Git not available - skipping backup")
            archive.add_warning("Git backup skipped: git command not found")
        elif not config.is_git_configured():
            console.print("[yellow]⚠[/yellow] Git not configured - set KERNICLE_GIT_REMOTE, KERNICLE_GIT_REPO_DIR")
            archive.add_warning("Git backup skipped: missing KERNICLE_GIT_* environment variables")
        elif not zip_result.success or zip_result.zip_path is None:
            console.print("[yellow]⚠[/yellow] Git backup skipped - no ZIP file available")
            archive.add_warning("Git backup skipped: ZIP creation failed")
        else:
            with console.status("[bold green]Backing up to Git..."):
                git_config = GitConfig.from_env(config.base_dir)
                git_result = backup_to_git(zip_result.zip_path, git_config)
                archive.set_git_result(git_result)
            
            if git_result.success:
                status_parts = []
                if git_result.committed:
                    status_parts.append("committed")
                if git_result.pushed:
                    status_parts.append("pushed")
                status_str = " & ".join(status_parts) if status_parts else "no changes"
                console.print(f"[green]✓[/green] Git backup complete ({status_str})")
                if git_result.commit_hash:
                    console.print(f"  [dim]Commit: {git_result.commit_hash[:8]}[/dim]")
            else:
                console.print(f"[yellow]⚠[/yellow] Git backup had issues:")
                for error in git_result.errors:
                    console.print(f"  [red]✗[/red] {error}")
                for warning in git_result.warnings:
                    console.print(f"  [yellow]⚠[/yellow] {warning}")
    
    # Update manifest with ZIP and Git results
    archive.write_manifest(time_range, kernel_only)
    
    # Show summary
    console.print("\n[bold green]Session complete![/bold green]")
    console.print(f"Location: [cyan]{archive.session_dir}[/cyan]")
    if zip_result.success:
        console.print(f"ZIP file: [cyan]{zip_result.zip_path}[/cyan]")
    
    if archive.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in archive.warnings:
            console.print(f"  ⚠ {warning}")
    
    console.print("\n[dim]View report: cat ~/.kernicle/archives/{}/report.txt[/dim]".format(
        archive.session_dir.name
    ))


@app.command()
def show(
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Number of archives to show"
    ),
    local: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Show local sessions"
    ),
    github: bool = typer.Option(
        False,
        "--github",
        "-g",
        help="Show GitHub archives"
    ),
):
    """
    List capture sessions and archives.
    
    Examples:
        kernicle show           # Default: local sessions
        kernicle show -l        # Local sessions only
        kernicle show -g        # GitHub archives only
        kernicle show -l -g     # Both local and GitHub
        kernicle show -n 5 -g   # Show 5 GitHub archives
    """
    import subprocess
    import tempfile
    import shutil
    
    # Default: if neither flag specified, show local
    show_local = local or (not local and not github)
    show_github = github
    
    # Show local sessions
    if show_local:
        sessions = config.list_sessions(limit=limit)
        
        if not sessions:
            console.print("[yellow]No local sessions found.[/yellow]")
            console.print(f"Hint: Run [cyan]kernicle push --range 'last:5m' --kernel-only[/cyan] to create a session.")
        else:
            table = Table(
                title=f"📁 Local Sessions (showing {len(sessions)})",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan"
            )
            
            table.add_column("Session", style="cyan")
            table.add_column("Created", style="green")
            table.add_column("Sources", style="yellow")
            table.add_column("Size", justify="right", style="magenta")
            table.add_column("ZIP", justify="center", style="blue")
            
            for session_path in sessions:
                created = session_path.stat().st_mtime
                from datetime import datetime
                created_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
                
                sources_dir = session_path / "sources"
                if sources_dir.exists():
                    source_files = list(sources_dir.glob("*.log"))
                    sources_str = f"{len(source_files)} files"
                else:
                    sources_str = "0 files"
                
                total_size = 0
                if sources_dir.exists():
                    for f in sources_dir.rglob("*"):
                        if f.is_file():
                            total_size += f.stat().st_size
                
                size_kb = total_size / 1024
                size_str = f"{size_kb/1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
                
                zip_files = list(session_path.glob("*.zip"))
                zip_str = "✓" if zip_files else "-"
                
                table.add_row(session_path.name, created_str, sources_str, size_str, zip_str)
            
            console.print(table)
            console.print(f"\n[dim]Location: {config.archives_dir}[/dim]")
    
    # Show GitHub archives
    if show_github:
        git_remote = os.environ.get("KERNICLE_GIT_REMOTE", "")
        
        if not git_remote:
            if show_local:
                console.print("\n")
            console.print("[yellow]GitHub not configured.[/yellow]")
            console.print("[dim]Set KERNICLE_GIT_REMOTE environment variable[/dim]")
            return
        
        if show_local:
            console.print("\n")
        
        try:
            temp_dir = tempfile.mkdtemp(prefix="kernicle-show-")
            result = subprocess.run(
                ["git", "clone", "--quiet", "--depth", "1", git_remote, temp_dir],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                console.print(f"[red]Failed to access GitHub: {result.stderr.strip()}[/red]")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            
            git_archives_dir = Path(temp_dir) / "archives"
            
            if not git_archives_dir.exists():
                console.print("[yellow]No archives folder in GitHub repo[/yellow]")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            
            import re
            # Extract timestamp from filename for sorting (YYYYMMDD-HHMMSS)
            def get_timestamp(p: Path) -> str:
                match = re.search(r'(\d{8}-\d{6})', p.name)
                return match.group(1) if match else p.name
            
            git_zips = sorted(
                [f for f in git_archives_dir.iterdir() if f.suffix == ".zip"],
                key=get_timestamp,
                reverse=True
            )[:limit]
            
            if not git_zips:
                console.print("[yellow]No ZIP archives in GitHub repo[/yellow]")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            
            git_table = Table(
                title=f"☁️  GitHub Archives (showing {len(git_zips)})",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan"
            )
            
            git_table.add_column("Archive", style="cyan")
            git_table.add_column("Size", justify="right", style="magenta")
            
            total_git_size = 0
            for zip_file in git_zips:
                size = zip_file.stat().st_size
                total_git_size += size
                size_kb = size / 1024
                size_str = f"{size_kb/1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
                git_table.add_row(zip_file.name, size_str)
            
            console.print(git_table)
            
            total_kb = total_git_size / 1024
            total_str = f"{total_kb/1024:.1f} MB" if total_kb > 1024 else f"{total_kb:.1f} KB"
            console.print(f"\n[dim]Total: {len(git_zips)} archives, {total_str}[/dim]")
            console.print(f"[dim]Remote: {git_remote}[/dim]")
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except subprocess.TimeoutExpired:
            console.print("[red]GitHub fetch timed out[/red]")
        except Exception as e:
            console.print(f"[red]Error fetching GitHub: {e}[/red]")


# Sprint 5: Background session commands

@app.command()
def start(
    range_spec: str = typer.Option(
        "last:5m",
        "--range",
        "-r",
        help="Time range for each capture cycle: 'last:5m', 'last:10m', etc."
    ),
    collect_every: int = typer.Option(
        10,
        "--collect-every",
        "-c",
        help="Seconds between log captures [default: 10]"
    ),
    archive_every: int = typer.Option(
        120,
        "--archive-every",
        "-e",
        help="Seconds between archive creations [default: 120]"
    ),
    duration: int = typer.Option(
        None,
        "--duration",
        "-d",
        help="Total duration in seconds (optional, runs until stopped if not set)"
    ),
    kernel_only: bool = typer.Option(
        False,
        "--kernel-only", "-k",
        help="Capture kernel logs only"
    ),
    all_logs: bool = typer.Option(
        False,
        "--all", "-a",
        help="Capture both kernel and system logs"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-N",
        help="Custom session name prefix (e.g., 'ABC-Crash')"
    ),
    git_backup: bool = typer.Option(
        False,
        "--git/--no-git",
        help="Backup archives to Git repository"
    ),
    max_archives: int = typer.Option(
        20,
        "--max-archives",
        "-m",
        help="Maximum number of archives to keep (retention)"
    ),
):
    """
    Start a background capture session.
    
    The session runs in the background, capturing logs at regular intervals
    and creating archives periodically.
    
    Examples:
        kernicle start --all
        kernicle start -a -c 60 -e 600 -d 1800
        kernicle start -k -N "prod-monitor"
        kernicle start --range "last:10m" -a --name "nginx-debug" --git
    """
    from kernicle.services.session import (
        SessionConfig,
        start_background_session,
        SessionManager,
    )
    
    # Ensure config directories exist
    config.ensure_directories()
    
    # Validate options
    if not kernel_only and not all_logs:
        console.print("[red]Error:[/red] Must specify either --kernel-only or --all")
        raise typer.Exit(1)
    
    if kernel_only and all_logs:
        console.print("[yellow]Warning:[/yellow] Both --kernel-only and --all specified. Using --all.")
        kernel_only = False
    
    # Validate time range
    try:
        parse_range(range_spec)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid time range: {str(e)}")
        raise typer.Exit(1)
    
    # Check if already running
    manager = SessionManager(config.session_dir)
    is_running, existing = manager.is_session_running()
    if is_running:
        console.print(f"[red]Error:[/red] A session is already running (PID: {existing.pid if existing else 'unknown'})")
        console.print("Use [cyan]kernicle stop[/cyan] to stop it first.")
        raise typer.Exit(1)
    
    # ==========================================================================
    # AUTO-DETECT AND ANALYZE CRASHES ON START
    # ==========================================================================
    from kernicle.services.crashdump import CrashDumpManager
    import json
    
    crash_manager = CrashDumpManager()
    crash_dumps = crash_manager.list_crash_dumps()
    unanalyzed_crashes = [d for d in crash_dumps if not d.get("analyzed", False)]
    
    if unanalyzed_crashes:
        console.print(Panel.fit(
            f"[bold red]🚨 {len(unanalyzed_crashes)} UNANALYZED CRASH DUMP(S) DETECTED![/bold red]\n"
            f"Your system crashed before. Analyzing now...",
            title="⚠️ Previous Crash Detected",
            border_style="red"
        ))
        
        for crash in unanalyzed_crashes:
            crash_path = Path(crash["vmcore"])
            console.print(f"\n[yellow]Analyzing crash: {crash_path.parent.name}[/yellow]")
            
            with console.status("[bold green]Extracting crash information..."):
                crash_info = crash_manager.analyze_crash_dump(crash_path)
            
            if crash_info:
                console.print(f"[green]✓[/green] Crash analyzed: {crash_info.panic_message or 'Kernel panic'}")
                
                # Create a session for this crash analysis
                crash_archive = create_session_archive(config.archives_dir)
                crash_archive.write_ai_verdict(crash_info=crash_info)
                
                # Write crash report
                crash_report_path = crash_archive.session_dir / "crash_report.txt"
                crash_report_path.write_text(f"""KERNEL CRASH REPORT
==================
Crash Time: {crash_info.timestamp}
Kernel: {crash_info.kernel_version}
Panic: {crash_info.panic_message or 'Unknown'}

Call Trace:
{chr(10).join(crash_info.call_trace[:30]) if crash_info.call_trace else 'Not available'}
""", encoding="utf-8")
                
                crash_archive.write_manifest(parse_range("last:1m"), kernel_only=False)
                console.print(f"[green]✓[/green] Crash session created: {crash_archive.session_dir.name}")
                
                # Mark as analyzed
                analysis_marker = crash_path.parent / "kernicle_analysis.json"
                analysis_marker.write_text(json.dumps({
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                    "panic_message": crash_info.panic_message,
                    "session": crash_archive.session_dir.name,
                }), encoding="utf-8")
            else:
                console.print(f"[yellow]⚠[/yellow] Could not fully analyze crash dump")
        
        console.print("")  # Blank line
    
    # ==========================================================================
    # CREATE SESSION CONFIG AND START
    # ==========================================================================
    
    # Create session config
    session_config = SessionConfig(
        capture_interval=collect_every,
        push_interval=archive_every,
        duration=duration,
        kernel_only=kernel_only,
        git_backup=git_backup,
        max_archives=max_archives,
        range_spec=range_spec,
        name=name,
    )
    
    # Show startup info
    duration_str = f"{duration}s" if duration else "until stopped"
    name_str = name if name else "session (default)"
    console.print(Panel.fit(
        f"[bold cyan]Kernicle v{__version__}[/bold cyan]\n"
        f"Mode: [magenta]Background Session[/magenta]\n"
        f"Name: [cyan]{name_str}[/cyan]\n"
        f"Range: [yellow]{range_spec}[/yellow]\n"
        f"Capture: every [green]{collect_every}s[/green]\n"
        f"Archive: every [green]{archive_every}s[/green]\n"
        f"Duration: [yellow]{duration_str}[/yellow]\n"
        f"Max archives: [yellow]{max_archives}[/yellow]\n"
        f"Git backup: [{'green' if git_backup else 'dim'}]{git_backup}[/]",
        title="🚀 Starting Background Session",
        border_style="cyan"
    ))
    
    # Start background session
    success, message = start_background_session(
        session_config,
        config.archives_dir,
        config.session_dir,
    )
    
    if success:
        console.print(f"\n[bold green]✓[/bold green] {message}")
        console.print("\nUse [cyan]kernicle status[/cyan] to check progress")
        console.print("Use [cyan]kernicle stop[/cyan] to stop the session")
    else:
        console.print(f"\n[bold red]✗[/bold red] {message}")
        raise typer.Exit(1)


@app.command()
def status():
    """
    Show status of the background capture session.
    
    Displays whether a session is running, its configuration,
    and capture/archive statistics.
    
    Examples:
        kernicle status
    """
    from kernicle.services.session import get_session_status
    
    status_info = get_session_status(config.session_dir)
    
    if not status_info.get("running") and status_info.get("message") == "No session state found":
        console.print("[yellow]No session has been started.[/yellow]")
        console.print("Use [cyan]kernicle start --all[/cyan] to start a background session.")
        return
    
    # Build status panel
    running = status_info.get("running", False)
    status_color = "green" if running else "red"
    status_text = "Running" if running else "Stopped"
    
    lines = [
        f"Status: [{status_color}]{status_text}[/{status_color}]",
        f"PID: [cyan]{status_info.get('pid', 'N/A')}[/cyan]",
        f"Started: [green]{status_info.get('started_utc', 'N/A')}[/green]",
    ]
    
    if status_info.get("stopped_utc"):
        lines.append(f"Stopped: [red]{status_info['stopped_utc']}[/red]")
    
    lines.extend([
        "",
        f"Captures: [yellow]{status_info.get('capture_count', 0)}[/yellow]",
        f"Archives: [yellow]{status_info.get('archive_count', 0)}[/yellow]",
        f"Last capture: [dim]{status_info.get('last_capture_utc', 'N/A')}[/dim]",
        f"Last archive: [dim]{status_info.get('last_archive_utc', 'N/A')}[/dim]",
        f"Current session: [cyan]{status_info.get('current_session_id', 'N/A')}[/cyan]",
    ])
    
    # Config info
    cfg = status_info.get("config", {})
    lines.extend([
        "",
        "[bold]Configuration:[/bold]",
        f"  Capture interval: {cfg.get('capture_interval', 'N/A')}s",
        f"  Archive interval: {cfg.get('push_interval', 'N/A')}s",
        f"  Duration: {cfg.get('duration', 'unlimited')}s" if cfg.get('duration') else "  Duration: unlimited",
        f"  Max archives: {cfg.get('max_archives', 'N/A')}",
        f"  Git backup: {cfg.get('git_backup', False)}",
    ])
    
    # Errors and warnings
    errors = status_info.get("errors", [])
    warnings = status_info.get("warnings", [])
    
    if errors:
        lines.append("")
        lines.append("[bold red]Errors:[/bold red]")
        for err in errors[-5:]:  # Show last 5 errors
            lines.append(f"  [red]✗[/red] {err}")
    
    if warnings:
        lines.append("")
        lines.append("[bold yellow]Warnings:[/bold yellow]")
        for warn in warnings[-5:]:  # Show last 5 warnings
            lines.append(f"  [yellow]⚠[/yellow] {warn}")
    
    console.print(Panel(
        "\n".join(lines),
        title="📊 Session Status",
        border_style="cyan"
    ))


@app.command()
def stop():
    """
    Stop the running background capture session.
    
    Requests a graceful shutdown, allowing the session to create
    a final archive before exiting.
    
    Examples:
        kernicle stop
    """
    from kernicle.services.session import stop_background_session, SessionManager
    
    manager = SessionManager(config.session_dir)
    is_running, state = manager.is_session_running()
    
    if not is_running:
        console.print("[yellow]No session is currently running.[/yellow]")
        if state and state.stopped_utc:
            console.print(f"Last session stopped at: {state.stopped_utc}")
        return
    
    console.print(f"Stopping session (PID: {state.pid if state else 'unknown'})...")
    console.print("[dim]Waiting for final archive to be created...[/dim]")
    
    success, message = stop_background_session(config.session_dir, timeout=30)
    
    if success:
        console.print(f"\n[bold green]✓[/bold green] {message}")
    else:
        console.print(f"\n[bold red]✗[/bold red] {message}")
        raise typer.Exit(1)


# Sprint 6: Export command

@app.command()
def export(
    session_id: str = typer.Argument(
        ...,
        help="Session ID or partial match (e.g., 'session-20260103-120000' or '20260103')"
    ),
    format: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Export format: json, md (markdown), or html"
    ),
    output: str = typer.Option(
        None,
        "--out",
        "-o",
        help="Output file path (default: <session-id>.<format> in current directory)"
    ),
):
    """
    Export a session report to JSON, Markdown, or HTML format.
    
    Creates professional, shareable reports from captured session data.
    
    Examples:
        kernicle export session-20260103-120000 --format html
        kernicle export 20260103 --format md --out ./report.md
        kernicle export session-20260103-120000 --format json --out ~/reports/incident.json
    """
    from kernicle.services.export import export_session, find_session
    
    # Validate format
    valid_formats = ["json", "md", "html"]
    if format not in valid_formats:
        console.print(f"[red]Error:[/red] Invalid format '{format}'. Use one of: {', '.join(valid_formats)}")
        raise typer.Exit(1)
    
    # Find session
    session_dir = find_session(config.archives_dir, session_id)
    
    if session_dir is None:
        console.print(f"[red]Error:[/red] Session not found: {session_id}")
        console.print("\n[dim]Available sessions:[/dim]")
        sessions = config.list_sessions(limit=5)
        for s in sessions:
            console.print(f"  • {s.name}")
        if len(sessions) >= 5:
            console.print(f"  [dim]... use 'kernicle show' to see more[/dim]")
        raise typer.Exit(1)
    
    # Determine output path
    if output:
        output_path = Path(output).expanduser()
    else:
        output_path = Path.cwd() / f"{session_dir.name}.{format}"
    
    console.print(Panel.fit(
        f"[bold cyan]Session:[/bold cyan] {session_dir.name}\n"
        f"[bold cyan]Format:[/bold cyan] {format.upper()}\n"
        f"[bold cyan]Output:[/bold cyan] {output_path}",
        title="📤 Exporting Report",
        border_style="cyan"
    ))
    
    # Export
    with console.status(f"[bold green]Generating {format.upper()} report..."):
        result = export_session(session_dir, output_path, format)
    
    if result.success:
        # Get file size
        file_size = output_path.stat().st_size
        if file_size > 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        elif file_size > 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} bytes"
        
        console.print(f"\n[bold green]✓[/bold green] Export complete ({size_str})")
        console.print(f"Output: [cyan]{output_path}[/cyan]")
        
        # Show helpful hint
        if format == "html":
            console.print(f"\n[dim]Open in browser: xdg-open {output_path}[/dim]")
        elif format == "md":
            console.print(f"\n[dim]View: cat {output_path}[/dim]")
        elif format == "json":
            console.print(f"\n[dim]View: jq . {output_path}[/dim]")
    else:
        console.print(f"\n[bold red]✗[/bold red] Export failed: {result.error}")
        raise typer.Exit(1)


# =============================================================================
# CRASH CAPTURE COMMANDS
# =============================================================================

@app.command("crash-status")
def crash_status():
    """
    Check the status of kernel crash capture setup.
    
    Shows whether kdump/kexec is properly configured to capture
    kernel panics and hard crashes.
    
    Examples:
        kernicle crash-status
    """
    from kernicle.services.crashdump import CrashDumpManager, CrashCaptureStatus
    
    manager = CrashDumpManager()
    status = manager.get_detailed_status()
    
    # Status color mapping
    status_colors = {
        CrashCaptureStatus.NOT_INSTALLED.value: "red",
        CrashCaptureStatus.INSTALLED_NOT_CONFIGURED.value: "yellow",
        CrashCaptureStatus.CONFIGURED_NOT_ENABLED.value: "yellow",
        CrashCaptureStatus.ENABLED_NOT_LOADED.value: "yellow",
        CrashCaptureStatus.FULLY_OPERATIONAL.value: "green",
    }
    
    status_icons = {
        CrashCaptureStatus.NOT_INSTALLED.value: "❌",
        CrashCaptureStatus.INSTALLED_NOT_CONFIGURED.value: "⚠️",
        CrashCaptureStatus.CONFIGURED_NOT_ENABLED.value: "⚠️",
        CrashCaptureStatus.ENABLED_NOT_LOADED.value: "⚠️",
        CrashCaptureStatus.FULLY_OPERATIONAL.value: "✅",
    }
    
    color = status_colors.get(status["status"], "white")
    icon = status_icons.get(status["status"], "❓")
    
    # Build status panel
    lines = [
        f"Status: [{color}]{icon} {status['status'].upper()}[/{color}]",
        f"[dim]{status['status_description']}[/dim]",
        "",
        "[bold]Packages:[/bold]",
    ]
    
    for pkg, installed in status["packages"].items():
        pkg_icon = "✓" if installed else "✗"
        pkg_color = "green" if installed else "red"
        lines.append(f"  [{pkg_color}]{pkg_icon}[/{pkg_color}] {pkg}")
    
    lines.extend([
        "",
        "[bold]Configuration:[/bold]",
        f"  Crashkernel in GRUB file: {'✓' if status.get('crashkernel_in_grub', status['crashkernel_configured']) else '✗'}",
        f"  Crashkernel active: {'✓ ' + status['crashkernel_param'] if status['crashkernel_param'] else '✗ Not set'}",
        f"  kdump enabled: {'✓' if status['kdump_enabled'] else '✗'}",
        f"  kdump running: {'✓' if status['kdump_running'] else '✗'}",
        f"  Crash kernel loaded: {'✓' if status['crash_kernel_loaded'] else '✗'}",
        "",
        f"Crash dump directory: [cyan]{status['crash_dir']}[/cyan]",
    ])
    
    # Show success message if fully operational
    if status["status"] == CrashCaptureStatus.FULLY_OPERATIONAL.value:
        lines.extend([
            "",
            "[bold green]🎉 CRASH CAPTURE IS FULLY OPERATIONAL![/bold green]",
            "[dim]Your system will capture kernel panics and save them to /var/crash/[/dim]",
        ])
    
    # Show pending crashes
    if status["pending_crashes"]:
        lines.extend([
            "",
            f"[bold yellow]⚠ {len(status['pending_crashes'])} crash dump(s) found![/bold yellow]",
        ])
        for crash in status["pending_crashes"][:3]:
            analyzed = "analyzed" if crash["analyzed"] else "NOT analyzed"
            lines.append(f"  • {crash['timestamp']} ({crash['size_mb']:.1f} MB) - {analyzed}")
        if len(status["pending_crashes"]) > 3:
            lines.append(f"  [dim]... and {len(status['pending_crashes']) - 3} more[/dim]")
        lines.append("")
        lines.append("[cyan]Run 'kernicle analyze-crash' to analyze crash dumps[/cyan]")
    
    # Show recommendations
    if status["recommendations"]:
        lines.extend([
            "",
            "[bold]Recommendations:[/bold]",
        ])
        for rec in status["recommendations"]:
            lines.append(f"  → {rec}")
    
    console.print(Panel(
        "\n".join(lines),
        title="🔧 Crash Capture Status",
        border_style="cyan"
    ))


@app.command("setup-crash")
def setup_crash(
    memory: str = typer.Option(
        "512M-:192M",
        "--memory", "-m",
        help="Crashkernel memory allocation (e.g., '512M-:192M')"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force reconfiguration even if already set up"
    ),
):
    """
    Set up kernel crash capture (kdump/kexec).
    
    This command configures your system to capture kernel panics
    and hard crashes. REQUIRES SUDO/ROOT privileges.
    
    After setup, a reboot is required to activate crash capture.
    
    Examples:
        sudo kernicle setup-crash
        sudo kernicle setup-crash --memory "1G-:256M"
    """
    import os
    from kernicle.services.crashdump import CrashDumpManager, CrashCaptureStatus
    
    # Check for root
    if os.geteuid() != 0:
        console.print(Panel(
            "[bold red]Root privileges required![/bold red]\n\n"
            "Run this command with sudo:\n"
            "[cyan]sudo kernicle setup-crash[/cyan]",
            title="⚠️ Permission Denied",
            border_style="red"
        ))
        raise typer.Exit(1)
    
    manager = CrashDumpManager()
    
    # Check current status
    current_status = manager.get_status()
    
    if current_status == CrashCaptureStatus.FULLY_OPERATIONAL and not force:
        console.print(Panel(
            "[bold green]✅ Crash capture is already fully operational![/bold green]\n\n"
            "Your system is configured to capture kernel panics.\n"
            "Use [cyan]--force[/cyan] to reconfigure anyway.",
            title="Already Configured",
            border_style="green"
        ))
        return
    
    console.print(Panel.fit(
        "[bold cyan]Kernicle Crash Capture Setup[/bold cyan]\n\n"
        "This will:\n"
        "1. Install kdump-tools and kexec-tools\n"
        "2. Configure crashkernel in GRUB\n"
        "3. Enable kdump service\n"
        f"\nMemory allocation: [yellow]{memory}[/yellow]",
        title="🔧 Setup",
        border_style="cyan"
    ))
    
    with console.status("[bold green]Setting up crash capture..."):
        result = manager.setup_crash_capture(crashkernel_mem=memory)
    
    if result.success:
        if result.requires_reboot:
            console.print(Panel(
                "[bold green]✅ Setup completed successfully![/bold green]\n\n"
                "[bold yellow]⚠️ REBOOT REQUIRED[/bold yellow]\n\n"
                "The crash capture system is configured but requires a reboot\n"
                "to load the crash kernel into memory.\n\n"
                "After reboot, run [cyan]kernicle crash-status[/cyan] to verify.",
                title="Setup Complete",
                border_style="green"
            ))
        else:
            console.print(Panel(
                "[bold green]✅ Crash capture is now fully operational![/bold green]\n\n"
                "Your system will now capture kernel panics and hard crashes.\n"
                "Crash dumps will be saved to [cyan]/var/crash/[/cyan]\n\n"
                "Run [cyan]kernicle crash-status[/cyan] to see detailed status.",
                title="Setup Complete",
                border_style="green"
            ))
    else:
        console.print(Panel(
            f"[bold red]❌ Setup failed![/bold red]\n\n"
            f"Message: {result.message}\n\n"
            "Errors:\n" + "\n".join(f"  • {e}" for e in result.errors),
            title="Setup Failed",
            border_style="red"
        ))
        raise typer.Exit(1)
    
    # Show any warnings
    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warn in result.warnings:
            console.print(f"  ⚠ {warn}")


@app.command("crash-analyze")
def crash_analyze(
    dump_path: str = typer.Argument(
        None,
        help="Path to crash dump (default: analyze latest)"
    ),
    output_dir: str = typer.Option(
        None,
        "--output", "-o",
        help="Output directory for analysis (default: new session)"
    ),
):
    """
    Analyze a kernel crash dump.
    
    Extracts panic message, call trace, and kernel logs from
    a crash dump (vmcore) and generates a comprehensive report.
    Automatically sends to AI for diagnosis.
    
    Examples:
        kernicle crash-analyze
        kernicle crash-analyze /var/crash/202601031200/
        kernicle crash-analyze --output ./crash-report/
    """
    from kernicle.services.crashdump import CrashDumpManager
    from kernicle.services.archive import create_session_archive
    from kernicle.services import ai_integration
    
    manager = CrashDumpManager()
    
    # Find crash dump to analyze
    if dump_path:
        crash_path = Path(dump_path)
        if not crash_path.exists():
            console.print(f"[red]Error:[/red] Crash dump not found: {dump_path}")
            raise typer.Exit(1)
    else:
        # Find latest unanalyzed crash
        dumps = manager.list_crash_dumps()
        if not dumps:
            console.print(Panel(
                "[yellow]No crash dumps found.[/yellow]\n\n"
                "Crash dumps are created when the kernel panics.\n"
                "Check that crash capture is set up: [cyan]kernicle crash-status[/cyan]",
                title="No Crashes",
                border_style="yellow"
            ))
            return
        
        # Prefer unanalyzed dumps
        unanalyzed = [d for d in dumps if not d["analyzed"]]
        if unanalyzed:
            crash_path = Path(unanalyzed[0]["vmcore"])
            console.print(f"Analyzing latest unanalyzed crash: [cyan]{crash_path.parent}[/cyan]")
        else:
            crash_path = Path(dumps[0]["vmcore"])
            console.print(f"Analyzing latest crash: [cyan]{crash_path.parent}[/cyan]")
    
    console.print(Panel.fit(
        f"[bold cyan]Analyzing Crash Dump[/bold cyan]\n\n"
        f"Path: [yellow]{crash_path}[/yellow]\n"
        f"Size: {crash_path.stat().st_size / (1024*1024):.1f} MB",
        title="🔍 Crash Analysis",
        border_style="cyan"
    ))
    
    # Analyze the crash
    with console.status("[bold green]Extracting crash information..."):
        crash_info = manager.analyze_crash_dump(crash_path)
    
    if not crash_info:
        console.print("[red]Error:[/red] Failed to analyze crash dump")
        console.print("[dim]Make sure 'crash' utility is installed: sudo apt install crash[/dim]")
        raise typer.Exit(1)
    
    console.print("[green]✓[/green] Crash information extracted")
    
    # Create session for this crash
    if output_dir:
        session_dir = Path(output_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
    else:
        archive = create_session_archive(config.archives_dir)
        session_dir = archive.session_dir
    
    # Generate report
    with console.status("[bold green]Generating crash report..."):
        report_path = manager.generate_crash_report(crash_info, session_dir)
    
    console.print(f"[green]✓[/green] Crash report generated: [cyan]{report_path}[/cyan]")
    
    # Show crash summary
    console.print(Panel(
        f"[bold]Crash Time:[/bold] {crash_info.timestamp}\n"
        f"[bold]Kernel:[/bold] {crash_info.kernel_version}\n"
        f"[bold]Panic Message:[/bold]\n{crash_info.panic_message or 'Unable to extract'}\n\n"
        f"[bold]Call Trace:[/bold] {len(crash_info.call_trace)} frames captured\n"
        f"[bold]Kernel Log:[/bold] {len(crash_info.dmesg_tail)} lines captured",
        title="📋 Crash Summary",
        border_style="yellow"
    ))
    
    # Generate AI verdict
    if ai_integration.is_ai_available():
        with console.status("[bold green]Generating AI verdict..."):
            # Prepare crash data for AI
            crash_content = f"""
KERNEL PANIC ANALYSIS

Panic Message:
{crash_info.panic_message or 'Unknown'}

Call Trace:
{chr(10).join(crash_info.call_trace[:20])}

Kernel Log (last lines before crash):
{chr(10).join(crash_info.dmesg_tail[-50:])}
"""
            context = f"Kernel: {crash_info.kernel_version}, Crash time: {crash_info.timestamp}"
            
            try:
                result = ai_integration.analyze_logs(crash_content, context, timeout=90.0)
                if result:
                    verdict_content = ai_integration.format_analysis(result, crash_content)
                    verdict_path = session_dir / "ai_verdict.md"
                    verdict_path.write_text(verdict_content, encoding="utf-8")
                    console.print(f"[green]✓[/green] AI verdict generated: [cyan]{verdict_path}[/cyan]")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] AI analysis failed: {e}")
    else:
        console.print("[yellow]⚠[/yellow] AI not available - install kernicle-ai for AI diagnosis")
    
    # Mark as analyzed
    analysis_marker = crash_path.parent / "kernicle_analysis.json"
    import json
    analysis_marker.write_text(json.dumps({
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "session_dir": str(session_dir),
    }), encoding="utf-8")
    
    console.print(f"\n[bold green]✓[/bold green] Crash analysis complete!")
    console.print(f"Results saved to: [cyan]{session_dir}[/cyan]")


@app.command("crash-check")
def crash_check():
    """
    Quick check for any new crash dumps.
    
    Use this after a system reboot to check if any crashes
    were captured during the previous session.
    
    Examples:
        kernicle crash-check
    """
    from kernicle.services.crashdump import CrashDumpManager
    
    manager = CrashDumpManager()
    dumps = manager.list_crash_dumps()
    
    if not dumps:
        console.print("[green]✓[/green] No crash dumps found. System is healthy!")
        return
    
    unanalyzed = [d for d in dumps if not d["analyzed"]]
    
    if unanalyzed:
        console.print(Panel(
            f"[bold red]⚠️ {len(unanalyzed)} UNANALYZED CRASH(ES) FOUND![/bold red]\n\n"
            "Your system experienced kernel panic(s).\n"
            "Run [cyan]kernicle analyze-crash[/cyan] to investigate.",
            title="🚨 Crashes Detected",
            border_style="red"
        ))
        
        for crash in unanalyzed:
            console.print(f"  • {crash['timestamp']} - {crash['size_mb']:.1f} MB")
    else:
        console.print(Panel(
            f"[yellow]{len(dumps)} crash dump(s) found (all analyzed)[/yellow]\n\n"
            "All previous crashes have been analyzed.\n"
            "Run [cyan]kernicle analyze-crash <path>[/cyan] to re-analyze.",
            title="Crash History",
            border_style="yellow"
        ))


@app.command()
def clean(
    keep_count: int = typer.Option(
        10, "--keep", "-n",
        help="Keep only the N most recent archives"
    ),
    local_only: bool = typer.Option(
        False, "--local", "-l",
        help="Clean only local sessions"
    ),
    github_only: bool = typer.Option(
        False, "--github", "-g",
        help="Clean only GitHub repo"
    ),
    delete_name: Optional[str] = typer.Option(
        None, "--delete", "-D",
        help="Delete archives matching pattern(s) - comma-separated for multiple"
    ),
    keep_name: Optional[str] = typer.Option(
        None, "--keep-name", "-K",
        help="Keep/protect archives matching pattern(s) - comma-separated for multiple"
    ),
    max_size: Optional[int] = typer.Option(
        None, "--max-size",
        help="Delete oldest until total size is under MB"
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Delete without confirmation"
    ),
):
    """
    🧹 Clean up old sessions/archives.
    
    By default cleans BOTH local and GitHub.
    Use -l for local only, -g for GitHub only.
    
    Name-based filtering (supports comma-separated patterns):
      --delete/-D  Delete only archives matching pattern(s)
      --keep-name/-K  Protect archives matching pattern(s) from deletion
    
    Examples:
      kernicle clean              # Clean both (default)
      kernicle clean -l           # Clean local only
      kernicle clean -g           # Clean GitHub only
      kernicle clean -n 5         # Keep 5 most recent
      kernicle clean -D "nginx"   # Delete all with 'nginx' in name
      kernicle clean -D "nginx,memory"  # Delete 'nginx' OR 'memory'
      kernicle clean -K "prod,critical" # Protect 'prod' and 'critical'
      kernicle clean -n 3 -K "prod"     # Keep 3 + all 'prod'
    """
    import shutil
    import subprocess
    import tempfile
    from datetime import datetime
    
    archives_dir = Path.home() / ".kernicle" / "archives"
    git_remote = os.environ.get("KERNICLE_GIT_REMOTE", "")
    
    # Determine what to clean
    clean_local = not github_only  # Clean local unless --github specified
    clean_github = not local_only  # Clean github unless --local specified
    
    # If both flags specified, that's an error
    if local_only and github_only:
        console.print("[red]Cannot specify both --local and --github. Use neither for both.[/red]")
        raise typer.Exit(1)
    
    local_items = []
    local_to_delete = []
    git_items = []
    git_to_delete = []
    temp_dir = None
    
    # Calculate size helper
    def get_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    
    # Name matching helper - supports comma-separated patterns
    def matches_pattern(name: str, patterns: str) -> bool:
        """Check if name contains any of the patterns (case-insensitive, comma-separated)."""
        pattern_list = [p.strip() for p in patterns.split(",") if p.strip()]
        return any(p.lower() in name.lower() for p in pattern_list)
    
    import re
    # Extract timestamp for sorting
    def get_timestamp(name: str) -> str:
        match = re.search(r'(\d{8}-\d{6})', name)
        return match.group(1) if match else name
    
    # ===== LOCAL CLEANUP =====
    if clean_local:
        console.print(f"\n[bold cyan]📁 Local Sessions[/bold cyan]")
        
        if archives_dir.exists():
            # Match any directory/file with timestamp pattern
            timestamp_pattern = re.compile(r'-\d{8}-\d{6}')
            for item in archives_dir.iterdir():
                if timestamp_pattern.search(item.name):
                    local_items.append(item)
        
        # Sort by timestamp (newest first)
        local_items = sorted(local_items, key=lambda p: get_timestamp(p.name), reverse=True)
        total_size = sum(get_size(item) for item in local_items)
        
        console.print(f"   Count: {len(local_items)} | Size: {total_size / 1024:.1f} KB")
        
        # Determine what to delete locally
        if delete_name:
            # Delete only items matching the pattern
            local_to_delete = [item for item in local_items if matches_pattern(item.name, delete_name)]
            # But protect items matching keep_name
            if keep_name:
                local_to_delete = [item for item in local_to_delete if not matches_pattern(item.name, keep_name)]
        else:
            # Standard: keep N most recent
            if len(local_items) > keep_count:
                local_to_delete = local_items[keep_count:]
            
            # Protect items matching keep_name
            if keep_name:
                local_to_delete = [item for item in local_to_delete if not matches_pattern(item.name, keep_name)]
        
        # By size: delete more if still over max_size
        if max_size is not None:
            max_bytes = max_size * 1024 * 1024
            remaining = [s for s in local_items if s not in local_to_delete]
            current_size = sum(get_size(s) for s in remaining)
            for s in reversed(remaining):
                if current_size <= max_bytes:
                    break
                # Don't delete if protected by keep_name
                if keep_name and matches_pattern(s.name, keep_name):
                    continue
                local_to_delete.append(s)
                current_size -= get_size(s)
    
    # ===== GITHUB CLEANUP =====
    if clean_github:
        if git_remote:
            console.print(f"\n[bold cyan]☁️  GitHub Archives[/bold cyan]")
            try:
                temp_dir = tempfile.mkdtemp(prefix="kernicle-clean-")
                result = subprocess.run(
                    ["git", "clone", "--quiet", git_remote, temp_dir],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    git_archives_dir = Path(temp_dir) / "archives"
                    if git_archives_dir.exists():
                        git_items = sorted(
                            [f for f in git_archives_dir.iterdir() if f.suffix == ".zip"],
                            key=lambda p: get_timestamp(p.name),
                            reverse=True
                        )
                        git_size = sum(f.stat().st_size for f in git_items)
                        console.print(f"   Count: {len(git_items)} | Size: {git_size / 1024:.1f} KB")
                        
                        # Determine what to delete
                        if delete_name:
                            # Delete only items matching the pattern
                            git_to_delete = [item for item in git_items if matches_pattern(item.name, delete_name)]
                            # But protect items matching keep_name
                            if keep_name:
                                git_to_delete = [item for item in git_to_delete if not matches_pattern(item.name, keep_name)]
                        else:
                            # Standard: keep N most recent
                            if len(git_items) > keep_count:
                                git_to_delete = git_items[keep_count:]
                            
                            # Protect items matching keep_name
                            if keep_name:
                                git_to_delete = [item for item in git_to_delete if not matches_pattern(item.name, keep_name)]
                    else:
                        console.print("   [yellow]No archives folder in repo[/yellow]")
                else:
                    console.print(f"   [red]Failed to clone: {result.stderr.strip()}[/red]")
            except Exception as e:
                console.print(f"   [red]Error: {e}[/red]")
        else:
            console.print(f"\n[dim]GitHub not configured (set KERNICLE_GIT_REMOTE)[/dim]")
    
    # ===== SUMMARY =====
    if not local_to_delete and not git_to_delete:
        console.print("\n[green]✓ Nothing to clean.[/green]")
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise typer.Exit(0)
    
    # Show what will be deleted
    console.print(f"\n[yellow bold]🗑️  Will Delete:[/yellow bold]")
    
    if local_to_delete:
        local_size_to_free = sum(get_size(s) for s in local_to_delete)
        console.print(f"\n   [yellow]Local: {len(local_to_delete)} session(s) (~{local_size_to_free / 1024:.1f} KB)[/yellow]")
        for item in local_to_delete[:5]:
            mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            console.print(f"     • {item.name} ({mtime})")
        if len(local_to_delete) > 5:
            console.print(f"     ... +{len(local_to_delete) - 5} more")
    
    if git_to_delete:
        git_size_to_free = sum(f.stat().st_size for f in git_to_delete)
        console.print(f"\n   [yellow]GitHub: {len(git_to_delete)} archive(s) (~{git_size_to_free / 1024:.1f} KB)[/yellow]")
        for item in git_to_delete[:5]:
            console.print(f"     • {item.name}")
        if len(git_to_delete) > 5:
            console.print(f"     ... +{len(git_to_delete) - 5} more")
    
    # Confirmation
    if not force:
        if not typer.confirm("\nProceed with cleanup?"):
            console.print("[yellow]Cancelled.[/yellow]")
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise typer.Exit(0)
    
    # ===== DELETE LOCAL =====
    local_deleted = 0
    if local_to_delete:
        for item in local_to_delete:
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                local_deleted += 1
            except Exception as e:
                console.print(f"[red]Failed: {item.name}: {e}[/red]")
        
        if local_deleted:
            console.print(f"[green]✓ Local: Deleted {local_deleted} session(s)[/green]")
    
    # ===== DELETE GITHUB =====
    git_deleted = 0
    if git_to_delete and temp_dir:
        try:
            for item in git_to_delete:
                item.unlink()
                git_deleted += 1
            
            # Commit and push
            subprocess.run(["git", "add", "-A"], cwd=temp_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"🧹 Clean: keep {keep_count} most recent archives"],
                cwd=temp_dir, capture_output=True
            )
            result = subprocess.run(
                ["git", "push"], cwd=temp_dir, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                console.print(f"[green]✓ GitHub: Deleted {git_deleted} archive(s)[/green]")
            else:
                console.print(f"[red]GitHub push failed: {result.stderr.strip()}[/red]")
        except Exception as e:
            console.print(f"[red]GitHub cleanup error: {e}[/red]")
    
    # Cleanup temp
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    console.print(f"\n[green bold]✓ Cleanup complete![/green bold]")


if __name__ == "__main__":
    app()
