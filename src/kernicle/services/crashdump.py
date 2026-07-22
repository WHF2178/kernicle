"""
Crash Dump Capture and Analysis for Kernicle.

This module provides functionality to:
1. Set up kdump/kexec for capturing kernel crashes
2. Detect and analyze crash dumps (vmcore) after reboot
3. Extract meaningful information from crash dumps
4. Integrate with AI analysis for crash diagnosis

CRITICAL: This is the core differentiator of Kernicle - capturing logs
from hard crashes that would otherwise be completely lost.
"""

import os
import re
import subprocess
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple
from enum import Enum


class CrashCaptureStatus(Enum):
    """Status of crash capture setup."""
    NOT_INSTALLED = "not_installed"
    INSTALLED_NOT_CONFIGURED = "installed_not_configured"
    CONFIGURED_NOT_ENABLED = "configured_not_enabled"
    ENABLED_NOT_LOADED = "enabled_not_loaded"
    FULLY_OPERATIONAL = "fully_operational"


@dataclass
class CrashDumpInfo:
    """Information about a crash dump."""
    dump_path: Path
    timestamp: datetime
    kernel_version: str
    crash_command: Optional[str] = None  # Command that triggered crash
    panic_message: Optional[str] = None
    call_trace: List[str] = field(default_factory=list)
    dmesg_tail: List[str] = field(default_factory=list)
    memory_info: Optional[dict] = None
    cpu_info: Optional[dict] = None
    
    def to_dict(self) -> dict:
        return {
            "dump_path": str(self.dump_path),
            "timestamp": self.timestamp.isoformat(),
            "kernel_version": self.kernel_version,
            "crash_command": self.crash_command,
            "panic_message": self.panic_message,
            "call_trace": self.call_trace,
            "dmesg_tail": self.dmesg_tail,
            "memory_info": self.memory_info,
            "cpu_info": self.cpu_info,
        }


