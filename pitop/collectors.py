"""System data collection module.

All psutil interaction is isolated here. The rest of the application
works with typed dataclasses instead of raw psutil objects.
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_percent: float


@dataclass(slots=True)
class NetworkStats:
    bytes_sent: int
    bytes_recv: int
    sent_rate: float  # KB/s
    recv_rate: float  # KB/s


@dataclass(slots=True)
class DiskInfo:
    mountpoint: str
    device: str
    total: int
    used: int
    free: int
    percent: float


@dataclass(slots=True)
class SystemSnapshot:
    timestamp: datetime.datetime
    cpu_percent: float
    cpu_per_core: list[float]
    cpu_count: int
    memory_percent: float
    memory_used: int
    memory_total: int
    swap_percent: float
    swap_used: int
    swap_total: int
    battery_percent: float | None
    battery_charging: bool | None
    battery_time_left: int | None  # seconds, or None
    disks: list[DiskInfo]
    network: NetworkStats
    uptime: datetime.timedelta
    processes: list[ProcessInfo]
    load_avg: tuple[float, float, float] | None


class SystemCollector:
    """Collects system metrics via psutil.

    Keeps minimal state for computing network rates between ticks.
    """

    def __init__(self) -> None:
        self._prev_net_sent: int = 0
        self._prev_net_recv: int = 0
        self._net_initialized: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(
        self,
        sort_key: str = "cpu_percent",
        sort_reverse: bool = True,
        process_filter: str = "",
        max_processes: int = 50,
        include_processes: bool = True,
    ) -> SystemSnapshot:
        """Return a full system snapshot."""

        now = datetime.datetime.now()

        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu_count = psutil.cpu_count() or 1

        # Memory
        mem = psutil.virtual_memory()
        try:
            swap = psutil.swap_memory()
            swap_percent, swap_used, swap_total = swap.percent, swap.used, swap.total
        except Exception:
            swap_percent = swap_used = swap_total = 0

        # Battery (may not exist)
        battery_percent: float | None = None
        battery_charging: bool | None = None
        battery_time: int | None = None
        try:
            bat = psutil.sensors_battery()
            if bat is not None:
                battery_percent = bat.percent
                battery_charging = bat.power_plugged
                if bat.secsleft > 0:
                    battery_time = bat.secsleft
        except Exception:
            pass

        # Network
        network = self._collect_network()

        # Disk
        disks = self._collect_disks()

        # Uptime
        boot_time = psutil.boot_time()
        uptime = now - datetime.datetime.fromtimestamp(boot_time)

        # Load average (Unix only)
        load_avg: tuple[float, float, float] | None = None
        if hasattr(os, "getloadavg"):
            try:
                load_avg = os.getloadavg()  # type: ignore[assignment]
            except OSError:
                pass

        # Processes (optionally skipped for performance)
        processes: list[ProcessInfo] = []
        if include_processes:
            processes = self._collect_processes(
                sort_key, sort_reverse, process_filter, max_processes
            )

        return SystemSnapshot(
            timestamp=now,
            cpu_percent=cpu_percent,
            cpu_per_core=cpu_per_core,
            cpu_count=cpu_count,
            memory_percent=mem.percent,
            memory_used=mem.used,
            memory_total=mem.total,
            swap_percent=swap_percent,
            swap_used=swap_used,
            swap_total=swap_total,
            battery_percent=battery_percent,
            battery_charging=battery_charging,
            battery_time_left=battery_time,
            disks=disks,
            network=network,
            uptime=uptime,
            processes=processes,
            load_avg=load_avg,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_network(self) -> NetworkStats:
        net = psutil.net_io_counters()
        if not self._net_initialized:
            self._prev_net_sent = net.bytes_sent
            self._prev_net_recv = net.bytes_recv
            self._net_initialized = True

        sent_rate = max(0.0, (net.bytes_sent - self._prev_net_sent) / 1024)
        recv_rate = max(0.0, (net.bytes_recv - self._prev_net_recv) / 1024)
        self._prev_net_sent = net.bytes_sent
        self._prev_net_recv = net.bytes_recv

        return NetworkStats(
            bytes_sent=net.bytes_sent,
            bytes_recv=net.bytes_recv,
            sent_rate=sent_rate,
            recv_rate=recv_rate,
        )

    @staticmethod
    def _collect_disks() -> list[DiskInfo]:
        disks: list[DiskInfo] = []
        for part in psutil.disk_partitions(all=False):
            try:
                if os.name == "nt" and ("cdrom" in part.opts or part.fstype == ""):
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(
                    DiskInfo(
                        mountpoint=part.mountpoint,
                        device=part.device,
                        total=usage.total,
                        used=usage.used,
                        free=usage.free,
                        percent=usage.percent,
                    )
                )
            except (PermissionError, OSError):
                pass
        return disks

    @staticmethod
    def _collect_processes(
        sort_key: str,
        sort_reverse: bool,
        process_filter: str,
        max_processes: int,
    ) -> list[ProcessInfo]:
        raw: list[ProcessInfo] = []
        attrs = ["pid", "name", "cpu_percent", "memory_percent", "username"]
        for proc in psutil.process_iter(attrs):
            try:
                info = proc.info
                name = info["name"] or ""
                if process_filter and process_filter.lower() not in name.lower():
                    continue
                raw.append(
                    ProcessInfo(
                        pid=info["pid"],
                        name=name,
                        username=(info["username"] or "")[:20],
                        cpu_percent=info["cpu_percent"] or 0.0,
                        memory_percent=info["memory_percent"] or 0.0,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        raw.sort(key=lambda p: getattr(p, sort_key, 0), reverse=sort_reverse)
        return raw[:max_processes]
