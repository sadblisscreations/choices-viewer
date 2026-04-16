"""Books tab — visual branching story graph."""

from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QScrollArea, QSizePolicy, QSplitter, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from ..assets import discover_books
from ..parsers.protobuf_parser import build_story


# ---------------------------------------------------------------------------
# Theme colours (matching dark Win98 bevels)
# ---------------------------------------------------------------------------
BG       = QColor("#2b2b2b")
FG       = QColor("#e0e0e0")
SHADOW   = QColor("#0a0a0a")
LIGHT    = QColor("#5c5c5c")
MID      = QColor("#3d3d3d")
ACCENT   = QColor("#4a9eff")
DIALOG_BORDER = QColor("#6b8c42")   # muted green for dialog
CHOICE_BORDER = QColor("#c9a227")   # amber for choices
BREAK_BORDER  = QColor("#8c4a4a")   # muted red for breaks


# ---------------------------------------------------------------------------
# Story graph canvas
# ---------------------------------------------------------------------------
class StoryGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self._boxes = []      # list of dicts with keys: rect, kind, text, subtext
        self._lines = []      # list of (QPoint, QPoint)
        self._pixmap = None   # cached render of the graph
        self._fm = QFontMetrics(self.font())
        self.setMinimumSize(400, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_events(self, events: list):
        self.events = events
        self._layout_graph()
        self._render_to_pixmap()
        self.update()

    def _wrap_text(self, text: str, max_width: int) -> str:
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            if self._fm.horizontalAdvance(test) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return "\n".join(lines) if lines else text

    def _layout_graph(self):
        self._boxes.clear()
        self._lines.clear()

        if not self.events:
            self.setMinimumSize(400, 200)
            return

        MARGIN_X = 80
        MARGIN_Y = 40
        BOX_W = 520
        BOX_MIN_H = 56
        GAP_Y = 48
        OPTION_W = 280
        OPTION_GAP = 32

        y = MARGIN_Y
        row_specs = []   # list of (kind, box_w_list, texts) for width calculation

        # First pass: determine heights and collect widths
        for ev in self.events:
            kind = ev.get("type", "unknown")

            if kind == "dialog":
                speaker = ev.get("speaker", "")
                text = ev.get("text", "")
                emotion = ev.get("emotion", "")

                display = self._wrap_text(text, BOX_W - 36)
                h = max(BOX_MIN_H, display.count("\n") * self._fm.height() + self._fm.height() + 24)
                if speaker:
                    h += self._fm.height() + 4
                if emotion:
                    h += self._fm.height() + 4

                sub = ""
                if speaker and emotion:
                    sub = f"{speaker}  •  {emotion}"
                elif speaker:
                    sub = speaker
                elif emotion:
                    sub = emotion

                row_specs.append({"kind": "dialog", "h": h, "main_w": BOX_W, "opts": [],
                                  "text": display, "subtext": sub})
                y += h + GAP_Y

            elif kind == "choice":
                options = ev.get("options", [])
                header_h = 34
                row_specs.append({"kind": "choice_header", "h": header_h, "main_w": BOX_W, "opts": [],
                                  "text": "CHOICE", "subtext": ""})
                y += header_h + 16

                if options:
                    opt_heights = []
                    opt_texts = []
                    for idx, opt in enumerate(options):
                        ot = self._wrap_text(opt.get("text", ""), OPTION_W - 28)
                        oh = max(40, ot.count("\n") * self._fm.height() + self._fm.height() + 20)
                        opt_texts.append(ot)
                        opt_heights.append(oh)
                    row_specs.append({"kind": "choice_options", "h": max(opt_heights), "main_w": 0,
                                      "opts": opt_texts, "subtext": ""})
                    y += max(opt_heights) + GAP_Y
                else:
                    row_specs.append({"kind": "choice_options", "h": 34, "main_w": 0,
                                      "opts": ["(continue)"], "subtext": ""})
                    y += 34 + GAP_Y

            elif kind == "break":
                row_specs.append({"kind": "break", "h": 34, "main_w": BOX_W, "opts": [],
                                  "text": ev.get("text", "— break —"), "subtext": ""})
                y += 34 + GAP_Y

            else:
                info = ev.get("info", "")
                row_specs.append({"kind": "unknown", "h": 34, "main_w": BOX_W, "opts": [],
                                  "text": info or kind, "subtext": ""})
                y += 34 + GAP_Y

        # Compute required width
        max_content_w = 0
        for row in row_specs:
            if row["kind"] == "choice_options":
                n = len(row["opts"])
                w = n * OPTION_W + (n - 1) * OPTION_GAP
            else:
                w = row["main_w"]
            if w > max_content_w:
                max_content_w = w

        max_w = max_content_w + MARGIN_X * 2
        max_h = y - GAP_Y + MARGIN_Y
        self.setMinimumSize(max_w, max_h)

        center_x = max_w // 2
        y = MARGIN_Y

        # Second pass: place boxes
        i = 0
        while i < len(row_specs):
            row = row_specs[i]
            kind = row["kind"]

            if kind == "choice_options":
                n = len(row["opts"])
                total_w = n * OPTION_W + (n - 1) * OPTION_GAP
                start_x = center_x - total_w // 2
                for idx, ot in enumerate(row["opts"]):
                    ox = start_x + idx * (OPTION_W + OPTION_GAP)
                    oh = max(40, ot.count("\n") * self._fm.height() + self._fm.height() + 20)
                    rect = QRect(ox, y, OPTION_W, oh)
                    self._boxes.append({"rect": rect, "kind": "choice_option", "text": ot, "subtext": ""})
                y += row["h"] + GAP_Y
                i += 1
            else:
                h = row["h"]
                w = row["main_w"]
                rect = QRect(center_x - w // 2, y, w, h)
                self._boxes.append({"rect": rect, "kind": kind, "text": row["text"], "subtext": row["subtext"]})
                y += h + GAP_Y if kind != "choice_header" else h + 16
                i += 1

        # Build lines
        i = 0
        while i < len(self._boxes):
            b = self._boxes[i]
            if b["kind"] == "choice_header":
                j = i + 1
                opts = []
                while j < len(self._boxes) and self._boxes[j]["kind"] == "choice_option":
                    opts.append(j)
                    j += 1
                hb = QPoint(b["rect"].center().x(), b["rect"].bottom())
                for oi in opts:
                    ot = QPoint(self._boxes[oi]["rect"].center().x(), self._boxes[oi]["rect"].top())
                    self._lines.append((hb, ot))
                if opts and j < len(self._boxes):
                    for oi in opts:
                        ob = QPoint(self._boxes[oi]["rect"].center().x(), self._boxes[oi]["rect"].bottom())
                        nt = QPoint(self._boxes[j]["rect"].center().x(), self._boxes[j]["rect"].top())
                        self._lines.append((ob, nt))
                i = j
            else:
                if i + 1 < len(self._boxes) and self._boxes[i + 1]["kind"] != "choice_option":
                    bb = QPoint(b["rect"].center().x(), b["rect"].bottom())
                    nt = QPoint(self._boxes[i + 1]["rect"].center().x(), self._boxes[i + 1]["rect"].top())
                    self._lines.append((bb, nt))
                i += 1

    def _render_to_pixmap(self):
        if not self._boxes:
            self._pixmap = None
            return
        pm = QPixmap(self.width(), self.height())
        pm.fill(BG)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw lines
        pen = QPen(QColor("#555555"))
        pen.setWidth(2)
        painter.setPen(pen)
        for p1, p2 in self._lines:
            painter.drawLine(p1, p2)

        # Draw boxes
        for box in self._boxes:
            rect = box["rect"]
            kind = box["kind"]
            text = box["text"]
            sub = box["subtext"]

            if kind == "dialog":
                border = DIALOG_BORDER
                bg = QColor("#323a2a")
            elif kind == "choice_header":
                border = CHOICE_BORDER
                bg = QColor("#3d362a")
            elif kind == "choice_option":
                border = QColor("#888888")
                bg = QColor("#333333")
            elif kind == "break":
                border = BREAK_BORDER
                bg = QColor("#3d2a2a")
            else:
                border = QColor("#777777")
                bg = QColor("#333333")

            # Fill
            painter.fillRect(rect, bg)

            # Bevel border (dark Win98 style)
            painter.setPen(QPen(LIGHT))
            painter.drawLine(rect.left(), rect.bottom(), rect.left(), rect.top())
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.setPen(QPen(SHADOW))
            painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
            painter.drawLine(rect.right(), rect.bottom(), rect.left(), rect.bottom())

            # Inner accent border
            painter.setPen(QPen(border, 1))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

            # Text
            painter.setPen(QPen(FG))
            if kind == "choice_header":
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            else:
                text_rect = rect.adjusted(10, 8, -10, -8)
                if sub:
                    sub_h = self._fm.height() + 4
                    painter.setPen(QPen(ACCENT))
                    painter.drawText(text_rect.left(), text_rect.top() + self._fm.ascent(), sub)
                    painter.setPen(QPen(FG))
                    body_rect = text_rect.adjusted(0, sub_h, 0, 0)
                    painter.drawText(body_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, text)
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, text)

        painter.end()
        self._pixmap = pm

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._pixmap:
            painter.drawPixmap(event.rect(), self._pixmap, event.rect())
        else:
            painter.fillRect(self.rect(), BG)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_to_pixmap()


# ---------------------------------------------------------------------------
# Books tab
# ---------------------------------------------------------------------------
class BooksTab(QWidget):
    def __init__(self, books: list):
        super().__init__()
        self._books_root = None
        self._books = books

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: book / chapter tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.currentItemChanged.connect(self._on_select)

        # Right: scrollable graph
        self._graph = StoryGraphWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._graph)
        scroll.setStyleSheet("background-color: #2b2b2b; border: none;")

        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(scroll)
        self._splitter.setSizes([260, 1100])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._splitter)

        self._populate_tree()

    def _populate_tree(self):
        self._tree.clear()
        for book_name, chapters in self._books:
            book_item = QTreeWidgetItem(self._tree, [str(book_name)])
            book_item.setExpanded(True)
            for chapter_name, chapter_path in chapters:
                ch_item = QTreeWidgetItem(book_item, [str(chapter_name)])
                ch_item.setData(0, Qt.ItemDataRole.UserRole, str(chapter_path))

    def _on_select(self, current, _previous):
        if current is None:
            return
        path_str = current.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        try:
            events = build_story(Path(path_str))
            self._graph.set_events(events)
        except Exception as exc:
            self._graph.set_events([{"type": "unknown", "info": f"Parse error: {exc}"}])

    def update_books(self, books_root: Path):
        self._books_root = books_root
        self._books = discover_books(books_root)
        self._populate_tree()

    def refresh(self, books_root: Path, books: list):
        self._books_root = books_root
        self._books = books
        self._populate_tree()
