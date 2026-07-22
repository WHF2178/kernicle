"""Fixtures package for Kernicle tests."""

from tests.fixtures.synthetic_logs import (
    CLEAN_KERNEL_LOG,
    KERNEL_PANIC_LOG,
    OOPS_BUG_LOG,
    OOM_KILLER_LOG,
    MIXED_ANOMALIES_LOG,
    NO_TIMESTAMP_LOG,
    ALL_SAMPLES,
)

__all__ = [
    "CLEAN_KERNEL_LOG",
    "KERNEL_PANIC_LOG",
    "OOPS_BUG_LOG",
    "OOM_KILLER_LOG",
    "MIXED_ANOMALIES_LOG",
    "NO_TIMESTAMP_LOG",
    "ALL_SAMPLES",
]
