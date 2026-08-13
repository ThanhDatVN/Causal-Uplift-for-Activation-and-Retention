"""Test cho resource gate kiểm tra liên tục trong lúc chạy.

Trước Sprint 3, gate chỉ được kiểm tra một lần trước khi chạy. Ở các stage
full-data, RAM khả dụng đã tụt xuống 1,55 GB — dưới ngưỡng 2,0 GB đã đăng ký —
mà không có gì dừng lại. Các test dưới đây khóa hành vi mới.
"""

import time

import pytest

from src.experiment import ResourceGateBreached, ResourceMonitor


def test_monitor_without_threshold_never_breaches():
    """Không đặt ngưỡng thì monitor chỉ đo, không bao giờ chặn."""
    with ResourceMonitor(interval_seconds=0.01) as monitor:
        time.sleep(0.05)
    assert monitor.breached is False
    monitor.raise_if_breached()  # không được raise
    assert monitor.peak_process_rss_gb > 0


def test_monitor_records_peak_and_minimum():
    with ResourceMonitor(interval_seconds=0.01) as monitor:
        time.sleep(0.05)
    assert monitor.peak_process_rss_gb > 0
    assert monitor.min_system_available_ram_gb > 0


def test_breach_is_flagged_when_threshold_is_unreachable():
    """Ngưỡng đặt cao vô lý thì cờ phải bật ngay ở lần lấy mẫu đầu tiên."""
    with ResourceMonitor(interval_seconds=0.01, min_available_gb=10**6) as monitor:
        time.sleep(0.1)
    assert monitor.breached is True
    assert monitor.breach_available_gb is not None
    assert monitor.breach_utc is not None


def test_raise_if_breached_reports_the_numbers_and_the_remedy():
    with ResourceMonitor(interval_seconds=0.01, min_available_gb=10**6) as monitor:
        time.sleep(0.1)
    with pytest.raises(ResourceGateBreached) as error:
        monitor.raise_if_breached("candidate X fold 2")
    message = str(error.value)
    assert "candidate X fold 2" in message
    assert "pool-frac" in message
    assert str(10**6) in message or "1000000" in message


def test_breach_flag_is_sticky():
    """Một lần vi phạm là vi phạm; không được tự xoá khi RAM hồi lại."""
    monitor = ResourceMonitor(interval_seconds=0.01, min_available_gb=10**6)
    with monitor:
        time.sleep(0.05)
    assert monitor.breached is True
    monitor.min_available_gb = 0.0  # dù ngưỡng có đổi
    assert monitor.breached is True
    with pytest.raises(ResourceGateBreached):
        monitor.raise_if_breached()


def test_threshold_of_zero_never_breaches():
    with ResourceMonitor(interval_seconds=0.01, min_available_gb=0.0) as monitor:
        time.sleep(0.05)
    assert monitor.breached is False


def test_memory_percent_threshold_is_enforced():
    with ResourceMonitor(
        interval_seconds=0.01,
        max_system_memory_percent=0.0,
    ) as monitor:
        time.sleep(0.05)
    assert monitor.breached is True
    assert monitor.breach_memory_percent is not None
    assert monitor.max_system_memory_percent > 0
