"""Built-in knowledge base for offline diagnostics.

This provides common solutions for Linux system errors when
LLM APIs are unavailable or for quick offline lookups.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
import re


@dataclass
class KnowledgeEntry:
    """A knowledge base entry with pattern matching."""
    
    pattern: str  # Regex pattern to match
    title: str
    description: str
    causes: List[str]
    solutions: List[str]
    severity: str  # "critical", "warning", "info"
    keywords: List[str]
    resources: List[str]


# Common Linux system error patterns and solutions
KNOWLEDGE_BASE: List[KnowledgeEntry] = [
    # OOM Killer
    KnowledgeEntry(
        pattern=r"Out of memory|oom-killer|oom_kill|Killed process.*oom",
        title="Out of Memory (OOM) Killer Invoked",
        description="The Linux OOM killer terminated a process because the system ran out of memory.",
        causes=[
            "Memory leak in application",
            "Insufficient RAM for workload",
            "Too many processes running",
            "Memory overcommitment",
            "Swap space exhausted"
        ],
        solutions=[
            "Increase system RAM or add swap space",
            "Identify and fix memory leaks using tools like valgrind",
            "Set memory limits with cgroups or ulimit",
            "Configure vm.overcommit_memory and vm.overcommit_ratio",
            "Use oom_score_adj to protect critical processes"
        ],
        severity="critical",
        keywords=["oom", "memory", "killed", "out of memory"],
        resources=[
            "https://www.kernel.org/doc/html/latest/admin-guide/mm/oom.html",
            "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/monitoring_and_managing_system_status_and_performance/assembly_managing-memory-with-oom_monitoring-and-managing-system-status-and-performance"
        ]
    ),
    
    # Kernel Panic
    KnowledgeEntry(
        pattern=r"Kernel panic|kernel BUG|BUG:|OOPS:|general protection fault",
        title="Kernel Panic / Oops",
        description="The kernel encountered an unrecoverable error and stopped execution.",
        causes=[
            "Hardware failure (RAM, CPU, disk)",
            "Corrupted kernel module",
            "Driver bug or incompatibility",
            "Kernel bug triggered by specific conditions",
            "Memory corruption"
        ],
        solutions=[
            "Check hardware with memtest86+ and disk diagnostics",
            "Update kernel to latest stable version",
            "Remove recently added kernel modules",
            "Check for known kernel bugs in distribution tracker",
            "Review and report bug at kernel.org if reproducible"
        ],
        severity="critical",
        keywords=["panic", "bug", "oops", "kernel", "crash"],
        resources=[
            "https://www.kernel.org/doc/html/latest/admin-guide/bug-hunting.html",
            "https://wiki.ubuntu.com/DebuggingKernelOops"
        ]
    ),
    
    # Disk I/O Errors
    KnowledgeEntry(
        pattern=r"I/O error|Buffer I/O error|end_request.*error|blk_update_request.*error|ata.*error",
        title="Disk I/O Error",
        description="The system encountered errors reading from or writing to a storage device.",
        causes=[
            "Failing hard drive or SSD",
            "Bad sectors on disk",
            "Loose or damaged SATA/power cables",
            "Filesystem corruption",
            "RAID array degradation"
        ],
        solutions=[
            "Check SMART data: smartctl -a /dev/sdX",
            "Run filesystem check: fsck /dev/sdX",
            "Check and reseat disk cables",
            "Replace failing drive immediately",
            "Backup data as soon as possible"
        ],
        severity="critical",
        keywords=["i/o", "disk", "error", "ata", "sata", "nvme"],
        resources=[
            "https://www.smartmontools.org/",
            "https://wiki.archlinux.org/title/S.M.A.R.T."
        ]
    ),
    
    # Segmentation Fault
    KnowledgeEntry(
        pattern=r"segfault|SIGSEGV|Segmentation fault",
        title="Segmentation Fault",
        description="A process attempted to access memory it wasn't allowed to access.",
        causes=[
            "Bug in application code (null pointer, buffer overflow)",
            "Corrupted shared library",
            "Stack overflow",
            "Hardware memory error",
            "Incompatible binary/library versions"
        ],
        solutions=[
            "Debug with gdb or strace to find crash location",
            "Check for known bugs in application",
            "Update to latest version of crashing software",
            "Run memtest86+ to check for RAM errors",
            "Reinstall affected packages"
        ],
        severity="warning",
        keywords=["segfault", "segmentation", "sigsegv", "crash"],
        resources=[
            "https://www.gnu.org/software/gdb/",
            "https://wiki.ubuntu.com/DebuggingProgramCrash"
        ]
    ),
    
    # USB Errors
    KnowledgeEntry(
        pattern=r"usb.*error|USB disconnect|device descriptor read.*error|reset.*port",
        title="USB Device Error",
        description="A USB device encountered communication errors or disconnected unexpectedly.",
        causes=[
            "Faulty USB cable or port",
            "Insufficient power for device",
            "USB controller issues",
            "Driver compatibility problems",
            "Device hardware failure"
        ],
        solutions=[
            "Try different USB port or cable",
            "Use powered USB hub for high-power devices",
            "Update USB drivers and kernel",
            "Check dmesg for specific error messages",
            "Disable USB autosuspend for problematic devices"
        ],
        severity="warning",
        keywords=["usb", "disconnect", "reset", "port", "hub"],
        resources=[
            "https://www.kernel.org/doc/html/latest/driver-api/usb/index.html"
        ]
    ),
    
    # Network Errors
    KnowledgeEntry(
        pattern=r"link (is )?down|carrier lost|network unreachable|connection timed out|NETDEV WATCHDOG",
        title="Network Connectivity Issue",
        description="Network interface lost connectivity or encountered errors.",
        causes=[
            "Physical cable disconnection",
            "Network interface hardware failure",
            "Driver bug or incompatibility",
            "DHCP lease expiration",
            "Router/switch issues"
        ],
        solutions=[
            "Check physical network connections",
            "Restart network interface: ip link set dev <iface> down && up",
            "Check router/switch status",
            "Update network drivers",
            "Review NetworkManager or systemd-networkd logs"
        ],
        severity="warning",
        keywords=["network", "link", "carrier", "ethernet", "wifi"],
        resources=[
            "https://wiki.archlinux.org/title/Network_configuration"
        ]
    ),
    
    # Systemd Service Failures
    KnowledgeEntry(
        pattern=r"Failed to start|service.*failed|systemd.*failed|entered failed state",
        title="Systemd Service Failure",
        description="A systemd service failed to start or crashed during operation.",
        causes=[
            "Configuration error in service file",
            "Missing dependencies",
            "Permission issues",
            "Application crash or bug",
            "Resource exhaustion"
        ],
        solutions=[
            "Check service status: systemctl status <service>",
            "View full logs: journalctl -u <service> -b",
            "Verify configuration files",
            "Check file permissions and ownership",
            "Look for dependency issues with systemctl list-dependencies"
        ],
        severity="warning",
        keywords=["systemd", "service", "failed", "unit"],
        resources=[
            "https://www.freedesktop.org/software/systemd/man/systemd.service.html"
        ]
    ),
    
    # Filesystem Errors
    KnowledgeEntry(
        pattern=r"EXT4-fs error|XFS.*error|Remounting filesystem read-only|journal.*error",
        title="Filesystem Error",
        description="The filesystem encountered an error and may have remounted read-only.",
        causes=[
            "Disk hardware failure",
            "Unclean shutdown",
            "Filesystem corruption",
            "Bad blocks on disk",
            "Kernel bug in filesystem driver"
        ],
        solutions=[
            "Unmount and run fsck from recovery mode",
            "Check disk health with SMART tools",
            "Restore from backup if corruption is severe",
            "Update kernel for filesystem driver fixes",
            "Consider filesystem migration if issues persist"
        ],
        severity="critical",
        keywords=["ext4", "xfs", "btrfs", "filesystem", "journal", "read-only"],
        resources=[
            "https://wiki.archlinux.org/title/Fsck",
            "https://ext4.wiki.kernel.org/"
        ]
    ),
    
    # CPU/Thermal Issues
    KnowledgeEntry(
        pattern=r"CPU.*temperature|thermal|overheating|mce.*error|Machine check|critical temperature",
        title="CPU/Thermal Issue",
        description="The system detected high temperatures or CPU errors.",
        causes=[
            "Insufficient cooling",
            "Dust buildup in cooling system",
            "Failed CPU fan",
            "Thermal paste degradation",
            "Overclocking instability"
        ],
        solutions=[
            "Clean dust from heatsinks and fans",
            "Check and replace thermal paste",
            "Verify all fans are working",
            "Reduce CPU frequency or disable overclocking",
            "Improve case airflow"
        ],
        severity="critical",
        keywords=["temperature", "thermal", "overheating", "mce", "cpu"],
        resources=[
            "https://wiki.archlinux.org/title/CPU_frequency_scaling",
            "https://www.kernel.org/doc/html/latest/x86/mce.html"
        ]
    ),
    
    # Authentication/PAM Errors
    KnowledgeEntry(
        pattern=r"authentication failure|pam.*error|Failed password|Invalid user",
        title="Authentication Failure",
        description="User authentication failed, possibly indicating security issues.",
        causes=[
            "Incorrect password entered",
            "User account locked or expired",
            "PAM configuration error",
            "Brute force attack attempt",
            "SSH key mismatch"
        ],
        solutions=[
            "Verify correct credentials are being used",
            "Check account status: passwd -S <user>",
            "Review PAM configuration in /etc/pam.d/",
            "Check for attack patterns with fail2ban",
            "Review /var/log/auth.log for details"
        ],
        severity="warning",
        keywords=["auth", "pam", "password", "login", "ssh"],
        resources=[
            "https://wiki.archlinux.org/title/PAM",
            "https://www.fail2ban.org/"
        ]
    ),
    
    # GPU Errors
    KnowledgeEntry(
        pattern=r"GPU.*error|drm.*error|amdgpu.*error|nouveau.*error|nvidia.*error|i915.*error",
        title="GPU/Display Driver Error",
        description="Graphics driver encountered an error.",
        causes=[
            "GPU hardware issue",
            "Driver bug",
            "Overheating GPU",
            "Insufficient power supply",
            "Kernel/driver version mismatch"
        ],
        solutions=[
            "Update GPU drivers to latest version",
            "Check GPU temperature and cooling",
            "Try different kernel version",
            "Check GPU power connections",
            "Test with different driver (open vs proprietary)"
        ],
        severity="warning",
        keywords=["gpu", "drm", "graphics", "nvidia", "amd", "intel"],
        resources=[
            "https://wiki.archlinux.org/title/NVIDIA",
            "https://wiki.archlinux.org/title/AMDGPU"
        ]
    ),
    
    # ACPI Errors
    KnowledgeEntry(
        pattern=r"ACPI.*error|ACPI.*warning|ACPI BIOS Error",
        title="ACPI Error",
        description="Advanced Configuration and Power Interface reported an error.",
        causes=[
            "BIOS/UEFI bug",
            "ACPI table issues",
            "Kernel ACPI compatibility issue",
            "Hardware not properly described in firmware"
        ],
        solutions=[
            "Update BIOS/UEFI firmware",
            "Try kernel boot parameter: acpi=off (test only)",
            "Report bug to hardware vendor",
            "Check for kernel workarounds for specific hardware"
        ],
        severity="info",
        keywords=["acpi", "bios", "power", "firmware"],
        resources=[
            "https://www.kernel.org/doc/html/latest/admin-guide/acpi/index.html"
        ]
    ),
]


class KnowledgeBase:
    """Query the built-in knowledge base for diagnostics."""
    
    def __init__(self):
        self.entries = KNOWLEDGE_BASE
        # Pre-compile regex patterns for efficiency
        self._compiled_patterns: Dict[int, re.Pattern] = {}
        for i, entry in enumerate(self.entries):
            self._compiled_patterns[i] = re.compile(entry.pattern, re.IGNORECASE)
    
    def search(self, text: str, max_results: int = 5) -> List[KnowledgeEntry]:
        """Search knowledge base for entries matching the text.
        
        Args:
            text: Log text to search for matches
            max_results: Maximum number of results to return
            
        Returns:
            List of matching KnowledgeEntry objects, sorted by relevance
        """
        matches: List[tuple[int, KnowledgeEntry]] = []
        
        text_lower = text.lower()
        
        for i, entry in enumerate(self.entries):
            score = 0
            
            # Pattern match (highest weight)
            pattern = self._compiled_patterns[i]
            pattern_matches = pattern.findall(text)
            if pattern_matches:
                score += 10 * len(pattern_matches)
            
            # Keyword match (secondary weight)
            for keyword in entry.keywords:
                if keyword.lower() in text_lower:
                    score += 2
            
            if score > 0:
                matches.append((score, entry))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)
        
        return [entry for _, entry in matches[:max_results]]
    
    def get_by_keyword(self, keyword: str) -> List[KnowledgeEntry]:
        """Get entries by keyword.
        
        Args:
            keyword: Keyword to search for
            
        Returns:
            List of matching entries
        """
        keyword_lower = keyword.lower()
        return [
            entry for entry in self.entries
            if keyword_lower in [k.lower() for k in entry.keywords]
        ]
    
    def get_critical(self) -> List[KnowledgeEntry]:
        """Get all critical severity entries."""
        return [e for e in self.entries if e.severity == "critical"]
    
    def format_entry(self, entry: KnowledgeEntry) -> str:
        """Format a knowledge entry as readable text.
        
        Args:
            entry: The entry to format
            
        Returns:
            Formatted string
        """
        lines = [
            f"## {entry.title}",
            "",
            f"**Severity:** {entry.severity.upper()}",
            "",
            entry.description,
            "",
            "### Possible Causes",
        ]
        
        for cause in entry.causes:
            lines.append(f"- {cause}")
        
        lines.extend(["", "### Recommended Solutions"])
        
        for solution in entry.solutions:
            lines.append(f"- {solution}")
        
        if entry.resources:
            lines.extend(["", "### Resources"])
            for resource in entry.resources:
                lines.append(f"- {resource}")
        
        return "\n".join(lines)
    
    def format_results(self, entries: List[KnowledgeEntry]) -> str:
        """Format multiple entries as readable text.
        
        Args:
            entries: List of entries to format
            
        Returns:
            Formatted string with all entries
        """
        if not entries:
            return "No matching entries found in knowledge base."
        
        sections = []
        for entry in entries:
            sections.append(self.format_entry(entry))
        
        return "\n\n---\n\n".join(sections)


# Singleton instance
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """Get the singleton knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base
