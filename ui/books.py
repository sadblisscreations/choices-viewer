"""Books tab: cover library and readable chapter timeline."""

from pathlib import Path

from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from ..assets import discover_books
from ..parsers.protobuf_parser import build_story


BG = QColor("#2b2b2b")
FG = QColor("#e0e0e0")
SHADOW = QColor("#0a0a0a")
LIGHT = QColor("#5c5c5c")
ACCENT = QColor("#4a9eff")
DIALOG_BORDER = QColor("#6b8c42")
CHOICE_BORDER = QColor("#c9a227")
BREAK_BORDER = QColor("#8c4a4a")


class StoryGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self._boxes = []
        self._pixmap = None
        self._fm = QFontMetrics(self.font())
        self.setMinimumSize(520, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_events(self, events: list):
        self.events = events
        self._layout_graph()
        self._render_to_pixmap()
        self.update()

    def _wrap_text(self, text: str, max_width: int) -> str:
        words = str(text or "").split()
        lines = []
        cur = ""
        for word in words:
            test = f"{cur} {word}".strip()
            if self._fm.horizontalAdvance(test) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return "\n".join(lines) if lines else str(text or "")

    def _layout_graph(self):
        self._boxes.clear()
        if not self.events:
            self.setMinimumSize(520, 240)
            return

        margin_x = 30
        margin_y = 24
        gap_y = 12
        available_w = max(520, self.width() - margin_x * 2)
        card_w = min(920, available_w)
        x = margin_x + max(0, (available_w - card_w) // 2)
        y = margin_y

        for ev in self.events:
            kind = ev.get("type", "unknown")
            if kind == "dialog":
                speaker = ev.get("speaker", "")
                text = self._wrap_text(ev.get("text", ""), card_w - 52)
                sub = speaker
                line_count = max(1, text.count("\n") + 1)
                height = max(64, line_count * self._fm.height() + 32 + (self._fm.height() + 8 if sub else 0))
                self._boxes.append({"rect": QRect(x, y, card_w, height), "kind": "dialog", "text": text, "sub": sub})
                y += height + gap_y
            elif kind == "choice":
                options = [self._wrap_text(opt.get("text", ""), card_w - 84) for opt in ev.get("options", [])] or ["Continue"]
                line_count = sum(max(1, opt.count("\n") + 1) for opt in options)
                height = 50 + line_count * self._fm.height() + len(options) * 18
                self._boxes.append({"rect": QRect(x, y, card_w, height), "kind": "choice", "text": options, "sub": ""})
                y += height + gap_y
            elif kind == "break":
                self._boxes.append({"rect": QRect(x, y, card_w, 34), "kind": "break", "text": "SCENE BREAK", "sub": ""})
                y += 34 + gap_y
            else:
                text = self._wrap_text(ev.get("info", kind), card_w - 40)
                height = max(44, (text.count("\n") + 1) * self._fm.height() + 24)
                self._boxes.append({"rect": QRect(x, y, card_w, height), "kind": "unknown", "text": text, "sub": ""})
                y += height + gap_y

        self.setMinimumSize(card_w + margin_x * 2, y + margin_y)

    def _render_to_pixmap(self):
        if not self._boxes:
            self._pixmap = None
            return

        pm = QPixmap(max(1, self.width()), max(1, self.height()))
        pm.fill(BG)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        line_x = self._boxes[0]["rect"].left() - 14
        painter.setPen(QPen(QColor("#555555"), 2))
        painter.drawLine(line_x, self._boxes[0]["rect"].top(), line_x, self._boxes[-1]["rect"].bottom())

        for box in self._boxes:
            rect = box["rect"]
            kind = box["kind"]
            border, fill = {
                "dialog": (DIALOG_BORDER, QColor("#30362c")),
                "choice": (CHOICE_BORDER, QColor("#3c3427")),
                "break": (BREAK_BORDER, QColor("#3d2a2a")),
            }.get(kind, (QColor("#777777"), QColor("#333333")))

            painter.setPen(QPen(border, 2))
            painter.setBrush(QColor("#2f2f2f"))
            painter.drawEllipse(line_x - 5, rect.top() + 15, 10, 10)

            painter.fillRect(rect, fill)
            painter.setPen(QPen(LIGHT))
            painter.drawLine(rect.left(), rect.bottom(), rect.left(), rect.top())
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.setPen(QPen(SHADOW))
            painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
            painter.drawLine(rect.right(), rect.bottom(), rect.left(), rect.bottom())
            painter.setPen(QPen(border, 1))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

            if kind == "choice":
                inner = rect.adjusted(14, 9, -14, -9)
                painter.setPen(QPen(CHOICE_BORDER))
                painter.drawText(inner.left(), inner.top() + self._fm.ascent(), "CHOICE")
                y = inner.top() + self._fm.height() + 9
                for idx, opt in enumerate(box["text"], 1):
                    opt_h = max(self._fm.height() + 12, (opt.count("\n") + 1) * self._fm.height() + 12)
                    opt_rect = QRect(inner.left() + 8, y, inner.width() - 8, opt_h)
                    painter.fillRect(opt_rect, QColor("#282828"))
                    painter.setPen(QPen(QColor("#6a6a6a")))
                    painter.drawRect(opt_rect)
                    painter.setPen(QPen(FG))
                    painter.drawText(
                        opt_rect.adjusted(8, 5, -8, -5),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                        f"{idx}. {opt}",
                    )
                    y = opt_rect.bottom() + 8
            elif kind == "break":
                painter.setPen(QPen(BREAK_BORDER))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "SCENE BREAK")
            else:
                text_rect = rect.adjusted(12, 9, -12, -9)
                if box.get("sub"):
                    painter.setPen(QPen(ACCENT))
                    painter.drawText(text_rect.left(), text_rect.top() + self._fm.ascent(), box["sub"])
                    text_rect = text_rect.adjusted(0, self._fm.height() + 8, 0, 0)
                painter.setPen(QPen(FG))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, box["text"])

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
        self._layout_graph()
        self._render_to_pixmap()


