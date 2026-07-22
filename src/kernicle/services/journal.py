"""
Journalctl wrapper services for capturing system and kernel logs.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CaptureResult:
    """Result of a journal log capture operation."""
    
    success: bool
    """Whether the capture was successful."""
    
    output: str
    """The captured log content."""
    
    error: Optional[str] = None
    """Error message if capture failed."""
    
    command: Optional[str] = None
    """The command that was executed."""


def capture_kernel(since_arg: str) -> CaptureResult:
    """
    Capture kernel logs using journalctl.
    
    Args:
        since_arg: Time argument for --since (e.g., "2025-12-30 12:00:00")
        
    Returns:
        CaptureResult with log content or error information
    """
    cmd = [
        "journalctl",
        "-k",  # kernel messages only
        "--since", since_arg,
        "--no-pager",
        "--output=short-iso"
    ]
    
    return _run_journalctl(cmd)


def capture_system(since_arg: str) -> CaptureResult:
    """
    Capture system logs using journalctl.
    
    Args:
        since_arg: Time argument for --since (e.g., "2025-12-30 12:00:00")
        
    Returns:
        CaptureResult with log content or error information
    """
    cmd = [
        "journalctl",
        "--since", since_arg,
        "--no-pager",
        "--output=short-iso"
    ]
    
    return _run_journalctl(cmd)


def _run_journalctl(cmd: list[str]) -> CaptureResult:
    """
    Execute a journalctl command and return the result.
    
    Args:
        cmd: Command and arguments as a list
        
    Returns:
        CaptureResult with outcome
    """
    cmd_str = " ".join(cmd)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
            check=False  # Don't raise on non-zero exit
        )
        
        if result.returncode == 0:
            return CaptureResult(
                success=True,
                output=result.stdout,
                command=cmd_str
            )
        else:
            # Common error: permission denied
            error_msg = result.stderr.strip()
            
            if "permission" in error_msg.lower() or result.returncode == 1:
                error_msg = (
                    f"Permission denied accessing journal logs.\n"
                    f"Suggestion: Run with sudo or add your user to systemd-journal group:\n"
                    f"  sudo usermod -a -G systemd-journal $USER\n"
                    f"Then log out and back in.\n\n"
                    f"Original error: {error_msg}"
                )
            
            return CaptureResult(
                success=False,
                output="",
                error=error_msg,
                command=cmd_str
            )
    
    except subprocess.TimeoutExpired:
        return CaptureResult(
            success=False,
            output="",
            error="Command timed out after 30 seconds",
            command=cmd_str
        )
    
    except FileNotFoundError:
        return CaptureResult(
            success=False,
            output="",
            error="journalctl command not found. Is systemd installed?",
            command=cmd_str
        )
    
    except Exception as e:
        return CaptureResult(
            success=False,
            output="",
            error=f"Unexpected error: {str(e)}",
            command=cmd_str
        )
