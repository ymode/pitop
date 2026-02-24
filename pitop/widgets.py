"""Custom adaptive urwid widgets for pitop.

Every widget computes its visual content inside ``render()`` using the
``maxcol`` value provided by urwid.  This means the entire UI
automatically adapts when the terminal is resized -- no manual
SIGWINCH handling required.
"""

from __future__ import annotations

import urwid


# ======================================================================
# AdaptiveBar -- a progress bar that fills the available width
# ======================================================================

class AdaptiveBar(urwid.Widget):
    """A single-line progress bar whose width tracks the terminal."""

    _selectable = False
    _sizing = frozenset([urwid.FLOW])

    def __init__(self, label: str = "", percent: float = 0.0) -> None:
        super().__init__()
        self._label = label
        self._percent = 0.0
        self._suffix = ""
        self.set_data(percent)

    def set_data(self, percent: float, suffix: str = "") -> None:
        self._percent = max(0.0, min(100.0, percent))
        self._suffix = suffix
        self._invalidate()

    def rows(self, size: tuple[int], focus: bool = False) -> int:
        return 1

    def render(self, size: tuple[int], focus: bool = False) -> urwid.Canvas:
        maxcol = size[0]
        pct = self._percent
        label = self._label
        suffix = self._suffix

        # Layout:  " LBL [██░░] XX.X% suffix "
        suffix_len = len(suffix) + 1 if suffix else 0
        overhead = len(label) + 11 + suffix_len  # spaces + brackets + pct
        bar_width = max(4, maxcol - overhead)

        filled_f = bar_width * pct / 100.0
        filled = int(filled_f)
        empty = bar_width - filled

        color = "critical" if pct >= 90 else "warning" if pct >= 70 else "normal"

        markup: list = [
            ("bold", f" {label} "),
            ("dim", "["),
            (color, "\u2588" * filled),
            ("dim", "\u2591" * empty),
            ("dim", "]"),
            ("normal", f" {pct:5.1f}%"),
        ]
        if suffix:
            markup.append(("dim", f" {suffix}"))

        text = urwid.Text(markup, wrap="clip")
        return text.render(size, focus)


# ======================================================================
# SparklineGraph -- multi-row block-character sparkline
# ======================================================================

class SparklineGraph(urwid.Widget):
    """Multi-line sparkline graph that adapts to terminal width.

    Uses Unicode block characters (``\u2581`` .. ``\u2588``) to draw a
    graph with *height* rows.  Each row covers ``100 / height`` percent
    of the value range.
    """

    _selectable = False
    _sizing = frozenset([urwid.FLOW])

    BLOCKS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

    def __init__(self, label: str = "", height: int = 3) -> None:
        super().__init__()
        self._label = label
        self._values: list[float] = []
        self._height = max(1, height)

    def set_data(self, values: list[float]) -> None:
        self._values = list(values)
        self._invalidate()

    def rows(self, size: tuple[int], focus: bool = False) -> int:
        return self._height

    def render(self, size: tuple[int], focus: bool = False) -> urwid.Canvas:
        maxcol = size[0]
        label_width = len(self._label) + 2
        value_width = 8  # " XX.X% "
        graph_width = max(4, maxcol - label_width - value_width)

        # Pad or truncate values to fit the graph area
        values = list(self._values)
        if len(values) < graph_width:
            values = [0.0] * (graph_width - len(values)) + values
        else:
            values = values[-graph_width:]

        max_val = 100.0
        height = self._height
        row_range = max_val / height

        canvases: list[tuple] = []
        for row in range(height):
            row_from_bottom = height - 1 - row
            row_bottom = row_from_bottom * row_range

            line: list = []

            # Label on the first row, padding on others
            if row == 0:
                line.append(("bold", f" {self._label} "))
            else:
                line.append(("body", " " * label_width))

            # Graph characters
            for val in values:
                color = (
                    "critical" if val >= 90
                    else "warning" if val >= 70
                    else "normal"
                )
                if val >= row_bottom + row_range:
                    line.append((color, "\u2588"))
                elif val > row_bottom:
                    frac = (val - row_bottom) / row_range
                    idx = max(1, min(8, int(frac * 8)))
                    line.append((color, self.BLOCKS[idx]))
                else:
                    line.append(("body", " "))

            # Current value on first row
            if row == 0 and self._values:
                current = self._values[-1]
                line.append(("normal", f" {current:5.1f}%"))
            else:
                line.append(("body", " " * value_width))

            text = urwid.Text(line, wrap="clip")
            canvases.append((text.render(size, focus), None, False))

        return urwid.CanvasCombine(canvases)


