"""
Synthetic log sample fixtures for testing anomaly detection.
Sprint 2: Contains samples for kernel panic, oops, BUG, call trace, OOM.
"""

# Clean logs - no anomalies
CLEAN_KERNEL_LOG = """2025-12-30T10:00:00+0000 myhost kernel: Linux version 5.15.0-generic
2025-12-30T10:00:00+0000 myhost kernel: Command line: BOOT_IMAGE=/vmlinuz-5.15.0-generic root=/dev/sda1 ro
2025-12-30T10:00:01+0000 myhost kernel: x86/cpu: User Mode Instruction Prevention (UMIP) activated
2025-12-30T10:00:01+0000 myhost kernel: Initializing cgroup subsys cpuset
2025-12-30T10:00:02+0000 myhost kernel: ACPI: Core revision 20210730
2025-12-30T10:00:02+0000 myhost kernel: clocksource: tsc: mask: 0xffffffffffffffff max_cycles: 0x2b2c
2025-12-30T10:00:03+0000 myhost kernel: smpboot: CPU0: Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz
2025-12-30T10:00:03+0000 myhost kernel: smpboot: Total of 8 processors activated
2025-12-30T10:00:04+0000 myhost kernel: NET: Registered protocol family 2
2025-12-30T10:00:04+0000 myhost kernel: IP idents hash table entries: 65536
2025-12-30T10:00:05+0000 myhost kernel: e1000e 0000:00:1f.6: MAC: 12, PHY: 12, PBA No: 000000-000
2025-12-30T10:00:06+0000 myhost kernel: EXT4-fs (sda1): mounted filesystem with ordered data mode
"""

# Kernel panic sequence - includes panic, not syncing, call trace
KERNEL_PANIC_LOG = """2025-12-30T12:00:00+0000 myhost kernel: Linux version 5.15.0-generic
2025-12-30T12:00:01+0000 myhost kernel: Loading initial ramdisk...
2025-12-30T12:00:02+0000 myhost kernel: Starting kernel ...
2025-12-30T12:15:30+0000 myhost kernel: BUG: unable to handle page fault for address: ffffffff00000000
2025-12-30T12:15:30+0000 myhost kernel: #PF: supervisor read access in kernel mode
2025-12-30T12:15:30+0000 myhost kernel: #PF: error_code(0x0000) - not-present page
2025-12-30T12:15:30+0000 myhost kernel: Oops: 0000 [#1] SMP NOPTI
2025-12-30T12:15:30+0000 myhost kernel: CPU: 2 PID: 1234 Comm: process_name Tainted: G           OE
2025-12-30T12:15:30+0000 myhost kernel: RIP: 0010:some_kernel_function+0x42/0x100
2025-12-30T12:15:30+0000 myhost kernel: Call Trace:
2025-12-30T12:15:30+0000 myhost kernel:  <TASK>
2025-12-30T12:15:30+0000 myhost kernel:  another_function+0x15/0x20
2025-12-30T12:15:30+0000 myhost kernel:  syscall_handler+0x28/0x40
2025-12-30T12:15:30+0000 myhost kernel:  </TASK>
2025-12-30T12:15:31+0000 myhost kernel: Kernel panic - not syncing: Fatal exception
2025-12-30T12:15:31+0000 myhost kernel: Kernel Offset: disabled
2025-12-30T12:15:31+0000 myhost kernel: ---[ end Kernel panic - not syncing: Fatal exception ]---
"""

# Oops/BUG/Call Trace sequence
OOPS_BUG_LOG = """2025-12-30T14:00:00+0000 myhost kernel: Normal operation log entry
2025-12-30T14:00:01+0000 myhost kernel: Loading module xyz
2025-12-30T14:00:02+0000 myhost kernel: Module initialized
2025-12-30T14:30:00+0000 myhost kernel: BUG: scheduling while atomic: kworker/0:1/123/0x00000002
2025-12-30T14:30:00+0000 myhost kernel: Modules linked in: nvidia(POE) snd_hda_codec_hdmi
2025-12-30T14:30:00+0000 myhost kernel: CPU: 0 PID: 123 Comm: kworker/0:1 Tainted: P           OE
2025-12-30T14:30:00+0000 myhost kernel: Call Trace:
2025-12-30T14:30:00+0000 myhost kernel:  dump_stack+0x6d/0x88
2025-12-30T14:30:00+0000 myhost kernel:  __schedule_bug+0x55/0x70
2025-12-30T14:30:00+0000 myhost kernel:  __schedule+0x5c9/0x850
2025-12-30T14:30:01+0000 myhost kernel: Oops: 0002 [#1] PREEMPT SMP
2025-12-30T14:30:01+0000 myhost kernel: RIP: 0010:faulty_function+0x20/0x50
2025-12-30T14:30:02+0000 myhost kernel: Attempting recovery...
"""

