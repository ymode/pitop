import pytest
from pitop import main
from pitop.collectors import SystemCollector


def test_application_starts():
    assert main(testing=True) is True


def test_collector_snapshot():
    collector = SystemCollector()
    snap = collector.collect()
    assert 0 <= snap.cpu_percent <= 100
    assert snap.memory_percent > 0
    assert snap.cpu_count > 0
    assert len(snap.cpu_per_core) == snap.cpu_count
    assert snap.memory_total > 0


def test_collector_processes():
    collector = SystemCollector()
    snap = collector.collect(max_processes=5)
    assert len(snap.processes) <= 5


def test_collector_filter():
    collector = SystemCollector()
    snap = collector.collect(process_filter="nonexistent_process_xyz_123")
    assert isinstance(snap.processes, list)


def test_collector_sort_keys():
    collector = SystemCollector()
    for key in ("cpu_percent", "memory_percent", "pid"):
        snap = collector.collect(sort_key=key, max_processes=5)
        assert isinstance(snap.processes, list)
