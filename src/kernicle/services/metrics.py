"""
System metrics collection using psutil.
Sprint 3: Captures CPU, memory, disk, and process metrics.
"""

import os
import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# psutil is optional - graceful degradation if missing
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False


@dataclass
class ProcessInfo:
    """Information about a single process."""
    pid: int
    name: str
    username: Optional[str]
    cpu_percent: float
    memory_rss_bytes: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pid": self.pid,
            "name": self.name,
            "username": self.username,
            "cpu_percent": self.cpu_percent,
            "memory_rss_bytes": self.memory_rss_bytes,
        }


@dataclass
class MetricsSnapshot:
    """
    System metrics snapshot at a point in time.
    All fields are optional to allow graceful degradation.
    """
    timestamp_utc: str
    hostname: str
    platform: dict = field(default_factory=dict)
    cpu: dict = field(default_factory=dict)
    memory: dict = field(default_factory=dict)
    disk: dict = field(default_factory=dict)
    top_processes: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    psutil_available: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp_utc": self.timestamp_utc,
            "hostname": self.hostname,
            "platform": self.platform,
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
            "top_processes": self.top_processes,
            "warnings": self.warnings,
            "psutil_available": self.psutil_available,
        }


def get_hostname() -> str:
    """Get system hostname."""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_platform_info() -> dict:
    """Get platform/OS information."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }
    
    # Try to get more detailed kernel info on Linux
    try:
        uname = os.uname()
        info["kernel_release"] = uname.release
        info["kernel_version"] = uname.version
    except Exception:
        pass
    
    return info


def get_cpu_metrics() -> tuple[dict, list[str]]:
    """
    Get CPU metrics using psutil.
    
    Returns:
        Tuple of (metrics dict, warnings list)
    """
    metrics = {}
    warnings = []
    
    if not PSUTIL_AVAILABLE or psutil is None:
        warnings.append("psutil not available - CPU metrics skipped")
        return metrics, warnings
    
    try:
        # Core counts
        metrics["logical_cores"] = psutil.cpu_count(logical=True)
        metrics["physical_cores"] = psutil.cpu_count(logical=False)
        
        # CPU percentage (short sample)
        metrics["cpu_percent_total"] = psutil.cpu_percent(interval=0.1)
        
        # Load average (Linux/Unix only)
        try:
            load_avg = os.getloadavg()
            metrics["load_avg"] = {
                "1min": load_avg[0],
                "5min": load_avg[1],
                "15min": load_avg[2],
            }
        except (OSError, AttributeError):
            # getloadavg not available on some systems
            pass
            
    except Exception as e:
        warnings.append(f"CPU metrics error: {str(e)}")
    
    return metrics, warnings


def get_memory_metrics() -> tuple[dict, list[str]]:
    """
    Get memory metrics using psutil.
    
    Returns:
        Tuple of (metrics dict, warnings list)
    """
    metrics = {}
    warnings = []
    
    if not PSUTIL_AVAILABLE or psutil is None:
        warnings.append("psutil not available - memory metrics skipped")
        return metrics, warnings
    
    try:
        mem = psutil.virtual_memory()
        metrics = {
            "total_bytes": mem.total,
            "available_bytes": mem.available,
            "used_bytes": mem.used,
            "percent": mem.percent,
        }
    except Exception as e:
        warnings.append(f"Memory metrics error: {str(e)}")
    
    return metrics, warnings


def get_disk_metrics(path: str = "/") -> tuple[dict, list[str]]:
    """
    Get disk metrics for a filesystem path.
    
    Args:
        path: Filesystem path to check (default: root "/")
        
    Returns:
        Tuple of (metrics dict, warnings list)
    """
    metrics = {}
    warnings = []
    
    if not PSUTIL_AVAILABLE or psutil is None:
        warnings.append("psutil not available - disk metrics skipped")
        return metrics, warnings
    
    try:
        disk = psutil.disk_usage(path)
        metrics = {
            "path": path,
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        }
    except Exception as e:
        warnings.append(f"Disk metrics error for {path}: {str(e)}")
    
    return metrics, warnings


def get_top_processes(limit: int = 5, sort_by: str = "memory") -> tuple[list[dict], list[str]]:
    """
    Get top processes by memory or CPU usage.
    
    Args:
        limit: Number of processes to return
        sort_by: "memory" or "cpu"
        
    Returns:
        Tuple of (process list, warnings list)
    """
    processes = []
    warnings = []
    
    if not PSUTIL_AVAILABLE or psutil is None:
        warnings.append("psutil not available - process list skipped")
        return processes, warnings
    
    try:
        # Get all process info
        proc_list = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                proc_list.append({
                    "pid": info['pid'],
                    "name": info['name'] or "unknown",
                    "username": info.get('username'),
                    "cpu_percent": info.get('cpu_percent', 0.0) or 0.0,
                    "memory_rss_bytes": info['memory_info'].rss if info.get('memory_info') else 0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process may have ended or we don't have permission
                continue
        
        # Sort by memory or CPU
        if sort_by == "memory":
            proc_list.sort(key=lambda x: x["memory_rss_bytes"], reverse=True)
        else:
            proc_list.sort(key=lambda x: x["cpu_percent"], reverse=True)
        
        processes = proc_list[:limit]
        
    except Exception as e:
        warnings.append(f"Process list error: {str(e)}")
    
    return processes, warnings


def capture_metrics() -> MetricsSnapshot:
    """
    Capture a complete system metrics snapshot.
    
    Returns:
        MetricsSnapshot with all available metrics
    """
    all_warnings = []
    
    # Timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Hostname
    hostname = get_hostname()
    
    # Platform info (no psutil needed)
    platform_info = get_platform_info()
    
    # CPU metrics
    cpu, cpu_warnings = get_cpu_metrics()
    all_warnings.extend(cpu_warnings)
    
    # Memory metrics
    memory, mem_warnings = get_memory_metrics()
    all_warnings.extend(mem_warnings)
    
    # Disk metrics
    disk, disk_warnings = get_disk_metrics("/")
    all_warnings.extend(disk_warnings)
    
    # Top processes (optional - best effort)
    top_processes, proc_warnings = get_top_processes(limit=5, sort_by="memory")
    all_warnings.extend(proc_warnings)
    
    return MetricsSnapshot(
        timestamp_utc=timestamp,
        hostname=hostname,
        platform=platform_info,
        cpu=cpu,
        memory=memory,
        disk=disk,
        top_processes=top_processes,
        warnings=all_warnings,
        psutil_available=PSUTIL_AVAILABLE,
    )


def is_psutil_available() -> bool:
    """Check if psutil is available."""
    return PSUTIL_AVAILABLE