# OOM (Out of Memory) killer sample
OOM_KILLER_LOG = """2025-12-30T16:00:00+0000 myhost kernel: Normal operation log entry
2025-12-30T16:30:00+0000 myhost kernel: memory allocation failed: out of memory
2025-12-30T16:30:00+0000 myhost kernel: Out of memory: Kill process 5432 (memory_hog) score 950 or sacrifice child
2025-12-30T16:30:00+0000 myhost kernel: Killed process 5432 (memory_hog) total-vm:8388608kB, anon-rss:8000000kB
2025-12-30T16:30:01+0000 myhost kernel: oom-killer: gfp_mask=0x6200ca(GFP_HIGHUSER_MOVABLE), order=0
2025-12-30T16:30:01+0000 myhost kernel: oom_reaper: reaped process 5432 (memory_hog), now anon-rss:0kB
2025-12-30T16:30:02+0000 myhost kernel: Normal operation resumed
"""

# Mixed anomalies - multiple issues spread in time
MIXED_ANOMALIES_LOG = """2025-12-30T08:00:00+0000 myhost kernel: Boot started
2025-12-30T08:00:01+0000 myhost kernel: System initializing
2025-12-30T08:30:00+0000 myhost kernel: BUG: soft lockup - CPU#2 stuck for 22s! [kworker/2:1:456]
2025-12-30T08:30:00+0000 myhost kernel: CPU: 2 PID: 456 Comm: kworker/2:1 Tainted: G
2025-12-30T08:30:01+0000 myhost kernel: Call Trace:
2025-12-30T08:30:01+0000 myhost kernel:  spin_lock_function+0x20/0x30
2025-12-30T08:35:00+0000 myhost kernel: Recovered from soft lockup
2025-12-30T09:00:00+0000 myhost kernel: Normal operation
2025-12-30T10:15:00+0000 myhost kernel: Out of memory: Kill process 7890 (chrome) score 850 or sacrifice child
2025-12-30T10:15:00+0000 myhost kernel: Killed process 7890 (chrome) total-vm:4194304kB
2025-12-30T10:15:01+0000 myhost kernel: Memory freed
2025-12-30T11:30:00+0000 myhost kernel: System stable
2025-12-30T14:00:00+0000 myhost kernel: BUG: kernel NULL pointer dereference
2025-12-30T14:00:00+0000 myhost kernel: Oops: 0000 [#1] SMP NOPTI
2025-12-30T14:00:00+0000 myhost kernel: Call Trace:
2025-12-30T14:00:00+0000 myhost kernel:  faulty_module+0x42/0x100
2025-12-30T14:00:01+0000 myhost kernel: Kernel panic - not syncing: Fatal exception
2025-12-30T14:00:01+0000 myhost kernel: ---[ end Kernel panic - not syncing: Fatal exception ]---
"""

# Log without timestamps (for proximity-based grouping tests)
NO_TIMESTAMP_LOG = """kernel: Linux version 5.15.0-generic
kernel: Loading modules...
kernel: BUG: scheduling while atomic
kernel: Call Trace:
kernel:  dump_stack+0x6d/0x88
kernel:  faulty_function+0x10/0x20
kernel: Normal operation
kernel: More normal logs
kernel: Another normal entry
kernel: Yet another normal entry
"""

# All samples dictionary for easy access
ALL_SAMPLES = {
    "clean": CLEAN_KERNEL_LOG,
    "kernel_panic": KERNEL_PANIC_LOG,
    "oops_bug": OOPS_BUG_LOG,
    "oom_killer": OOM_KILLER_LOG,
    "mixed": MIXED_ANOMALIES_LOG,
    "no_timestamp": NO_TIMESTAMP_LOG,
}
