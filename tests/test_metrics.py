"""
Tests for metrics.py - system metrics collection.
Sprint 3: Tests metrics snapshot, psutil integration, graceful degradation.
"""

import pytest
from unittest.mock import patch, MagicMock

from kernicle.services.metrics import (
    capture_metrics,
    get_hostname,
    get_platform_info,
    get_cpu_metrics,
    get_memory_metrics,
    get_disk_metrics,
    get_top_processes,
    MetricsSnapshot,
    ProcessInfo,
    is_psutil_available,
    PSUTIL_AVAILABLE,
)


class TestMetricsSnapshot:
    """Tests for MetricsSnapshot dataclass."""
    
    def test_snapshot_has_required_fields(self):
        """Test MetricsSnapshot has all required fields."""
        snapshot = capture_metrics()
        
        assert hasattr(snapshot, 'timestamp_utc')
        assert hasattr(snapshot, 'hostname')
        assert hasattr(snapshot, 'platform')
        assert hasattr(snapshot, 'cpu')
        assert hasattr(snapshot, 'memory')
        assert hasattr(snapshot, 'disk')
        assert hasattr(snapshot, 'top_processes')
        assert hasattr(snapshot, 'warnings')
        assert hasattr(snapshot, 'psutil_available')
    
    def test_snapshot_to_dict(self):
        """Test snapshot serialization to dict."""
        snapshot = capture_metrics()
        d = snapshot.to_dict()
        
        assert isinstance(d, dict)
        assert 'timestamp_utc' in d
        assert 'hostname' in d
        assert 'platform' in d
        assert 'cpu' in d
        assert 'memory' in d
        assert 'disk' in d


class TestHostname:
    """Tests for hostname retrieval."""
    
    def test_get_hostname_returns_string(self):
        """Test hostname is returned as string."""
        hostname = get_hostname()
        assert isinstance(hostname, str)
        assert len(hostname) > 0
    
    def test_get_hostname_fallback(self):
        """Test hostname fallback on error."""
        with patch('socket.gethostname', side_effect=Exception("Network error")):
            hostname = get_hostname()
            assert hostname == "unknown"


class TestPlatformInfo:
    """Tests for platform information."""
    
    def test_platform_info_has_system(self):
        """Test platform info contains system."""
        info = get_platform_info()
        assert 'system' in info
        assert isinstance(info['system'], str)
    
    def test_platform_info_has_release(self):
        """Test platform info contains release."""
        info = get_platform_info()
        assert 'release' in info
    
    def test_platform_info_has_machine(self):
        """Test platform info contains machine type."""
        info = get_platform_info()
        assert 'machine' in info


class TestCpuMetrics:
    """Tests for CPU metrics collection."""
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_cpu_metrics_has_cores(self):
        """Test CPU metrics includes core counts."""
        metrics, warnings = get_cpu_metrics()
        
        assert 'logical_cores' in metrics
        assert metrics['logical_cores'] > 0
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_cpu_metrics_has_percent(self):
        """Test CPU metrics includes percentage."""
        metrics, warnings = get_cpu_metrics()
        
        assert 'cpu_percent_total' in metrics
        assert isinstance(metrics['cpu_percent_total'], (int, float))
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_cpu_metrics_has_load_avg(self):
        """Test CPU metrics includes load average on Linux."""
        metrics, warnings = get_cpu_metrics()
        
        # Load average should be present on Linux
        if 'load_avg' in metrics:
            assert '1min' in metrics['load_avg']
            assert '5min' in metrics['load_avg']
            assert '15min' in metrics['load_avg']


class TestMemoryMetrics:
    """Tests for memory metrics collection."""
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_memory_metrics_has_total(self):
        """Test memory metrics includes total bytes."""
        metrics, warnings = get_memory_metrics()
        
        assert 'total_bytes' in metrics
        assert metrics['total_bytes'] > 0
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_memory_metrics_has_available(self):
        """Test memory metrics includes available bytes."""
        metrics, warnings = get_memory_metrics()
        
        assert 'available_bytes' in metrics
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_memory_metrics_has_percent(self):
        """Test memory metrics includes usage percent."""
        metrics, warnings = get_memory_metrics()
        
        assert 'percent' in metrics
        assert 0 <= metrics['percent'] <= 100