@dataclass
class SetupResult:
    """Result of kdump setup operation."""
    success: bool
    status: CrashCaptureStatus
    message: str
    requires_reboot: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status.value,
            "message": self.message,
            "requires_reboot": self.requires_reboot,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class CrashDumpManager:
    """
    Manages crash dump capture setup and analysis.
    
    This is the heart of Kernicle's crash capture capability.
    """
    
    # Default crash dump location
    CRASH_DIR = Path("/var/crash")
    
    # Required packages
    REQUIRED_PACKAGES = ["kdump-tools", "kexec-tools", "crash", "makedumpfile"]
    
    # GRUB config file
    GRUB_CONFIG = Path("/etc/default/grub")
    
    # kdump config file
    KDUMP_CONFIG = Path("/etc/default/kdump-tools")
    
    def __init__(self, crash_dir: Optional[Path] = None):
        """Initialize crash dump manager."""
        self.crash_dir = crash_dir or self.CRASH_DIR
    
    # =========================================================================
    # STATUS CHECKING
    # =========================================================================
    
    def get_status(self) -> CrashCaptureStatus:
        """
        Check the current status of crash capture setup.
        
        Returns:
            CrashCaptureStatus indicating current state
        """
        # Check if packages are installed
        if not self._are_packages_installed():
            return CrashCaptureStatus.NOT_INSTALLED
        
        # MOST IMPORTANT CHECK: Is crash kernel actually loaded?
        # If yes, the system is fully operational regardless of how it was configured
        if self._is_crash_kernel_loaded():
            return CrashCaptureStatus.FULLY_OPERATIONAL
        
        # Check if crashkernel is configured (either in GRUB file or in current cmdline)
        crashkernel_configured = self._is_crashkernel_configured() or self._get_crashkernel_param() is not None
        
        if not crashkernel_configured:
            return CrashCaptureStatus.INSTALLED_NOT_CONFIGURED
        
        # Check if kdump service is enabled
        if not self._is_kdump_enabled():
            return CrashCaptureStatus.CONFIGURED_NOT_ENABLED
        
        # Crashkernel configured and kdump enabled, but kernel not loaded = needs reboot
        return CrashCaptureStatus.ENABLED_NOT_LOADED
    
    def get_detailed_status(self) -> dict:
        """
        Get detailed status information about crash capture setup.
        
        Returns:
            Dictionary with detailed status information
        """
        status = self.get_status()
        
        details = {
            "status": status.value,
            "status_description": self._get_status_description(status),
            "packages": {},
            "crashkernel_configured": False,
            "crashkernel_param": None,
            "kdump_enabled": False,
            "kdump_running": False,
            "crash_kernel_loaded": False,
            "crash_dir": str(self.crash_dir),
            "crash_dir_exists": self.crash_dir.exists(),
            "pending_crashes": [],
            "recommendations": [],
        }
        
        # Check each package
        for pkg in self.REQUIRED_PACKAGES:
            details["packages"][pkg] = self._is_package_installed(pkg)
        
        # Check crashkernel parameter
        crashkernel_in_grub = self._is_crashkernel_configured()
        crashkernel_param = self._get_crashkernel_param()
        details["crashkernel_configured"] = crashkernel_in_grub or crashkernel_param is not None
        details["crashkernel_param"] = crashkernel_param
        details["crashkernel_in_grub"] = crashkernel_in_grub
        
        # Check kdump service
        details["kdump_enabled"] = self._is_kdump_enabled()
        details["kdump_running"] = self._is_kdump_running()
        
        # Check crash kernel loaded
        details["crash_kernel_loaded"] = self._is_crash_kernel_loaded()
        
        # Check for pending crash dumps
        details["pending_crashes"] = self.list_crash_dumps()
        
        # Generate recommendations
        details["recommendations"] = self._get_recommendations(status)
        
        return details
    
    def _get_status_description(self, status: CrashCaptureStatus) -> str:
        """Get human-readable description of status."""
        descriptions = {
            CrashCaptureStatus.NOT_INSTALLED: 
                "kdump/kexec packages are not installed. Crash capture is NOT possible.",
            CrashCaptureStatus.INSTALLED_NOT_CONFIGURED:
                "Packages installed but crashkernel not configured in GRUB.",
            CrashCaptureStatus.CONFIGURED_NOT_ENABLED:
                "Crashkernel configured but kdump service not enabled.",
            CrashCaptureStatus.ENABLED_NOT_LOADED:
                "kdump enabled but crash kernel not loaded. Reboot required.",
            CrashCaptureStatus.FULLY_OPERATIONAL:
                "Crash capture is FULLY OPERATIONAL. System will capture kernel panics.",
        }
        return descriptions.get(status, "Unknown status")
    
    def _get_recommendations(self, status: CrashCaptureStatus) -> List[str]:
        """Get recommendations based on current status."""
        recommendations = []
        
        if status == CrashCaptureStatus.NOT_INSTALLED:
            recommendations.append("Run: sudo kernicle setup-crash")
            recommendations.append("Or manually: sudo apt install kdump-tools kexec-tools crash")
        
        elif status == CrashCaptureStatus.INSTALLED_NOT_CONFIGURED:
            recommendations.append("Configure crashkernel in GRUB")
            recommendations.append("Run: sudo kernicle setup-crash --configure")
        
        elif status == CrashCaptureStatus.CONFIGURED_NOT_ENABLED:
            recommendations.append("Enable kdump service: sudo systemctl enable kdump-tools")
            recommendations.append("Start kdump service: sudo systemctl start kdump-tools")
        
        elif status == CrashCaptureStatus.ENABLED_NOT_LOADED:
            recommendations.append("Reboot the system to load crash kernel")
            recommendations.append("After reboot, verify with: cat /sys/kernel/kexec_crash_loaded")
        
        return recommendations
    
    # =========================================================================
    # PACKAGE MANAGEMENT
    # =========================================================================
    
    def _is_package_installed(self, package: str) -> bool:
        """Check if a package is installed."""
        try:
            result = subprocess.run(
                ["dpkg", "-s", package],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0 and "Status: install ok installed" in result.stdout
        except Exception:
            return False
    
    def _are_packages_installed(self) -> bool:
        """Check if all required packages are installed."""
        # At minimum, kdump-tools must be installed
        return self._is_package_installed("kdump-tools")
    
    def install_packages(self) -> Tuple[bool, str]:
        """
        Install required packages for crash capture.
        Requires sudo/root privileges.
        
        Returns:
            Tuple of (success, message)
        """
        if os.geteuid() != 0:
            return False, "Root privileges required. Run with sudo."
        
        try:
            # Update package list
            subprocess.run(
                ["apt-get", "update"],
                capture_output=True,
                timeout=120
            )
            
            # Install packages
            result = subprocess.run(
                ["apt-get", "install", "-y"] + self.REQUIRED_PACKAGES,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                return True, "Packages installed successfully"
            else:
                return False, f"Installation failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, f"Installation error: {str(e)}"
    
    # =========================================================================
    # GRUB CONFIGURATION
    # =========================================================================
    
    def _is_crashkernel_configured(self) -> bool:
        """Check if crashkernel parameter is in GRUB config."""
        try:
            if self.GRUB_CONFIG.exists():
                content = self.GRUB_CONFIG.read_text()
                return "crashkernel=" in content
            return False
        except Exception:
            return False
    
    def _get_crashkernel_param(self) -> Optional[str]:
        """Get current crashkernel parameter from /proc/cmdline."""
        try:
            cmdline = Path("/proc/cmdline").read_text()
            match = re.search(r'crashkernel=(\S+)', cmdline)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
    def configure_crashkernel(self, memory: str = "512M-:192M") -> Tuple[bool, str]:
        """
        Configure crashkernel parameter in GRUB.
        
        Args:
            memory: Crashkernel memory allocation (e.g., "512M-:192M")
                    Format: "threshold:size" - reserve 'size' when RAM > 'threshold'
        
        Returns:
            Tuple of (success, message)
        """
        if os.geteuid() != 0:
            return False, "Root privileges required. Run with sudo."
        
        try:
            # Backup GRUB config
            backup_path = self.GRUB_CONFIG.with_suffix('.grub.bak')
            shutil.copy(self.GRUB_CONFIG, backup_path)
            
            content = self.GRUB_CONFIG.read_text()
            
            # Find GRUB_CMDLINE_LINUX_DEFAULT line
            pattern = r'(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*)'
            match = re.search(pattern, content)
            
            if match:
                current = match.group(1)
                
                # Remove any existing crashkernel param
                current = re.sub(r'\s*crashkernel=\S+', '', current)
                
                # Add new crashkernel param
                new_line = f'{current} crashkernel={memory}'
                content = content.replace(match.group(1), new_line)
            else:
                # Add new line if not found
                content += f'\nGRUB_CMDLINE_LINUX_DEFAULT="crashkernel={memory}"\n'
            
            # Write updated config
            self.GRUB_CONFIG.write_text(content)
            
            # Update GRUB
            result = subprocess.run(
                ["update-grub"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, f"Crashkernel configured ({memory}). REBOOT REQUIRED."
            else:
                return False, f"GRUB update failed: {result.stderr}"
                
        except Exception as e:
            return False, f"Configuration error: {str(e)}"
    
    # =========================================================================
    # KDUMP SERVICE MANAGEMENT
    # =========================================================================
    
    def _is_kdump_enabled(self) -> bool:
        """Check if kdump service is enabled."""
        try:
            result = subprocess.run(
                ["systemctl", "is-enabled", "kdump-tools"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() == "enabled"
        except Exception:
            return False
    
    def _is_kdump_running(self) -> bool:
        """Check if kdump service is running."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "kdump-tools"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False
    
    def _is_crash_kernel_loaded(self) -> bool:
        """Check if crash kernel is actually loaded in memory."""
        try:
            kexec_loaded = Path("/sys/kernel/kexec_crash_loaded")
            if kexec_loaded.exists():
                return kexec_loaded.read_text().strip() == "1"
            return False
        except Exception:
            return False
    
    def enable_kdump(self) -> Tuple[bool, str]:
        """Enable and start kdump service."""
        if os.geteuid() != 0:
            return False, "Root privileges required. Run with sudo."
        
        try:
            # Configure kdump-tools
            if self.KDUMP_CONFIG.exists():
                content = self.KDUMP_CONFIG.read_text()
                # Enable kdump
                content = re.sub(r'USE_KDUMP=\d', 'USE_KDUMP=1', content)
                self.KDUMP_CONFIG.write_text(content)
            
            # Enable service
            subprocess.run(
                ["systemctl", "enable", "kdump-tools"],
                capture_output=True,
                timeout=30
            )
            
            # Start service
            result = subprocess.run(
                ["systemctl", "start", "kdump-tools"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, "kdump service enabled and started"
            else:
                # May fail if crash kernel not loaded (needs reboot)
                return True, "kdump enabled. May need reboot to fully activate."
                
        except Exception as e:
            return False, f"Failed to enable kdump: {str(e)}"
    
    # =========================================================================
    # COMPLETE SETUP
    # =========================================================================
    
    def setup_crash_capture(self, crashkernel_mem: str = "512M-:192M") -> SetupResult:
        """
        Complete setup of crash capture system.
        
        This is the main entry point for setting up kdump/kexec.
        Requires root privileges.
        
        Args:
            crashkernel_mem: Memory to reserve for crash kernel
            
        Returns:
            SetupResult with status and any errors
        """
        errors = []
        warnings = []
        requires_reboot = False
        
        # Check privileges
        if os.geteuid() != 0:
            return SetupResult(
                success=False,
                status=self.get_status(),
                message="Root privileges required. Run: sudo kernicle setup-crash",
                errors=["Not running as root"]
            )
        
        # Step 1: Install packages
        if not self._are_packages_installed():
            success, msg = self.install_packages()
            if not success:
                errors.append(msg)
                return SetupResult(
                    success=False,
                    status=CrashCaptureStatus.NOT_INSTALLED,
                    message="Failed to install required packages",
                    errors=errors
                )
        
        # Step 2: Configure crashkernel in GRUB
        if not self._is_crashkernel_configured():
            success, msg = self.configure_crashkernel(crashkernel_mem)
            if not success:
                errors.append(msg)
            else:
                requires_reboot = True
                warnings.append("GRUB updated - reboot required")
        
        # Step 3: Enable kdump service
        if not self._is_kdump_enabled():
            success, msg = self.enable_kdump()
            if not success:
                errors.append(msg)
        
        # Check if crash kernel is loaded
        if not self._is_crash_kernel_loaded():
            requires_reboot = True
            warnings.append("Crash kernel not loaded - reboot required")
        
        # Get final status
        final_status = self.get_status()
        
        if errors:
            return SetupResult(
                success=False,
                status=final_status,
                message="Setup completed with errors",
                requires_reboot=requires_reboot,
                errors=errors,
                warnings=warnings
            )
        
        if requires_reboot:
            return SetupResult(
                success=True,
                status=final_status,
                message="Setup complete. REBOOT REQUIRED to activate crash capture.",
                requires_reboot=True,
                warnings=warnings
            )
        
        return SetupResult(
            success=True,
            status=CrashCaptureStatus.FULLY_OPERATIONAL,
            message="Crash capture is fully operational!",
            requires_reboot=False
        )
    
    # =========================================================================
    # CRASH DUMP DETECTION AND ANALYSIS
    # =========================================================================
    
    def list_crash_dumps(self) -> List[dict]:
        """
        List all crash dumps in the crash directory.
        
        Returns:
            List of crash dump info dictionaries
        """
        dumps = []
        
        if not self.crash_dir.exists():
            return dumps
        
        # Look for crash dump directories (format varies by distro)
        # Ubuntu/Debian: /var/crash/YYYYMMDDHHMMSS/
        # Also check for vmcore files directly
        
        for item in self.crash_dir.iterdir():
            if item.is_dir():
                vmcore = item / "vmcore"
                if vmcore.exists():
                    dumps.append({
                        "path": str(item),
                        "vmcore": str(vmcore),
                        "timestamp": datetime.fromtimestamp(
                            item.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "size_mb": vmcore.stat().st_size / (1024 * 1024),
                        "analyzed": (item / "kernicle_analysis.json").exists()
                    })
            elif item.name.startswith("vmcore"):
                dumps.append({
                    "path": str(item.parent),
                    "vmcore": str(item),
                    "timestamp": datetime.fromtimestamp(
                        item.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "size_mb": item.stat().st_size / (1024 * 1024),
                    "analyzed": False
                })
        
        # Sort by timestamp (newest first)
        dumps.sort(key=lambda x: x["timestamp"], reverse=True)
        return dumps
    
    def has_unanalyzed_crashes(self) -> bool:
        """Check if there are any unanalyzed crash dumps."""
        dumps = self.list_crash_dumps()
        return any(not d["analyzed"] for d in dumps)
    
    def analyze_crash_dump(self, dump_path: Path) -> Optional[CrashDumpInfo]:
        """
        Analyze a crash dump and extract information.
        
        Args:
            dump_path: Path to crash dump directory or vmcore file
            
        Returns:
            CrashDumpInfo with extracted information, or None if failed
        """
        if dump_path.is_file():
            vmcore_path = dump_path
            dump_dir = dump_path.parent
        else:
            vmcore_path = dump_path / "vmcore"
            dump_dir = dump_path
        
        if not vmcore_path.exists():
            return None
        
        try:
            # Extract information using crash utility
            crash_info = CrashDumpInfo(
                dump_path=dump_dir,
                timestamp=datetime.fromtimestamp(
                    vmcore_path.stat().st_mtime, tz=timezone.utc
                ),
                kernel_version=self._extract_kernel_version(vmcore_path),
            )
            
            # Try to extract more details
            crash_info.panic_message = self._extract_panic_message(vmcore_path)
            crash_info.call_trace = self._extract_call_trace(vmcore_path)
            crash_info.dmesg_tail = self._extract_dmesg(vmcore_path)
            
            return crash_info
            
        except Exception as e:
            print(f"Error analyzing crash dump: {e}")
            return None
    
    def _extract_kernel_version(self, vmcore_path: Path) -> str:
        """Extract kernel version from vmcore."""
        try:
            # Try using crash utility
            result = subprocess.run(
                ["crash", "--osrelease", str(vmcore_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        # Fallback: try to read from vmcore header
        try:
            # The kernel version is often near the beginning
            with open(vmcore_path, "rb") as f:
                header = f.read(4096).decode("utf-8", errors="ignore")
                match = re.search(r'Linux version (\S+)', header)
                if match:
                    return match.group(1)
        except Exception:
            pass
        
        return "unknown"
    
    def _extract_panic_message(self, vmcore_path: Path) -> Optional[str]:
        """Extract panic message from vmcore using crash utility."""
        try:
            # Use crash utility to get panic message
            crash_script = "log | grep -A5 'Kernel panic'\nquit\n"
            result = subprocess.run(
                ["crash", "-s", str(vmcore_path)],
                input=crash_script,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                # Find the panic line
                for line in result.stdout.splitlines():
                    if "Kernel panic" in line or "Oops" in line:
                        return line.strip()
        except Exception:
            pass
        
        return None
    
    def _extract_call_trace(self, vmcore_path: Path) -> List[str]:
        """Extract call trace from vmcore."""
        trace = []
        
        try:
            crash_script = "bt\nquit\n"
            result = subprocess.run(
                ["crash", "-s", str(vmcore_path)],
                input=crash_script,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # Parse backtrace output
                in_trace = False
                for line in result.stdout.splitlines():
                    if "#" in line and ("0x" in line or "[" in line):
                        trace.append(line.strip())
                        in_trace = True
                    elif in_trace and line.strip() == "":
                        break
        except Exception:
            pass
        
        return trace[:50]  # Limit to 50 frames
    
    def _extract_dmesg(self, vmcore_path: Path) -> List[str]:
        """Extract dmesg log from vmcore."""
        dmesg_lines = []
        
        try:
            crash_script = "log | tail -100\nquit\n"
            result = subprocess.run(
                ["crash", "-s", str(vmcore_path)],
                input=crash_script,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                dmesg_lines = result.stdout.splitlines()[-100:]
        except Exception:
            pass
        
        return dmesg_lines
    
    def generate_crash_report(
        self, 
        crash_info: CrashDumpInfo,
        output_dir: Path
    ) -> Path:
        """
        Generate a comprehensive crash report.
        
        Args:
            crash_info: Analyzed crash information
            output_dir: Directory to write report
            
        Returns:
            Path to generated report
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write JSON data
        json_path = output_dir / "crash_analysis.json"
        json_path.write_text(
            json.dumps(crash_info.to_dict(), indent=2),
            encoding="utf-8"
        )
        
        # Write human-readable report
        report_path = output_dir / "crash_report.txt"
        report_lines = [
            "=" * 70,
            "KERNICLE CRASH DUMP ANALYSIS",
            "Kernicle reads the CHAOS; shows the CLARITY",
            "=" * 70,
            "",
            f"Crash Time: {crash_info.timestamp.isoformat()}",
            f"Kernel Version: {crash_info.kernel_version}",
            f"Dump Location: {crash_info.dump_path}",
            "",
            "-" * 70,
            "PANIC MESSAGE",
            "-" * 70,
            crash_info.panic_message or "Unable to extract panic message",
            "",
            "-" * 70,
            "CALL TRACE (Stack Backtrace)",
            "-" * 70,
        ]
        
        if crash_info.call_trace:
            report_lines.extend(crash_info.call_trace)
        else:
            report_lines.append("Unable to extract call trace")
        
        report_lines.extend([
            "",
            "-" * 70,
            "KERNEL LOG (Last 100 lines before crash)",
            "-" * 70,
        ])
        
        if crash_info.dmesg_tail:
            report_lines.extend(crash_info.dmesg_tail)
        else:
            report_lines.append("Unable to extract kernel log")
        
        report_lines.extend([
            "",
            "=" * 70,
            "END OF CRASH REPORT",
            "=" * 70,
        ])
        
        report_path.write_text("\n".join(report_lines), encoding="utf-8")
        
        return report_path


# Convenience functions
def get_crash_status() -> dict:
    """Get current crash capture status."""
    manager = CrashDumpManager()
    return manager.get_detailed_status()


def setup_crash_capture() -> SetupResult:
    """Set up crash capture (requires root)."""
    manager = CrashDumpManager()
    return manager.setup_crash_capture()


def check_for_crashes() -> List[dict]:
    """Check for any crash dumps."""
    manager = CrashDumpManager()
    return manager.list_crash_dumps()


def analyze_latest_crash() -> Optional[CrashDumpInfo]:
    """Analyze the most recent crash dump."""
    manager = CrashDumpManager()
    dumps = manager.list_crash_dumps()
    
    if not dumps:
        return None
    
    latest = dumps[0]
    return manager.analyze_crash_dump(Path(latest["vmcore"]))
