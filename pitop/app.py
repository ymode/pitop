"""Main pitop TUI application.

All mutable state lives inside ``PitopApp`` -- there are no module-level
globals.  The ``main()`` entry point parses CLI arguments and either
starts the TUI or the web server.
"""

from __future__ import annotations

import argparse
import logging

import psutil
import urwid

from .collectors import SystemCollector
from .theme import DisplayConfig, load_config
from .widgets import (
    AdaptiveBar,
    CoreMiniBar,
    ProcessRow,
    SparklineGraph,
    StatusLine,
)

logger = logging.getLogger(__name__)


class PitopApp:
    """Encapsulates the entire TUI lifecycle."""

    def __init__(
        self,
        palette: list[tuple[str, str, str]],
        display: DisplayConfig,
    ) -> None:
        self.palette = palette
        self.cfg = display
        self.collector = SystemCollector()

        # History buffers
        self.cpu_history: list[float] = []
        self.memory_history: list[float] = []

        # Process state
        self.sort_key: str = "cpu_percent"
        self.sort_reverse: bool = True
        self.process_filter: str = ""
        self.filter_mode: bool = False

        # Update tick counter (used to throttle process refresh)
        self._tick: int = 0

        self._build_widgets()
        self._build_layout()

    # ==================================================================
    # Widget creation
    # ==================================================================

    def _build_widgets(self) -> None:
        # Header
        self.header_title = urwid.Text(("header", " pitop "))
        self.header_time = urwid.Text(("header", ""), align="right")
        self.header = urwid.AttrMap(
            urwid.Columns([self.header_title, self.header_time]),
            "header",
        )

        # System resource bars
        self.cpu_bar = AdaptiveBar("CPU", 0)
        self.mem_bar = AdaptiveBar("MEM", 0)
        self.swp_bar = AdaptiveBar("SWP", 0)

        # Per-core display
        self.core_bars = CoreMiniBar()

        # Sparkline graphs
        self.cpu_graph = SparklineGraph("CPU", height=self.cfg.graph_height)
        self.mem_graph = SparklineGraph("MEM", height=self.cfg.graph_height)

        # Status line (uptime, battery, network, load)
        self.status_line = StatusLine()

        # Disk
        self.disk_text = urwid.Text("")

        # Process table header (mutable text widgets for sort indicators)
        self._proc_name_w = urwid.Text(("bold", " NAME"))
        self._proc_user_w = urwid.Text(("bold", "USER"))
        self._proc_pid_w = urwid.Text(("bold", "PID"))
        self._proc_cpu_w = urwid.Text(("bold", "CPU%"))
        self._proc_mem_w = urwid.Text(("bold", "MEM%"))
        self.proc_header = urwid.AttrMap(
            urwid.Columns(
                [
                    ("weight", 3, self._proc_name_w),
                    ("weight", 2, self._proc_user_w),
                    ("fixed", 8, self._proc_pid_w),
                    ("fixed", 8, self._proc_cpu_w),
                    ("fixed", 8, self._proc_mem_w),
                ]
            ),
            "header",
        )
        self._update_sort_indicators()

        # Process list
        self.process_walker = urwid.SimpleFocusListWalker([])
        self.process_listbox = urwid.ListBox(self.process_walker)

        # Footer
        self.footer = urwid.AttrMap(
            urwid.Text(
                [
                    ("key", " q "), ("key_label", "Quit "),
                    ("key", " k "), ("key_label", "Kill "),
                    ("key", " c "), ("key_label", "CPU "),
                    ("key", " m "), ("key_label", "Mem "),
                    ("key", " p "), ("key_label", "PID "),
                    ("key", " / "), ("key_label", "Filter "),
                    ("key", " esc "), ("key_label", "Clear "),
                ],
                align="center",
            ),
            "footer",
        )

        # Filter dialog
        self.filter_edit = urwid.Edit(("filter_edit", " Filter: "), "")
        urwid.connect_signal(self.filter_edit, "change", self._on_filter_change)

    def _update_sort_indicators(self) -> None:
        arrow = "\u25bc" if self.sort_reverse else "\u25b2"

        def _label(field: str, text: str) -> tuple[str, str]:
            if self.sort_key == field:
                return ("sort_active", f"{text}{arrow}")
            return ("bold", text)

        self._proc_pid_w.set_text(_label("pid", "PID"))
        self._proc_cpu_w.set_text(_label("cpu_percent", "CPU%"))
        self._proc_mem_w.set_text(_label("memory_percent", "MEM%"))

    # ==================================================================
    # Layout
    # ==================================================================

    def _build_layout(self) -> None:
        div = urwid.AttrMap(urwid.Divider("\u2500"), "dim")

        self.body = urwid.Pile(
            [
                ("pack", self.header),
                ("pack", div),
                ("pack", self.cpu_bar),
                ("pack", self.mem_bar),
                ("pack", self.swp_bar),
                ("pack", self.core_bars),
                ("pack", urwid.AttrMap(urwid.Divider("\u2500"), "dim")),
                ("pack", self.cpu_graph),
                ("pack", self.mem_graph),
                ("pack", urwid.AttrMap(urwid.Divider("\u2500"), "dim")),
                ("pack", self.status_line),
                ("pack", self.disk_text),
                ("pack", urwid.AttrMap(urwid.Divider("\u2500"), "dim")),
                ("pack", self.proc_header),
                ("weight", 1, urwid.AttrMap(self.process_listbox, "body")),
            ]
        )

        self.frame = urwid.Frame(
            urwid.AttrMap(self.body, "body"),
            footer=self.footer,
        )

        # Filter overlay (centred popup)
        filter_box = urwid.AttrMap(
            urwid.LineBox(
                urwid.Padding(self.filter_edit, left=1, right=1),
                title="Filter Processes",
            ),
            "popup",
        )
        self.filter_overlay = urwid.Overlay(
            filter_box,
            self.frame,
            "center", ("relative", 40),
            "middle", 3,
        )

    # ==================================================================
    # Data formatting helpers
    # ==================================================================

    @staticmethod
    def _fmt_rate(kb_per_sec: float) -> str:
        if kb_per_sec >= 1024:
            return f"{kb_per_sec / 1024:.1f} MB/s"
        return f"{kb_per_sec:.1f} KB/s"

    @staticmethod
    def _fmt_bytes(nbytes: int) -> str:
        for unit in ("B", "K", "M", "G", "T"):
            if abs(nbytes) < 1024:
                return f"{nbytes:.1f}{unit}"
            nbytes /= 1024  # type: ignore[assignment]
        return f"{nbytes:.1f}P"

    @staticmethod
    def _fmt_uptime(td) -> str:
        total = int(td.total_seconds())
        days = total // 86400
        hours = (total % 86400) // 3600
        mins = (total % 3600) // 60
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        return " ".join(parts)

    # ==================================================================
    # Update loop
    # ==================================================================

    def update(self, loop: urwid.MainLoop, _user_data: object = None) -> None:
        """Collect fresh metrics and push them into the widgets."""

        self._tick += 1
        include_procs = (self._tick % self.cfg.process_update_interval == 0)

        try:
            snap = self.collector.collect(
                sort_key=self.sort_key,
                sort_reverse=self.sort_reverse,
                process_filter=self.process_filter,
                max_processes=self.cfg.max_processes,
                include_processes=include_procs,
            )

            # Header
            self.header_time.set_text(
                ("header", snap.timestamp.strftime(" %Y-%m-%d %H:%M:%S "))
            )

            # Bars with memory size suffix
            mem_total_g = snap.memory_total / (1024 ** 3)
            mem_used_g = snap.memory_used / (1024 ** 3)
            swp_total_g = snap.swap_total / (1024 ** 3)
            swp_used_g = snap.swap_used / (1024 ** 3)

            self.cpu_bar.set_data(snap.cpu_percent)
            self.mem_bar.set_data(
                snap.memory_percent,
                suffix=f"{mem_used_g:.1f}G / {mem_total_g:.1f}G",
            )
            self.swp_bar.set_data(
                snap.swap_percent,
                suffix=f"{swp_used_g:.1f}G / {swp_total_g:.1f}G",
            )

            # Per-core
            self.core_bars.set_data(snap.cpu_per_core)

            # History + graphs
            self.cpu_history.append(snap.cpu_percent)
            self.memory_history.append(snap.memory_percent)
            max_h = self.cfg.max_history
            if len(self.cpu_history) > max_h:
                self.cpu_history = self.cpu_history[-max_h:]
            if len(self.memory_history) > max_h:
                self.memory_history = self.memory_history[-max_h:]

            self.cpu_graph.set_data(self.cpu_history)
            self.mem_graph.set_data(self.memory_history)

            # Status line
            parts: list[tuple[str, str, str]] = []
            parts.append(("Up", self._fmt_uptime(snap.uptime), "normal"))

            if snap.load_avg is not None:
                la = snap.load_avg
                parts.append((
                    "Load",
                    f"{la[0]:.2f} {la[1]:.2f} {la[2]:.2f}",
                    "warning" if la[0] > snap.cpu_count else "normal",
                ))

            if snap.battery_percent is not None:
                icon = "AC" if snap.battery_charging else "BAT"
                bcolor = "normal" if snap.battery_percent > 30 else "critical"
                btext = f"{icon} {snap.battery_percent:.0f}%"
                if snap.battery_time_left:
                    h = snap.battery_time_left // 3600
                    m = (snap.battery_time_left % 3600) // 60
                    btext += f" ({h}:{m:02d})"
                parts.append(("Bat", btext, bcolor))

            net_color = (
                "warning"
                if snap.network.sent_rate > 1024 or snap.network.recv_rate > 1024
                else "normal"
            )
            parts.append((
                "Net",
                f"\u2191{self._fmt_rate(snap.network.sent_rate)} "
                f"\u2193{self._fmt_rate(snap.network.recv_rate)}",
                net_color,
            ))

            self.status_line.set_data(parts)

            # Disk
            disk_markup: list = [("body", " ")]
            for d in snap.disks:
                tg = d.total / (1024 ** 3)
                ug = d.used / (1024 ** 3)
                dc = (
                    "critical" if d.percent >= 90
                    else "warning" if d.percent >= 80
                    else "disk"
                )
                disk_markup.extend([
                    ("bold", "Disk "),
                    ("dim", f"{d.mountpoint} "),
                    (dc, f"{ug:.0f}G/{tg:.0f}G ({d.percent:.0f}%)"),
                    ("body", "  "),
                ])
            self.disk_text.set_text(disk_markup)

            # Process list
            if include_procs:
                rows = [ProcessRow(p) for p in snap.processes]
                self.process_walker[:] = rows

        except Exception:
            logger.error("Update error", exc_info=True)

        loop.set_alarm_in(self.cfg.update_interval, self.update)

    # ==================================================================
    # Input handling
    # ==================================================================

    def handle_input(self, key: str) -> bool | None:
        # ---- filter mode -------------------------------------------------
        if self.filter_mode:
            if key in ("esc", "enter"):
                self.filter_mode = False
                if key == "esc":
                    self.process_filter = ""
                    self.filter_edit.set_edit_text("")
                self.loop.widget = self.frame
                return True
            return None  # let Edit handle it

        # ---- normal mode -------------------------------------------------
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()

        if key in ("k", "K"):
            self._kill_selected()
            return True

        if key in ("c", "C"):
            self._toggle_sort("cpu_percent")
            return True

        if key in ("m", "M"):
            self._toggle_sort("memory_percent")
            return True

        if key in ("p", "P"):
            self._toggle_sort("pid")
            return True

        if key in ("/", "?"):
            self.filter_mode = True
            self.filter_edit.set_edit_text(self.process_filter)
            self.filter_edit.set_edit_pos(len(self.process_filter))
            self.loop.widget = self.filter_overlay
            return True

        if key == "esc":
            self.process_filter = ""
            self.filter_edit.set_edit_text("")
            return True

        return None

    def _toggle_sort(self, field: str) -> None:
        if self.sort_key == field:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = field
            self.sort_reverse = True
        self._update_sort_indicators()

    def _on_filter_change(self, _edit: urwid.Edit, new_text: str) -> None:
        self.process_filter = new_text

    def _kill_selected(self) -> None:
        focus = self.process_listbox.focus
        if focus is None or not hasattr(focus, "pid"):
            return
        pid = focus.pid
        try:
            psutil.Process(pid).terminate()
            logger.info("Terminated PID %d", pid)
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            logger.warning("Access denied killing PID %d", pid)

    # ==================================================================
    # Entry point
    # ==================================================================

    def run(self) -> None:
        self.loop = urwid.MainLoop(
            self.frame,
            palette=self.palette,
            unhandled_input=self.handle_input,
        )

        # Kick off the first update almost immediately
        self.loop.set_alarm_in(0.1, self.update)

        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass


# ======================================================================
# CLI entry point
# ======================================================================

def main(testing: bool = False) -> bool | None:
    """Entry point for ``pitop`` console script and ``python -m pitop``."""

    if testing:
        return True

    parser = argparse.ArgumentParser(
        prog="pitop",
        description="pitop - a terminal system monitor",
    )
    parser.add_argument(
        "--web", action="store_true", help="start the web dashboard instead of the TUI"
    )
    parser.add_argument(
        "--debug", action="store_true", help="write debug log to pitop_debug.log"
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            filename="pitop_debug.log",
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.web:
        from .web_server import run_server
        run_server()
        return None

    palette, display = load_config()
    app = PitopApp(palette, display)
    app.run()
    return None