class TestDiskMetrics:
    """Tests for disk metrics collection."""
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_disk_metrics_root_filesystem(self):
        """Test disk metrics for root filesystem."""
        metrics, warnings = get_disk_metrics("/")
        
        assert 'total_bytes' in metrics
        assert 'used_bytes' in metrics
        assert 'free_bytes' in metrics
        assert 'percent' in metrics
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_disk_metrics_path_included(self):
        """Test disk metrics includes path."""
        metrics, warnings = get_disk_metrics("/")
        
        assert 'path' in metrics
        assert metrics['path'] == "/"


class TestTopProcesses:
    """Tests for top processes collection."""
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_top_processes_returns_list(self):
        """Test top processes returns a list."""
        processes, warnings = get_top_processes(limit=5)
        
        assert isinstance(processes, list)
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_top_processes_respects_limit(self):
        """Test top processes respects limit."""
        processes, warnings = get_top_processes(limit=3)
        
        assert len(processes) <= 3
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
    def test_top_processes_has_required_fields(self):
        """Test each process has required fields."""
        processes, warnings = get_top_processes(limit=5)
        
        if processes:  # May be empty if no processes accessible
            proc = processes[0]
            assert 'pid' in proc
            assert 'name' in proc
            assert 'cpu_percent' in proc
            assert 'memory_rss_bytes' in proc


class TestCaptureMetrics:
    """Tests for full metrics capture."""
    
    def test_capture_metrics_returns_snapshot(self):
        """Test capture_metrics returns MetricsSnapshot."""
        snapshot = capture_metrics()
        
        assert isinstance(snapshot, MetricsSnapshot)
    
    def test_capture_metrics_has_timestamp(self):
        """Test snapshot has UTC timestamp."""
        snapshot = capture_metrics()
        
        assert snapshot.timestamp_utc is not None
        assert 'T' in snapshot.timestamp_utc  # ISO format
    
    def test_capture_metrics_has_hostname(self):
        """Test snapshot has hostname."""
        snapshot = capture_metrics()
        
        assert snapshot.hostname is not None
        assert len(snapshot.hostname) > 0
    
    def test_capture_metrics_has_platform(self):
        """Test snapshot has platform info."""
        snapshot = capture_metrics()
        
        assert snapshot.platform is not None
        assert 'system' in snapshot.platform


class TestGracefulDegradation:
    """Tests for graceful handling when psutil unavailable."""
    
    def test_is_psutil_available_returns_bool(self):
        """Test is_psutil_available returns boolean."""
        result = is_psutil_available()
        assert isinstance(result, bool)
    
    def test_snapshot_without_psutil(self):
        """Test metrics capture works without psutil (mocked)."""
        with patch('kernicle.services.metrics.PSUTIL_AVAILABLE', False):
            # Re-import to get mocked version
            from kernicle.services import metrics
            original = metrics.PSUTIL_AVAILABLE
            metrics.PSUTIL_AVAILABLE = False
            
            try:
                cpu, warnings = metrics.get_cpu_metrics()
                assert len(warnings) > 0
                assert 'psutil not available' in warnings[0]
            finally:
                metrics.PSUTIL_AVAILABLE = original


class TestProcessInfo:
    """Tests for ProcessInfo dataclass."""
    
    def test_process_info_to_dict(self):
        """Test ProcessInfo serialization."""
        proc = ProcessInfo(
            pid=1234,
            name="test_process",
            username="testuser",
            cpu_percent=5.5,
            memory_rss_bytes=1024000,
        )
        
        d = proc.to_dict()
        assert d['pid'] == 1234
        assert d['name'] == "test_process"
        assert d['username'] == "testuser"
        assert d['cpu_percent'] == 5.5
        assert d['memory_rss_bytes'] == 1024000
