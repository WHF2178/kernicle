"""
System information utilities for Kernicle.
Sprint 6: Enhanced system info including kernel version, uptime, boot time.

Provides system details for reports and exports.
"""

import os
import platform
import socket
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class SystemInfo:
    """System information snapshot."""
    hostname: str
    os: str
    kernel_version: str
    architecture: str
    platform: str
    uptime_seconds: Optional[float] = None
    uptime_formatted: Optional[str] = None
    boot_time: Optional[str] = None
    cpu_model: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def get_kernel_version() -> str:
    """
    Get the Linux kernel version.
    
    Returns:
        Kernel version string (e.g., "6.5.0-44-generic")
    """
    try:
        return platform.release()
    except Exception:
        return "unknown"


def get_uptime() -> tuple[Optional[float], Optional[str]]:
    """
    Get system uptime from /proc/uptime.
    
    Returns:
        Tuple of (uptime_seconds, formatted_uptime_string)
    """
    try:
        uptime_path = Path("/proc/uptime")
        if uptime_path.exists():
            content = uptime_path.read_text().strip()
            uptime_seconds = float(content.split()[0])
            
            # Format uptime
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0 or not parts:
                parts.append(f"{minutes}m")
            
            formatted = " ".join(parts)
            return uptime_seconds, formatted
    except Exception:
        pass
    
    return None, None


def get_boot_time() -> Optional[str]:
    """
    Get system boot time.
    
    Returns:
        ISO formatted boot time string or None
    """
    try:
        uptime_seconds, _ = get_uptime()
        if uptime_seconds is not None:
            boot_timestamp = datetime.now(timezone.utc).timestamp() - uptime_seconds
            boot_dt = datetime.fromtimestamp(boot_timestamp, tz=timezone.utc)
            return boot_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass
    
    # Fallback: try using who -b
    try:
        result = subprocess.run(
            ["who", "-b"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Output like: "         system boot  2025-01-01 10:00"
            output = result.stdout.strip()
            if "boot" in output:
                parts = output.split("boot")[-1].strip()
                return parts
    except Exception:
        pass
    
    return None


def get_cpu_model() -> Optional[str]:
    """
    Get CPU model name from /proc/cpuinfo.
    
    Returns:
        CPU model string or None
    """
    try:
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            content = cpuinfo_path.read_text()
            for line in content.splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    
    return None


def get_os_info() -> str:
    """
    Get OS distribution info.
    
    Returns:
        OS description string (e.g., "Ubuntu 22.04.3 LTS")
    """
    # Try /etc/os-release first (most reliable on modern Linux)
    try:
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            content = os_release_path.read_text()
            for line in content.splitlines():
                if line.startswith("PRETTY_NAME="):
                    # Remove PRETTY_NAME= and quotes
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    
    # Fallback to platform
    try:
        return f"{platform.system()} {platform.version()}"
    except Exception:
        return "Unknown"


def get_system_info() -> SystemInfo:
    """
    Collect comprehensive system information.
    
    Returns:
        SystemInfo dataclass with all system details
    """
    uptime_seconds, uptime_formatted = get_uptime()
    
    return SystemInfo(
        hostname=socket.gethostname(),
        os=get_os_info(),
        kernel_version=get_kernel_version(),
        architecture=platform.machine(),
        platform=platform.platform(),
        uptime_seconds=uptime_seconds,
        uptime_formatted=uptime_formatted,
        boot_time=get_boot_time(),
        cpu_model=get_cpu_model(),
    )


def get_host_info_for_manifest() -> dict:
    """
    Get host info dictionary for manifest.json.
    
    This is the enhanced version with Sprint 6 additions.
    
    Returns:
        Dictionary with host information
    """
    info = get_system_info()
    return {
        "hostname": info.hostname,
        "os": info.os,
        "kernel_version": info.kernel_version,
        "architecture": info.architecture,
        "platform": info.platform,
        "uptime_seconds": info.uptime_seconds,
        "uptime_formatted": info.uptime_formatted,
        "boot_time": info.boot_time,
        "cpu_model": info.cpu_model,
    }
