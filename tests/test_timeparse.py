"""
Tests for time range parsing.
"""

from datetime import datetime, timedelta, timezone
import pytest

from kernicle.services.timeparse import parse_range, TimeRange


class TestParseRange:
    """Tests for parse_range function."""
    
    def test_last_5_minutes(self):
        """Test parsing 'last:5m' format."""
        now = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_range("last:5m", now=now)
        
        expected_since = datetime(2025, 12, 30, 11, 55, 0, tzinfo=timezone.utc)
        
        assert isinstance(result, TimeRange)
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-30 11:55:00"
        assert result.range_input == "last:5m"
    
    def test_last_30_minutes(self):
        """Test parsing 'last:30m' format."""
        now = datetime(2025, 12, 30, 14, 30, 0, tzinfo=timezone.utc)
        result = parse_range("last:30m", now=now)
        
        expected_since = datetime(2025, 12, 30, 14, 0, 0, tzinfo=timezone.utc)
        
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-30 14:00:00"
    
    def test_last_2_hours(self):
        """Test parsing 'last:2h' format."""
        now = datetime(2025, 12, 30, 16, 0, 0, tzinfo=timezone.utc)
        result = parse_range("last:2h", now=now)
        
        expected_since = datetime(2025, 12, 30, 14, 0, 0, tzinfo=timezone.utc)
        
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-30 14:00:00"
    
    def test_last_1_day(self):
        """Test parsing 'last:1d' format."""
        now = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_range("last:1d", now=now)
        
        expected_since = datetime(2025, 12, 29, 12, 0, 0, tzinfo=timezone.utc)
        
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-29 12:00:00"
    
    def test_last_30_seconds(self):
        """Test parsing 'last:30s' format."""
        now = datetime(2025, 12, 30, 12, 0, 30, tzinfo=timezone.utc)
        result = parse_range("last:30s", now=now)
        
        expected_since = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-30 12:00:00"
    
    def test_iso_datetime_with_z(self):
        """Test parsing ISO datetime with Z suffix."""
        result = parse_range("2025-12-30T12:00:00Z")
        
        expected_since = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-30 12:00:00"
        assert result.range_input == "2025-12-30T12:00:00Z"
    
    def test_iso_datetime_without_z(self):
        """Test parsing ISO datetime without Z suffix (assumes UTC)."""
        result = parse_range("2025-12-30T12:00:00")
        
        expected_since = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        
        assert result.since_utc == expected_since
        assert result.since_arg == "2025-12-30 12:00:00"
    
    def test_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_range("invalid")
        
        assert "Invalid time range format" in str(exc_info.value)
    
    def test_invalid_relative_format(self):
        """Test that invalid relative format raises ValueError."""
        with pytest.raises(ValueError):
            parse_range("last:5x")  # 'x' is not a valid unit
    
    def test_case_insensitive_units(self):
        """Test that unit letters are case-insensitive."""
        now = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        
        result_lower = parse_range("last:5m", now=now)
        result_upper = parse_range("last:5M", now=now)
        
        assert result_lower.since_utc == result_upper.since_utc
    
    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled."""
        now = datetime(2025, 12, 30, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_range("  last:5m  ", now=now)
        
        expected_since = datetime(2025, 12, 30, 11, 55, 0, tzinfo=timezone.utc)
        assert result.since_utc == expected_since