# ======================================================================
# CoreMiniBar -- one character per CPU core
# ======================================================================

class CoreMiniBar(urwid.Widget):
    """Compact per-core CPU visualisation in a single line.

    Each core is represented by a single block character whose height
    indicates load, colour-coded green / yellow / red.
    """

    _selectable = False
    _sizing = frozenset([urwid.FLOW])

    BLOCKS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

    def __init__(self) -> None:
        super().__init__()
        self._percents: list[float] = []

    def set_data(self, percents: list[float]) -> None:
        self._percents = list(percents)
        self._invalidate()

    def rows(self, size: tuple[int], focus: bool = False) -> int:
        return 1 if self._percents else 0

    def render(self, size: tuple[int], focus: bool = False) -> urwid.Canvas:
        maxcol = size[0]
        markup: list = [("bold", " Cores ")]

        # Fit as many cores as the terminal allows
        overhead = 20  # label + avg display
        available = max(0, maxcol - overhead)
        show = min(len(self._percents), available)

        for i in range(show):
            pct = self._percents[i]
            color = "critical" if pct >= 90 else "warning" if pct >= 70 else "normal"
            idx = min(7, int(pct / 100.0 * 8))
            markup.append((color, self.BLOCKS[idx]))

        if show < len(self._percents):
            markup.append(("dim", f" +{len(self._percents) - show}"))

        if self._percents:
            avg = sum(self._percents) / len(self._percents)
            markup.append(("dim", f"  avg {avg:.0f}%"))

        text = urwid.Text(markup, wrap="clip")
        return text.render(size, focus)


# ======================================================================
# StatusLine -- labelled values separated by a pipe
# ======================================================================

class StatusLine(urwid.Widget):
    """Adaptive status bar: ``Label value | Label value | ...``"""

    _selectable = False
    _sizing = frozenset([urwid.FLOW])

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[tuple[str, str, str]] = []

    def set_data(self, parts: list[tuple[str, str, str]]) -> None:
        """*parts* is a list of ``(label, value, palette_name)`` tuples."""
        self._parts = list(parts)
        self._invalidate()

    def rows(self, size: tuple[int], focus: bool = False) -> int:
        return 1

    def render(self, size: tuple[int], focus: bool = False) -> urwid.Canvas:
        markup: list = [("body", " ")]
        for i, (label, value, color) in enumerate(self._parts):
            if i > 0:
                markup.append(("dim", " \u2502 "))
            markup.append(("bold", f"{label} "))
            markup.append((color, value))

        text = urwid.Text(markup, wrap="clip")
        return text.render(size, focus)


# ======================================================================
# ProcessRow -- a selectable row in the process table
# ======================================================================

class ProcessRow(urwid.WidgetWrap):
    """Selectable process row using weighted columns for adaptivity."""

    def __init__(self, proc) -> None:
        self.proc_info = proc
        self.pid = proc.pid

        cpu_color = (
            "critical" if proc.cpu_percent >= 90
            else "warning" if proc.cpu_percent >= 50
            else "process"
        )
        mem_color = (
            "critical" if proc.memory_percent >= 90
            else "warning" if proc.memory_percent >= 50
            else "process"
        )

        cols = urwid.Columns(
            [
                ("weight", 3, urwid.Text(("process", f" {proc.name}"))),
                ("weight", 2, urwid.Text(("process", proc.username))),
                ("fixed", 8, urwid.Text(("process", str(proc.pid)))),
                ("fixed", 8, urwid.Text((cpu_color, f"{proc.cpu_percent:5.1f}%"))),
                ("fixed", 8, urwid.Text((mem_color, f"{proc.memory_percent:5.1f}%"))),
            ]
        )
        super().__init__(urwid.AttrMap(cols, "process", focus_map="highlighted"))

    def selectable(self) -> bool:
        return True

    def keypress(self, size: tuple[int], key: str) -> str:
        return key