class BooksTab(QWidget):
    def __init__(self, books: list):
        super().__init__()
        self._books_root = None
        self._books = books
        self._book_cards = []
        self._image_index = None

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left.setMinimumWidth(300)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search books...")
        self._search.textChanged.connect(self._populate_books)
        left_lay.addWidget(self._search)

        self._genre_combo = QComboBox()
        self._genre_combo.currentIndexChanged.connect(self._populate_books)
        left_lay.addWidget(self._genre_combo)

        self._book_list = QListWidget()
        self._book_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._book_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._book_list.setMovement(QListWidget.Movement.Static)
        self._book_list.setSpacing(10)
        self._book_list.setIconSize(QSize(132, 190))
        self._book_list.setUniformItemSizes(True)
        self._book_list.currentItemChanged.connect(self._on_book_select)
        left_lay.addWidget(self._book_list, stretch=1)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(10, 0, 0, 0)
        right_lay.setSpacing(8)

        hero = QWidget()
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(0, 0, 0, 0)
        hero_lay.setSpacing(12)

        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(150, 216)
        self._cover_lbl.setScaledContents(True)
        self._cover_lbl.setStyleSheet("background: #1e1e1e; border: 1px solid #5c5c5c;")
        hero_lay.addWidget(self._cover_lbl)

        meta = QWidget()
        meta_lay = QVBoxLayout(meta)
        meta_lay.setContentsMargins(0, 0, 0, 0)
        meta_lay.setSpacing(6)
        self._title_lbl = QLabel("Select a book")
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #f0f0f0; background: transparent;")
        self._meta_lbl = QLabel("")
        self._meta_lbl.setStyleSheet("font-size: 12px; color: #b8b8b8; background: transparent;")
        self._chapter_list = QListWidget()
        self._chapter_list.setMaximumHeight(140)
        self._chapter_list.setUniformItemSizes(True)
        self._chapter_list.currentItemChanged.connect(self._on_chapter_select)
        meta_lay.addWidget(self._title_lbl)
        meta_lay.addWidget(self._meta_lbl)
        meta_lay.addWidget(self._chapter_list)
        hero_lay.addWidget(meta, stretch=1)
        right_lay.addWidget(hero)

        self._graph = StoryGraphWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._graph)
        scroll.setStyleSheet("background-color: #2b2b2b; border: none;")
        right_lay.addWidget(scroll, stretch=1)

        self._splitter.addWidget(left)
        self._splitter.addWidget(right)
        self._splitter.setSizes([420, 980])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._splitter)

        self._rebuild_cards()
        self._rebuild_genres()
        self._populate_books()

    def _assets_root(self) -> Path | None:
        if self._books_root:
            return self._books_root.parent / "assets"
        for _name, chapters in self._books:
            if chapters:
                return Path(chapters[0][1]).parent.parent.parent / "assets"
        return None

    @staticmethod
    def _book_key(display_name: str, chapters: list) -> str:
        if chapters:
            return Path(chapters[0][1]).parent.name.removeprefix("book_")
        return display_name.lower().replace(" ", "_")

    @staticmethod
    def _pretty_title(book_key: str) -> str:
        parts = book_key.split("_")
        if parts and parts[0] in {"deu", "fra", "spa"}:
            parts = parts[1:]
        if parts and parts[0] == "chat":
            parts = parts[2:]
        elif parts:
            parts = parts[1:]
        if parts and parts[-1].isdigit():
            num = int(parts[-1])
            parts = parts[:-1]
            title = " ".join(parts).title()
            return f"{title}, Book {num}" if num > 1 else title
        return " ".join(parts).title()

    @staticmethod
    def _genre(book_key: str) -> str:
        parts = book_key.split("_")
        lang = ""
        if parts and parts[0] in {"deu", "fra", "spa"}:
            lang = parts.pop(0).upper()
        if len(parts) >= 2 and parts[0] == "chat":
            genre = "Chat " + parts[1].title()
        else:
            genre = parts[0].title() if parts else "Other"
        return f"{lang} {genre}".strip()

    def _candidate_tokens(self, book_key: str) -> list[str]:
        parts = [p for p in book_key.split("_") if p not in {"book", "deu", "fra", "spa", "chat"}]
        if parts and parts[0] in {"adventure", "romance", "horror", "fantasy", "crime", "mystery", "scifi"}:
            parts = parts[1:]
        return [p for p in parts if len(p) > 1]

    def _series_key(self, book_key: str) -> str:
        return self._normalize_card_key("_".join(self._candidate_tokens(book_key)))

    @staticmethod
    def _normalize_card_key(value: str) -> str:
        value = value.lower()
        fixes = {
            "perfect_match_02": "perfect_match_2",
            "rideordie_01": "ride_or_die_01",
            "the_unexpected_heiress_01": "unexpected_heiress_01",
            "the_haunting_of_braidwood_manor_01": "braidwood_manor_01",
            "crimes_of_passion_01": "crimes_of_passion_01",
            "crimes_of_passion_02": "crimes_of_passion_02",
            "crimes_of_passion_03": "crimes_of_passion_03",
        }
        return fixes.get(value, value)

    def _build_image_index(self):
        assets = self._assets_root()
        self._image_index = []
        if not assets:
            return
        folders = [assets / "store_cards" / "3x", assets / "store_cards" / "2x"]
        for folder in folders:
            if folder.exists():
                for path in folder.glob("card_small*"):
                    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                        self._image_index.append(path)

    def _cover_path(self, book_key: str) -> Path | None:
        if self._image_index is None:
            self._build_image_index()
        image_index = self._image_index or []
        candidates = [book_key, self._normalize_card_key(book_key)]
        if book_key.startswith(("deu_", "fra_", "spa_")):
            stripped = "_".join(book_key.split("_")[1:])
            candidates.extend([stripped, self._normalize_card_key(stripped)])
        series_keys = [self._series_key(key) for key in candidates if self._series_key(key)]
        for prefix in ("card_small_",):
            for key in candidates:
                for path in image_index:
                    if path.stem.startswith(prefix + key):
                        return path
            for key in series_keys:
                for path in image_index:
                    if key and key in path.stem:
                        return path

        tokens = self._candidate_tokens(book_key)
        if not tokens:
            return None

        def score(path: Path) -> tuple[int, int, str]:
            stem = path.stem.lower()
            token_score = sum(1 for token in tokens if token in stem)
            priority = 1 if stem.startswith("card_small_") else 0
            return token_score, priority, stem

        best = max(image_index, key=score, default=None)
        if best and score(best)[0] >= max(2, min(4, len(tokens))):
            return best
        return None

    def _fallback_cover(self, title: str, genre: str) -> QPixmap:
        pm = QPixmap(264, 380)
        colors = {
            "Romance": ("#7b2f52", "#d77aa2"),
            "Horror": ("#263238", "#8fa3ad"),
            "Fantasy": ("#31533b", "#9cc56b"),
            "Crime": ("#333342", "#89a7ff"),
            "Adventure": ("#5c4a2d", "#e0b866"),
            "Scifi": ("#254d5c", "#73d6f0"),
        }
        key = next((k for k in colors if k in genre), "Romance")
        bg, fg = colors[key]
        pm.fill(QColor(bg))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(fg), 4))
        painter.drawRect(pm.rect().adjusted(10, 10, -10, -10))
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(18)
        painter.setFont(font)
        painter.drawText(pm.rect().adjusted(22, 48, -22, -70), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, title)
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#dddddd"))
        painter.drawText(pm.rect().adjusted(16, 0, -16, -22), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, genre.upper())
        painter.end()
        return pm

    def _cover_pixmap(self, card: dict) -> QPixmap:
        path = card.get("cover")
        if path:
            pm = QPixmap(str(path))
            if not pm.isNull():
                return pm
        return self._fallback_cover(card["title"], card["genre"])

    def _rebuild_cards(self):
        self._image_index = None
        self._book_cards = []
        for display, chapters in self._books:
            key = self._book_key(display, chapters)
            title = self._pretty_title(key) or str(display)
            self._book_cards.append({
                "key": key,
                "title": title,
                "genre": self._genre(key),
                "chapters": chapters,
                "cover": self._cover_path(key),
            })
        self._book_cards.sort(key=lambda c: (c["genre"], c["title"], c["key"]))

    def _rebuild_genres(self):
        current = self._genre_combo.currentData() if self._genre_combo.count() else ""
        genres = sorted({c["genre"] for c in self._book_cards})
        self._genre_combo.blockSignals(True)
        self._genre_combo.clear()
        self._genre_combo.addItem(f"All Genres ({len(self._book_cards)})", "")
        for genre in genres:
            count = sum(1 for c in self._book_cards if c["genre"] == genre)
            self._genre_combo.addItem(f"{genre} ({count})", genre)
        if current:
            idx = self._genre_combo.findData(current)
            if idx >= 0:
                self._genre_combo.setCurrentIndex(idx)
        self._genre_combo.blockSignals(False)

    def _populate_books(self):
        query = self._search.text().strip().lower()
        genre = self._genre_combo.currentData() if self._genre_combo.count() else ""
        self._book_list.blockSignals(True)
        self._book_list.clear()
        for card in self._book_cards:
            if genre and card["genre"] != genre:
                continue
            hay = f'{card["title"]} {card["genre"]} {card["key"]}'.lower()
            if query and query not in hay:
                continue
            item = QListWidgetItem(QIcon(self._cover_pixmap(card)), card["title"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(160, 235))
            item.setData(Qt.ItemDataRole.UserRole, card)
            self._book_list.addItem(item)
        self._book_list.blockSignals(False)
        if self._book_list.count():
            self._book_list.setCurrentRow(0)
        else:
            self._show_book(None)

    def _on_book_select(self, current, _previous):
        self._show_book(current.data(Qt.ItemDataRole.UserRole) if current else None)

    def _show_book(self, card: dict | None):
        self._chapter_list.blockSignals(True)
        self._chapter_list.clear()
        if not card:
            self._title_lbl.setText("Select a book")
            self._meta_lbl.setText("")
            self._cover_lbl.clear()
            self._graph.set_events([])
            self._chapter_list.blockSignals(False)
            return
        self._title_lbl.setText(card["title"])
        art_note = "cover art" if card.get("cover") else "generated card"
        self._meta_lbl.setText(f'{card["genre"]}  |  {len(card["chapters"])} chapter{"s" if len(card["chapters"]) != 1 else ""}  |  {art_note}')
        self._cover_lbl.setPixmap(self._cover_pixmap(card).scaled(
            self._cover_lbl.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        ))
        for chapter_name, chapter_path in card["chapters"]:
            item = QListWidgetItem(str(chapter_name))
            item.setData(Qt.ItemDataRole.UserRole, str(chapter_path))
            self._chapter_list.addItem(item)
        self._chapter_list.blockSignals(False)
        if self._chapter_list.count():
            self._chapter_list.setCurrentRow(0)

    def _on_chapter_select(self, current, _previous):
        if current is None:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
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
        self._rebuild_cards()
        self._rebuild_genres()
        self._populate_books()

    def refresh(self, books_root: Path, books: list):
        self._books_root = books_root
        self._books = books
        self._rebuild_cards()
        self._rebuild_genres()
        self._populate_books()
