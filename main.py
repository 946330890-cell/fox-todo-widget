#!/usr/bin/env pythonw
"""A frameless, transparent PyQt5 desktop todo widget for Windows."""

from __future__ import annotations

import json
import ctypes
import math
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

from PyQt5.QtCore import (
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QObject,
    QSize,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPolygonF,
    QPixmap,
)
from PyQt5.QtNetwork import (
    QLocalServer,
    QLocalSocket,
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = APP_DIR
DATA_DIR = os.path.join(APP_DIR, "data")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
EXPORT_DIR = os.path.join(APP_DIR, "exports")
ASSET_DIR = os.path.join(RESOURCE_DIR, "assets")
INSTANCE_NAME = "fox_todo_widget_single_instance_v1"
MUTEX_NAME = "FoxTodoWidgetMutexV1"
DEFAULT_LOCATION = {
    "name": "福州鼓楼",
    "latitude": 26.1025,
    "longitude": 119.2965,
}
IP_LOCATION_URL = "https://ipwho.is/"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
CARD_WIDTH = 340
CARD_HEIGHT = 360
FOX_OVERHANG = 52
WINDOW_HEIGHT = CARD_HEIGHT + FOX_OVERHANG
MEMO_RAIL_WIDTH = 78
MIN_CARD_WIDTH = 300
MIN_WINDOW_WIDTH = MEMO_RAIL_WIDTH + MIN_CARD_WIDTH
MIN_WINDOW_HEIGHT = 330
COLLAPSED_WIDTH = 132
COLLAPSED_HEIGHT = 132
COLLAPSED_MARGIN = 8
RESIZE_GRIP_SIZE = 8

PALETTE = {
    "card": "#fff9f1",
    "card_shadow": "#ead7c6",
    "orange": "#ef984e",
    "orange_dark": "#c96f35",
    "brown": "#6a4035",
    "brown_soft": "#987064",
    "cream": "#fffaf5",
    "white": "#ffffff",
    "line": "#f0dfd1",
    "mint": "#b9ded1",
    "mint_dark": "#579886",
    "peach": "#fff0e2",
    "muted": "#bca79b",
}


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def memo_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def format_memo_timestamp(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "暂无更新时间"
    return parsed.strftime("%m月%d日 %H:%M")


def normalize_location(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    name = str(value.get("name", "")).strip()
    try:
        latitude = float(value.get("latitude"))
        longitude = float(value.get("longitude"))
    except (TypeError, ValueError):
        return None
    if not name or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return None
    return {"name": name, "latitude": latitude, "longitude": longitude}


def default_state() -> dict:
    return {
        "todos": [],
        "habits": [],
        "active_tab": "todo",
        "memos": [],
        "active_memo_id": None,
        "memo_mode": False,
        "location": None,
    }


def load_state() -> dict:
    ensure_data_dir()
    if not os.path.exists(STATE_PATH):
        return default_state()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError, TypeError):
        return default_state()

    state = default_state()
    if isinstance(raw, dict):
        todos = raw.get("todos", [])
        habits = raw.get("habits", [])
        memos = raw.get("memos", [])
        state["active_tab"] = raw.get("active_tab", "todo")
        state["active_memo_id"] = raw.get("active_memo_id")
        state["memo_mode"] = bool(raw.get("memo_mode", False))
        state["location"] = normalize_location(raw.get("location"))
        if state["active_tab"] not in {"todo", "done", "habit"}:
            state["active_tab"] = "todo"
        if isinstance(todos, list):
            for item in todos:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                state["todos"].append(
                    {
                        "id": str(item.get("id") or new_id()),
                        "text": text,
                        "done": bool(item.get("done", False)),
                    }
                )
        if isinstance(habits, list):
            for item in habits:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                days = item.get("days", [False] * 7)
                if not isinstance(days, list):
                    days = [False] * 7
                days = [bool(value) for value in days[:7]]
                days.extend([False] * (7 - len(days)))
                state["habits"].append(
                    {
                        "id": str(item.get("id") or new_id()),
                        "name": name,
                        "days": days,
                    }
                )
        if isinstance(memos, list):
            for item in memos:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label", "")).strip()
                if not label:
                    continue
                state["memos"].append(
                    {
                        "id": str(item.get("id") or new_id()),
                        "label": label,
                        "content": str(item.get("content", "")),
                        "updated_at": str(item.get("updated_at") or memo_timestamp()),
                    }
                )
        memo_ids = {item["id"] for item in state["memos"]}
        if state["active_memo_id"] not in memo_ids:
            state["active_memo_id"] = None
        if not state["active_memo_id"]:
            state["memo_mode"] = False
    return state


def save_state(state: dict) -> None:
    ensure_data_dir()
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
    except OSError:
        # The widget should stay usable if a removable/read-only location is used.
        pass


def clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)


def font(size: int, weight: int = QFont.Normal) -> QFont:
    result = QFont("Microsoft YaHei UI")
    result.setPixelSize(size)
    result.setWeight(weight)
    return result


class CardSurface(QFrame):
    drag_started = pyqtSignal(QPoint)
    drag_moved = pyqtSignal(QPoint)
    drag_finished = pyqtSignal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.setPen(QColor(PALETTE["card_shadow"]))
        painter.setBrush(QColor(PALETTE["card"]))
        painter.drawRoundedRect(rect, 23, 23)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.drag_started.emit(event.globalPos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.drag_moved.emit(event.globalPos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.drag_finished.emit(event.globalPos())
        super().mouseReleaseEvent(event)


class DragHandle(QWidget):
    drag_started = pyqtSignal(QPoint)
    drag_moved = pyqtSignal(QPoint)
    drag_finished = pyqtSignal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self.drag_started.emit(event.globalPos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.drag_moved.emit(event.globalPos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
            self.drag_finished.emit(event.globalPos())
        super().mouseReleaseEvent(event)


class ResizeGrip(QWidget):
    """Invisible edge/corner grip for resizing the frameless window."""

    resize_started = pyqtSignal(str, QPoint)
    resize_moved = pyqtSignal(QPoint)
    resize_finished = pyqtSignal(QPoint)

    CURSORS = {
        "left": Qt.SizeHorCursor,
        "right": Qt.SizeHorCursor,
        "top": Qt.SizeVerCursor,
        "bottom": Qt.SizeVerCursor,
        "top_left": Qt.SizeFDiagCursor,
        "bottom_right": Qt.SizeFDiagCursor,
        "top_right": Qt.SizeBDiagCursor,
        "bottom_left": Qt.SizeBDiagCursor,
    }

    def __init__(self, edges: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edges = edges
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(self.CURSORS[edges])

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.resize_started.emit(self.edges, event.globalPos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.resize_moved.emit(event.globalPos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.resize_finished.emit(event.globalPos())
        super().mouseReleaseEvent(event)


class CharacterLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class BookmarkRibbon(QWidget):
    """A soft bookmark ribbon that sits behind the fox at the card's top-left."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width()
        height = self.height()
        ribbon = QPolygonF(
            [
                QPointF(8, 5),
                QPointF(width - 8, 5),
                QPointF(width - 8, height - 12),
                QPointF(width / 2, height - 27),
                QPointF(8, height - 12),
            ]
        )
        painter.setPen(QColor("#e5a05e"))
        painter.setBrush(QColor("#f7c47f"))
        painter.drawPolygon(ribbon)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#fff1d7"))
        painter.drawRoundedRect(QRectF(18, 12, width - 36, 7), 3.5, 3.5)
        painter.setBrush(QColor("#eda35e"))
        painter.drawEllipse(QRectF(width / 2 - 4, height - 39, 8, 8))
        painter.end()


class MoneyEffect(QWidget):
    """Lightweight coin and floating-money-text animation above the card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.coins: list[dict] = []
        self.elapsed = 0.0
        self.next_spawn = 0.9
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)

    def start(self) -> None:
        if not self.timer.isActive():
            self.timer.start(55)

    def stop(self) -> None:
        self.timer.stop()

    def spawn_coin_wave(self) -> None:
        target_x = 57.0
        target_y = 34.0
        for index in range(2):
            self.coins.append(
                {
                    "born": self.elapsed + index * 0.32,
                    "duration": 1.38 + random.uniform(-0.08, 0.08),
                    "start_x": random.uniform(205.0, 285.0),
                    "start_y": random.uniform(-10.0, 7.0),
                    "target_x": target_x + random.uniform(-3.0, 3.0),
                    "target_y": target_y + random.uniform(-2.0, 2.0),
                    "sway": random.uniform(-7.0, 7.0),
                }
            )

    def tick(self) -> None:
        self.elapsed += 0.055
        if self.elapsed >= self.next_spawn:
            self.spawn_coin_wave()
            self.next_spawn = self.elapsed + random.uniform(2.2, 3.4)
        self.coins = [
            coin
            for coin in self.coins
            if self.elapsed - coin["born"] <= coin["duration"]
        ]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # A tiny slot above the eyes makes the destination of the coins legible.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#6a4035"))
        painter.drawRoundedRect(QRectF(50, 33, 15, 4), 2, 2)

        for coin in self.coins:
            age = self.elapsed - coin["born"]
            if age < 0:
                continue
            progress = min(1.0, max(0.0, age / coin["duration"]))
            eased = 1.0 - (1.0 - progress) ** 2
            x = coin["start_x"] + (coin["target_x"] - coin["start_x"]) * eased
            y = coin["start_y"] + (coin["target_y"] - coin["start_y"]) * eased
            y += math.sin(progress * math.pi) * coin["sway"]
            alpha = 255 if progress < 0.82 else int(255 * (1.0 - progress) / 0.18)
            coin_color = QColor(248, 193, 65, max(0, alpha))
            edge_color = QColor(206, 133, 35, max(0, alpha))
            painter.setPen(edge_color)
            painter.setBrush(coin_color)
            painter.drawEllipse(QRectF(x - 8, y - 6, 16, 12))
            painter.setPen(QColor(255, 239, 171, max(0, alpha)))
            painter.setFont(font(8, QFont.Bold))
            painter.drawText(QRectF(x - 6, y - 5, 12, 10), Qt.AlignCenter, "¥")

        # Two staggered labels create a restrained “钱来钱来” rise without a pop.
        text_phase = (self.elapsed % 2.8) / 2.8
        if text_phase < 0.9:
            text_alpha = int(255 * min(1.0, (0.9 - text_phase) / 0.22))
            lift = text_phase * 18.0
            painter.setFont(font(13, QFont.Bold))
            for x, y in ((166, 42), (211, 51)):
                shadow = QColor(255, 255, 255, max(0, min(110, text_alpha)))
                painter.setPen(shadow)
                painter.drawText(QRectF(x + 1, y - lift + 1, 40, 22), Qt.AlignLeft, "钱来")
                painter.setPen(QColor(239, 143, 67, max(0, text_alpha)))
                painter.drawText(QRectF(x, y - lift, 40, 22), Qt.AlignLeft, "钱来")

        painter.end()


class FlatButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(font(14, QFont.Bold))
        self.setStyleSheet(
            f"""
            QPushButton {{
                color: {PALETTE['brown']};
                background: transparent;
                border: none;
                border-radius: 12px;
                padding: 0;
            }}
            QPushButton:hover {{ background: {PALETTE['peach']}; }}
            QPushButton:pressed {{ background: {PALETTE['line']}; }}
            """
        )


class LocationDialog(QDialog):
    """Small themed first-run dialog for selecting or detecting a city."""

    def __init__(self, parent: QWidget | None = None, current: dict | None = None) -> None:
        super().__init__(parent)
        self.selected_location: dict | None = None
        self.pending_kind = ""
        self.pending_query = ""
        self.network = QNetworkAccessManager(self)
        self.reply: QNetworkReply | None = None

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedSize(360, 250)

        panel = QFrame(self)
        panel.setGeometry(0, 0, 360, 250)
        panel.setStyleSheet(
            f"QFrame {{ background: {PALETTE['card']}; border: 1px solid {PALETTE['line']}; "
            "border-radius: 22px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 17, 22, 17)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("设置天气地点", panel)
        title.setFont(font(15, QFont.Bold))
        title.setStyleSheet(f"color: {PALETTE['brown']}; background: transparent;")
        header.addWidget(title, 1)
        close_button = FlatButton("×", panel)
        close_button.setFixedSize(26, 26)
        close_button.setFont(font(17, QFont.Normal))
        close_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['brown_soft']}; background: transparent; "
            "border: none; border-radius: 13px; padding: 0; }"
            f"QPushButton:hover {{ background: {PALETTE['peach']}; }}"
        )
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        layout.addLayout(header)

        subtitle = QLabel("输入城市名，或根据公网 IP 自动识别城市", panel)
        subtitle.setFont(font(9))
        subtitle.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        layout.addWidget(subtitle)

        self.city_input = QLineEdit(panel)
        current_name = str((current or {}).get("name", "")).strip()
        self.city_input.setText(current_name)
        self.city_input.setPlaceholderText("例如：福州鼓楼、杭州、上海")
        self.city_input.setFont(font(10))
        self.city_input.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: {PALETTE['white']}; "
            f"border: 1px solid {PALETTE['line']}; border-radius: 14px; padding: 7px 11px; }}"
            f"QLineEdit:focus {{ border: 1px solid {PALETTE['orange']}; }}"
        )
        self.city_input.returnPressed.connect(self.lookup_city)
        layout.addWidget(self.city_input)

        self.status_label = QLabel("天气会按照这个地点显示", panel)
        self.status_label.setWordWrap(True)
        self.status_label.setFont(font(8))
        self.status_label.setStyleSheet(f"color: {PALETTE['brown_soft']}; background: transparent;")
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 2, 0, 0)
        button_row.setSpacing(7)
        self.auto_button = FlatButton("自动识别", panel)
        self.auto_button.setFixedHeight(31)
        self.auto_button.setFont(font(10, QFont.Bold))
        self.auto_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['mint_dark']}; "
            "border: none; border-radius: 15px; padding: 0 12px; }"
            f"QPushButton:hover {{ background: {PALETTE['orange']}; }}"
        )
        self.auto_button.clicked.connect(self.auto_detect)
        button_row.addWidget(self.auto_button)

        self.skip_button = FlatButton("稍后设置", panel)
        self.skip_button.setFixedHeight(31)
        self.skip_button.setFont(font(9))
        self.skip_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['brown_soft']}; background: transparent; "
            "border: none; border-radius: 15px; padding: 0 8px; }"
            f"QPushButton:hover {{ background: {PALETTE['peach']}; }}"
        )
        self.skip_button.clicked.connect(self.reject)
        button_row.addWidget(self.skip_button)

        self.confirm_button = FlatButton("使用这个城市", panel)
        self.confirm_button.setFixedHeight(31)
        self.confirm_button.setFont(font(10, QFont.Bold))
        self.confirm_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['orange']}; "
            "border: none; border-radius: 15px; padding: 0 12px; }"
            f"QPushButton:hover {{ background: {PALETTE['orange_dark']}; }}"
        )
        self.confirm_button.clicked.connect(self.lookup_city)
        button_row.addWidget(self.confirm_button)
        layout.addLayout(button_row)

        privacy = QLabel("自动识别只能定位到城市级别，且可能受网络运营商影响。", panel)
        privacy.setFont(font(7))
        privacy.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        layout.addWidget(privacy)

    def _set_busy(self, busy: bool) -> None:
        self.auto_button.setEnabled(not busy)
        self.confirm_button.setEnabled(not busy)
        self.city_input.setEnabled(not busy)

    def lookup_city(self) -> None:
        query = self.city_input.text().strip()
        if not query:
            self.status_label.setText("请先输入城市名")
            return
        self.pending_kind = "geocode"
        self.pending_query = query
        encoded = quote(query)
        url = (
            f"{GEOCODING_URL}?name={encoded}&count=1&language=zh&format=json"
        )
        self._request(url, "正在查询城市…")

    def auto_detect(self) -> None:
        self.pending_kind = "ip"
        self.pending_query = ""
        self._request(IP_LOCATION_URL, "正在根据公网 IP 识别城市…")

    def _request(self, url: str, status: str) -> None:
        if self.reply is not None and self.reply.isRunning():
            return
        self._set_busy(True)
        self.status_label.setText(status)
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"FoxTodoWidget/1.0")
        self.reply = self.network.get(request)
        self.reply.finished.connect(self._on_reply_finished)

    def _on_reply_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        try:
            if reply.error() != QNetworkReply.NoError:
                raise ValueError("location request failed")
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            location = self._parse_location(payload)
            if location is None:
                raise ValueError("location not found")
            self.selected_location = location
            self.status_label.setText(f"已找到：{location['name']}")
            self.accept()
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            self.status_label.setText("没有找到这个地点，请换个城市名或稍后再试")
            self._set_busy(False)
        finally:
            if self.reply is reply:
                self.reply = None
            reply.deleteLater()

    def _parse_location(self, payload: dict) -> dict | None:
        if self.pending_kind == "geocode":
            results = payload.get("results") or []
            if not results:
                return None
            result = results[0]
            return normalize_location(
                {
                    "name": self.pending_query,
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                }
            )

        if payload.get("success") is False:
            return None
        city = str(payload.get("city") or payload.get("region") or "").strip()
        country = str(payload.get("country") or "").strip()
        name = city or country
        return normalize_location(
            {
                "name": name,
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
            }
        )


class TabButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(font(12, QFont.Bold))
        self.setStyleSheet(
            f"""
            QPushButton {{
                color: {PALETTE['brown_soft']};
                background: transparent;
                border: none;
                border-radius: 14px;
                padding: 0 6px;
            }}
            QPushButton:hover {{ background: {PALETTE['peach']}; }}
            QPushButton:checked {{
                color: {PALETTE['white']};
                background: {PALETTE['orange']};
            }}
            """
        )


class MemoTagButton(QPushButton):
    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.double_clicked.emit()
        event.accept()


class MemoTagRow(QWidget):
    activated = pyqtSignal(str)
    label_changed = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, item: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.memo_id = str(item["id"])
        self.current_label = str(item.get("label", "备忘"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.tag_button = MemoTagButton(self.current_label, self)
        self.tag_button.setMinimumWidth(44)
        self.tag_button.setFixedHeight(28)
        self.tag_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tag_button.setFocusPolicy(Qt.NoFocus)
        self.tag_button.setCursor(Qt.PointingHandCursor)
        self.tag_button.setFont(font(9, QFont.Bold))
        self.tag_button.clicked.connect(lambda: self.activated.emit(self.memo_id))
        self.tag_button.double_clicked.connect(self.begin_edit)
        layout.addWidget(self.tag_button, 1)

        self.editor = QLineEdit(self)
        self.editor.setText(self.current_label)
        self.editor.setFont(font(9, QFont.Bold))
        self.editor.setMinimumWidth(44)
        self.editor.setFixedHeight(28)
        self.editor.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: {PALETTE['white']}; "
            f"border: 1px solid {PALETTE['orange']}; border-radius: 10px; padding: 0 4px; }}"
        )
        self.editor.returnPressed.connect(self.commit_edit)
        self.editor.editingFinished.connect(self.commit_edit)
        self.editor.hide()
        layout.addWidget(self.editor, 1)

        self.delete_button = FlatButton("×", self)
        self.delete_button.setFixedSize(18, 28)
        self.delete_button.setFont(font(13, QFont.Normal))
        self.delete_button.setToolTip("删除备忘标签")
        self.delete_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['brown_soft']}; background: {PALETTE['cream']}; "
            "border: none; border-radius: 9px; padding: 0; }"
            f"QPushButton:hover {{ color: {PALETTE['orange_dark']}; background: {PALETTE['peach']}; }}"
        )
        self.delete_button.clicked.connect(lambda: self.removed.emit(self.memo_id))
        layout.addWidget(self.delete_button)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.tag_button.setStyleSheet(
                f"QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['orange']}; "
                "border: none; border-radius: 14px; padding: 0 3px; }"
                f"QPushButton:hover {{ background: {PALETTE['orange_dark']}; }}"
            )
        else:
            self.tag_button.setStyleSheet(
                f"QPushButton {{ color: {PALETTE['brown_soft']}; background: {PALETTE['cream']}; "
                f"border: 1px solid {PALETTE['line']}; border-radius: 14px; padding: 0 3px; }}"
                f"QPushButton:hover {{ color: {PALETTE['brown']}; background: {PALETTE['peach']}; }}"
            )

    def begin_edit(self) -> None:
        self.tag_button.hide()
        self.editor.show()
        self.editor.selectAll()
        self.editor.setFocus()

    def commit_edit(self) -> None:
        if not self.editor.isVisible():
            return
        label = self.editor.text().strip() or self.current_label
        changed = label != self.current_label
        self.current_label = label
        self.tag_button.setText(label)
        self.editor.hide()
        self.tag_button.show()
        if changed:
            self.label_changed.emit(self.memo_id, label)


class MemoRail(QWidget):
    memo_selected = pyqtSignal(str)
    memo_added = pyqtSignal(str)
    memo_removed = pyqtSignal(str)
    memo_renamed = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 0, 2, 0)
        layout.setSpacing(5)

        title = QLabel("备忘", self)
        title.setAlignment(Qt.AlignCenter)
        title.setFont(font(10, QFont.Bold))
        title.setStyleSheet(f"color: {PALETTE['brown_soft']}; background: transparent;")
        layout.addWidget(title)

        self.rows_host = QWidget(self)
        self.rows_host.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        layout.addWidget(self.rows_host, 1)

        self.add_editor = QLineEdit(self)
        self.add_editor.setPlaceholderText("标签名称")
        self.add_editor.setFont(font(9))
        self.add_editor.setFixedHeight(26)
        self.add_editor.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: {PALETTE['white']}; "
            f"border: 1px solid {PALETTE['line']}; border-radius: 10px; padding: 0 4px; }}"
        )
        self.add_editor.returnPressed.connect(self.commit_new_label)
        self.add_editor.hide()
        layout.addWidget(self.add_editor)

        self.add_button = FlatButton("＋", self)
        self.add_button.setFixedHeight(28)
        self.add_button.setFont(font(15, QFont.Bold))
        self.add_button.setToolTip("添加备忘标签")
        self.add_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['mint_dark']}; "
            "border: none; border-radius: 14px; padding: 0; }"
            f"QPushButton:hover {{ background: {PALETTE['orange']}; }}"
        )
        self.add_button.clicked.connect(self.toggle_add)
        layout.addWidget(self.add_button)

    def render(self, memos: list[dict], active_id: str | None) -> None:
        clear_layout(self.rows_layout)
        if not memos:
            hint = QLabel("点击下方\n＋ 新建")
            hint.setAlignment(Qt.AlignCenter)
            hint.setWordWrap(True)
            hint.setFont(font(9))
            hint.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
            self.rows_layout.addWidget(hint)
        else:
            for item in memos:
                row = MemoTagRow(item, self.rows_host)
                row.set_selected(item["id"] == active_id)
                row.activated.connect(self.memo_selected)
                row.removed.connect(self.memo_removed)
                row.label_changed.connect(self.memo_renamed)
                self.rows_layout.addWidget(row)
        self.rows_layout.addStretch(1)

    def toggle_add(self) -> None:
        if self.add_editor.isVisible():
            self.commit_new_label()
            return
        self.add_editor.clear()
        self.add_editor.show()
        self.add_button.setText("确定")
        self.add_editor.setFocus()

    def commit_new_label(self) -> None:
        label = self.add_editor.text().strip()
        if label:
            self.memo_added.emit(label)
        self.add_editor.clear()
        self.add_editor.hide()
        self.add_button.setText("＋")


class DayButton(QToolButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setFixedSize(24, 24)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(font(10, QFont.Bold))
        self.setStyleSheet(
            f"""
            QToolButton {{
                color: {PALETTE['brown_soft']};
                background: {PALETTE['peach']};
                border: none;
                border-radius: 12px;
                padding: 0;
            }}
            QToolButton:hover {{ background: #ffe4cd; }}
            QToolButton:checked {{
                color: {PALETTE['white']};
                background: {PALETTE['mint_dark']};
            }}
            """
        )


class CircleCheckBox(QCheckBox):
    """A small hand-painted checkbox so the checked state has a real tick."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("QCheckBox { background: transparent; border: none; }")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = self.rect().center()
        circle = QRect(center.x() - 8, center.y() - 8, 16, 16)
        if self.isChecked():
            painter.setPen(QColor(PALETTE["orange"]))
            painter.setBrush(QColor(PALETTE["orange"]))
            painter.drawEllipse(circle)
            pen = painter.pen()
            pen.setColor(QColor(PALETTE["white"]))
            pen.setWidth(2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(QPoint(center.x() - 4, center.y()), QPoint(center.x() - 1, center.y() + 3))
            painter.drawLine(QPoint(center.x() - 1, center.y() + 3), QPoint(center.x() + 5, center.y() - 4))
        else:
            painter.setPen(QColor(PALETTE["orange"]))
            painter.setBrush(QColor(PALETTE["white"]))
            painter.drawEllipse(circle)
        painter.end()


class TodoRow(QFrame):
    toggled = pyqtSignal(str, bool)
    text_changed = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, item: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item["id"]
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QFrame {{ background: {PALETTE['white']}; border: none; border-radius: 15px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 5, 2)
        layout.setSpacing(4)

        self.checkbox = CircleCheckBox(self)
        self.checkbox.setChecked(bool(item.get("done", False)))
        self.checkbox.toggled.connect(lambda checked: self.toggled.emit(self.item_id, checked))
        layout.addWidget(self.checkbox)

        self.editor = QLineEdit(self)
        self.editor.setText(str(item.get("text", "")))
        self.editor.setFont(font(12))
        self.editor.setFrame(False)
        self.editor.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: transparent; border: none; padding: 0; }}"
        )
        self.editor.editingFinished.connect(
            lambda: self.text_changed.emit(self.item_id, self.editor.text().strip())
        )
        layout.addWidget(self.editor, 1)

        self.delete_button = FlatButton("×", self)
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setFont(font(17, QFont.Normal))
        self.delete_button.setToolTip("删除")
        self.delete_button.clicked.connect(lambda: self.removed.emit(self.item_id))
        layout.addWidget(self.delete_button)
        self.update_visual(bool(item.get("done", False)))

    def update_visual(self, done: bool) -> None:
        current_font = self.editor.font()
        current_font.setStrikeOut(done)
        self.editor.setFont(current_font)
        self.editor.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['muted'] if done else PALETTE['brown']}; background: transparent; border: none; padding: 0; }}"
        )


class HabitRow(QFrame):
    day_changed = pyqtSignal(str, int, bool)
    name_changed = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, item: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item["id"]
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QFrame {{ background: {PALETTE['white']}; border: none; border-radius: 15px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 3, 4, 3)
        layout.setSpacing(2)

        self.editor = QLineEdit(self)
        self.editor.setText(str(item.get("name", "")))
        self.editor.setFont(font(11, QFont.Bold))
        self.editor.setFrame(False)
        self.editor.setMinimumWidth(62)
        self.editor.setMaximumWidth(92)
        self.editor.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: transparent; border: none; padding: 0; }}"
        )
        self.editor.editingFinished.connect(
            lambda: self.name_changed.emit(self.item_id, self.editor.text().strip())
        )
        layout.addWidget(self.editor, 1)

        days = item.get("days", [False] * 7)
        for index, label in enumerate("一二三四五六日"):
            button = DayButton(label, self)
            button.setChecked(bool(days[index]))
            button.toggled.connect(
                lambda checked, day=index: self.day_changed.emit(self.item_id, day, checked)
            )
            layout.addWidget(button)

        self.delete_button = FlatButton("×", self)
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setFont(font(16, QFont.Normal))
        self.delete_button.setToolTip("删除打卡项")
        self.delete_button.clicked.connect(lambda: self.removed.emit(self.item_id))
        layout.addWidget(self.delete_button)


class SpeechBubble(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(
            f"QFrame {{ background: {PALETTE['white']}; border: 1px solid {PALETTE['line']}; border-radius: 15px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(1)
        self.title = QLabel("距离下班")
        self.title.setFont(font(10, QFont.Bold))
        self.title.setStyleSheet(f"color: {PALETTE['orange_dark']}; background: transparent;")
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setFont(font(10))
        self.body.setStyleSheet(f"color: {PALETTE['brown']}; background: transparent;")
        layout.addWidget(self.title)
        layout.addWidget(self.body)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.setPen(QColor(PALETTE["line"]))
        painter.setBrush(QColor(PALETTE["white"]))
        painter.drawRoundedRect(rect, 15, 15)
        painter.end()
        super().paintEvent(event)


class InstanceGuard(QObject):
    show_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.mutex_handle = None
        self.server = QLocalServer(self)
        self.already_running = False

        # QLocalServer handles the wake-up message; the Windows mutex closes
        # the race where two launchers arrive at exactly the same moment.
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            self.mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            self.already_running = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS

        if self.already_running:
            self._send_show_request()
            return

        if not self.server.listen(INSTANCE_NAME):
            if self._send_show_request():
                self.already_running = True
            else:
                QLocalServer.removeServer(INSTANCE_NAME)
                self.server.listen(INSTANCE_NAME)
        self.server.newConnection.connect(self._on_connection)

    def _send_show_request(self) -> bool:
        probe = QLocalSocket(self)
        probe.connectToServer(INSTANCE_NAME)
        if not probe.waitForConnected(500):
            return False
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        return True

    def _on_connection(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda current=socket: self._read_socket(current))

    def _read_socket(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).strip() == b"show":
            self.show_requested.emit()
        socket.disconnectFromServer()


class MainWindow(QWidget):
    def __init__(self, state: dict, guard: InstanceGuard) -> None:
        super().__init__()
        self.state = state
        self.guard = guard
        self.active_tab = state.get("active_tab", "todo")
        self.active_memo_id = state.get("active_memo_id")
        self.memo_mode = bool(state.get("memo_mode", False) and self.active_memo_id)
        self.collapsed = False
        self.collapsed_side = "left"
        self.dragging = False
        self.drag_offset = QPoint()
        self.resizing = False
        self.resize_edges = ""
        self.resize_start_pos = QPoint()
        self.resize_start_geometry = QRect()
        self.resize_grips: dict[str, ResizeGrip] = {}
        self.last_full_pos: QPoint | None = None
        self.float_phase = 0.0
        self.carousel_index = 0
        self.effect_started = False
        self.blink_timer: QTimer | None = None
        self.bubble_timer: QTimer | None = None
        self.weather_reply: QNetworkReply | None = None
        self.location = normalize_location(state.get("location"))
        initial_location = self.location or DEFAULT_LOCATION
        self.weather_location = initial_location["name"]
        self.weather_latitude = initial_location["latitude"]
        self.weather_longitude = initial_location["longitude"]
        self.weather_condition = ""
        self.memo_save_timer: QTimer | None = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.resize(CARD_WIDTH + MEMO_RAIL_WIDTH, WINDOW_HEIGHT)

        self.card = CardSurface(self)
        self.card.setGeometry(MEMO_RAIL_WIDTH, FOX_OVERHANG, CARD_WIDTH, CARD_HEIGHT)
        self.card.drag_started.connect(self.begin_drag)
        self.card.drag_moved.connect(self.continue_drag)
        self.card.drag_finished.connect(self.finish_drag)

        self.bookmark = BookmarkRibbon(self.card)
        self.bookmark.setGeometry(7, 0, 105, 121)
        # The fox itself is transparent; keep the surrounding desktop visible
        # instead of drawing a solid bookmark plate behind it.
        self.bookmark.hide()

        self.character = CharacterLabel(self)
        self.character.setGeometry(MEMO_RAIL_WIDTH + 3, 0, 112, 112)
        self.character.clicked.connect(self.on_character_clicked)

        self.money_effect = MoneyEffect(self)
        self.money_effect.setGeometry(MEMO_RAIL_WIDTH, 0, CARD_WIDTH, WINDOW_HEIGHT)
        self.money_effect.hide()

        self.character_pixmaps = self.load_character_pixmaps()
        self.set_character_frame(0)
        self.memo_rail = MemoRail(self)
        self.memo_rail.memo_selected.connect(self.enter_memo)
        self.memo_rail.memo_added.connect(self.add_memo)
        self.memo_rail.memo_removed.connect(self.remove_memo)
        self.memo_rail.memo_renamed.connect(self.rename_memo)
        self.memo_save_timer = QTimer(self)
        self.memo_save_timer.setSingleShot(True)
        self.memo_save_timer.timeout.connect(self.save_current_memo)
        self.build_ui()
        self.update_memo_rail_geometry()
        self.create_resize_grips()

        self.character.raise_()
        self.money_effect.raise_()
        self.memo_rail.raise_()
        self.raise_resize_grips()

        self.bubble = SpeechBubble(self)
        self.bubble.setGeometry(MEMO_RAIL_WIDTH + 92, 93, 232, 65)
        self.bubble.hide()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        self.weather_manager = QNetworkAccessManager(self)
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.refresh_weather)
        self.weather_timer.start(15 * 60 * 1000)
        QTimer.singleShot(120, self.refresh_weather)
        if self.location is None and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QTimer.singleShot(0, self.ensure_location)

        guard.show_requested.connect(self.restore_and_raise)
        QTimer.singleShot(650, self.start_effects)

    def load_character_pixmaps(self) -> list[QPixmap]:
        paths = [
            os.path.join(ASSET_DIR, "fox_normal.png"),
            os.path.join(ASSET_DIR, "fox_smile.png"),
            os.path.join(ASSET_DIR, "fox_wink.png"),
        ]
        pixmaps = [QPixmap(path) for path in paths]
        return [pixmap for pixmap in pixmaps if not pixmap.isNull()]

    def build_ui(self) -> None:
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QWidget(self.card)
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(103, 0, 1, 0)
        header_layout.setSpacing(4)

        self.min_button = FlatButton("–", header)
        self.min_button.setFixedSize(24, 24)
        self.min_button.setFont(font(16, QFont.Normal))
        self.min_button.setToolTip("收起（点击狐狸恢复）")
        self.min_button.clicked.connect(lambda: self.collapse_to_edge("right"))
        header_layout.addWidget(self.min_button)

        self.close_button = FlatButton("×", header)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setFont(font(17, QFont.Normal))
        self.close_button.setToolTip("关闭")
        self.close_button.clicked.connect(QApplication.instance().quit)
        header_layout.addWidget(self.close_button)
        header_layout.addStretch(1)

        clock_column = QVBoxLayout()
        clock_column.setContentsMargins(0, 0, 0, 0)
        clock_column.setSpacing(1)
        clock_column.setAlignment(Qt.AlignRight)
        self.clock_label = QLabel()
        self.clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.clock_label.setFont(font(25, QFont.Bold))
        self.clock_label.setStyleSheet(f"color: {PALETTE['brown']}; background: transparent;")
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.date_label.setFont(font(9))
        self.date_label.setStyleSheet(f"color: {PALETTE['brown_soft']}; background: transparent;")
        self.weather_label = ClickableLabel(self.card)
        self.weather_label.setText("地点 · 获取中…")
        self.weather_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.weather_label.setFont(font(9, QFont.Bold))
        self.weather_label.setStyleSheet(f"color: {PALETTE['orange_dark']}; background: transparent;")
        self.weather_label.setToolTip("点击修改天气地点；联网失败时会显示为 —")
        self.weather_label.clicked.connect(self.open_location_dialog)
        clock_column.addWidget(self.clock_label)
        clock_column.addWidget(self.date_label)
        clock_column.addWidget(self.weather_label)
        header_layout.addLayout(clock_column)
        layout.addWidget(header)

        self.drag_handle = DragHandle(self.card)
        self.drag_handle.setGeometry(154, 0, 78, 58)
        self.drag_handle.drag_started.connect(self.begin_drag)
        self.drag_handle.drag_moved.connect(self.continue_drag)
        self.drag_handle.drag_finished.connect(self.finish_drag)

        self.tabs = QWidget(self.card)
        self.tabs.setFixedHeight(32)
        tabs_layout = QHBoxLayout(self.tabs)
        tabs_layout.setContentsMargins(4, 0, 4, 0)
        tabs_layout.setSpacing(8)
        self.tab_buttons: dict[str, TabButton] = {}
        for key, label in (("todo", "待办"), ("done", "已完成"), ("habit", "打卡")):
            button = TabButton(label, self.tabs)
            button.setFixedHeight(30)
            button.clicked.connect(lambda _checked=False, selected=key: self.change_tab(selected))
            tabs_layout.addWidget(button, 1)
            self.tab_buttons[key] = button
        layout.addWidget(self.tabs)

        self.progress_row = QWidget(self.card)
        self.progress_row.setFixedHeight(22)
        progress_layout = QHBoxLayout(self.progress_row)
        progress_layout.setContentsMargins(4, 0, 4, 0)
        progress_layout.setSpacing(8)
        self.progress_text = QLabel()
        self.progress_text.setFont(font(10, QFont.Bold))
        self.progress_text.setStyleSheet(f"color: {PALETTE['brown_soft']}; background: transparent;")
        progress_layout.addWidget(self.progress_text)
        self.progress_bar = QProgressBar(self.progress_row)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{ background: {PALETTE['peach']}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: {PALETTE['orange']}; border-radius: 3px; }}
            """
        )
        progress_layout.addWidget(self.progress_bar, 1)
        layout.addWidget(self.progress_row)

        self.pages = QStackedWidget(self.card)
        self.todo_page = self.build_todo_page()
        self.habit_page = self.build_habit_page()
        self.memo_page = self.build_memo_page()
        self.pages.addWidget(self.todo_page)
        self.pages.addWidget(self.habit_page)
        self.pages.addWidget(self.memo_page)
        layout.addWidget(self.pages, 1)

        self.render_all()

    def update_memo_rail_geometry(self) -> None:
        if not hasattr(self, "memo_rail") or self.collapsed:
            return
        card_height = max(240, self.height() - FOX_OVERHANG)
        self.memo_rail.setGeometry(
            0,
            FOX_OVERHANG + 60,
            MEMO_RAIL_WIDTH,
            max(160, card_height - 72),
        )

    def create_resize_grips(self) -> None:
        for edges in (
            "top",
            "bottom",
            "left",
            "right",
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
        ):
            grip = ResizeGrip(edges, self)
            grip.resize_started.connect(self.begin_resize)
            grip.resize_moved.connect(self.continue_resize)
            grip.resize_finished.connect(self.finish_resize)
            self.resize_grips[edges] = grip
        self.update_resize_grips()

    def update_resize_grips(self) -> None:
        if not self.resize_grips:
            return
        size = RESIZE_GRIP_SIZE
        width = self.width()
        height = self.height()
        rectangles = {
            "top": QRect(size, 0, max(1, width - size * 2), size),
            "bottom": QRect(size, max(0, height - size), max(1, width - size * 2), size),
            "left": QRect(0, size, size, max(1, height - size * 2)),
            "right": QRect(max(0, width - size), size, size, max(1, height - size * 2)),
            "top_left": QRect(0, 0, size, size),
            "top_right": QRect(max(0, width - size), 0, size, size),
            "bottom_left": QRect(0, max(0, height - size), size, size),
            "bottom_right": QRect(max(0, width - size), max(0, height - size), size, size),
        }
        for edges, grip in self.resize_grips.items():
            grip.setGeometry(rectangles[edges])

    def raise_resize_grips(self) -> None:
        for grip in self.resize_grips.values():
            grip.raise_()

    def set_resize_grips_visible(self, visible: bool) -> None:
        for grip in self.resize_grips.values():
            grip.setVisible(visible and not self.collapsed)

    def begin_resize(self, edges: str, global_pos: QPoint) -> None:
        if self.collapsed or self.dragging:
            return
        self.resizing = True
        self.resize_edges = edges
        self.resize_start_pos = QPoint(global_pos)
        self.resize_start_geometry = QRect(self.geometry())

    def continue_resize(self, global_pos: QPoint) -> None:
        if not self.resizing or self.collapsed:
            return
        delta = global_pos - self.resize_start_pos
        start = self.resize_start_geometry
        left = start.left()
        top = start.top()
        right = start.right()
        bottom = start.bottom()

        if "left" in self.resize_edges:
            left = start.left() + delta.x()
        if "right" in self.resize_edges:
            right = start.right() + delta.x()
        if "top" in self.resize_edges:
            top = start.top() + delta.y()
        if "bottom" in self.resize_edges:
            bottom = start.bottom() + delta.y()

        if right - left + 1 < MIN_WINDOW_WIDTH:
            if "left" in self.resize_edges:
                left = right - MIN_WINDOW_WIDTH + 1
            else:
                right = left + MIN_WINDOW_WIDTH - 1
        if bottom - top + 1 < MIN_WINDOW_HEIGHT:
            if "top" in self.resize_edges:
                top = bottom - MIN_WINDOW_HEIGHT + 1
            else:
                bottom = top + MIN_WINDOW_HEIGHT - 1

        self.setGeometry(QRect(QPoint(left, top), QPoint(right, bottom)))

    def finish_resize(self, global_pos: QPoint) -> None:
        if not self.resizing:
            return
        self.continue_resize(global_pos)
        self.resizing = False
        self.resize_edges = ""

    def build_todo_page(self) -> QWidget:
        page = QWidget(self.card)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(5)

        self.todo_scroll, self.todo_rows_layout = self.build_scroll_area()
        page_layout.addWidget(self.todo_scroll, 1)

        add_bar = QWidget(page)
        add_layout = QHBoxLayout(add_bar)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(5)
        self.todo_input = QLineEdit(add_bar)
        self.todo_input.setPlaceholderText("新增一件小事…")
        self.todo_input.setFont(font(11))
        self.todo_input.setFixedHeight(32)
        self.todo_input.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: {PALETTE['white']}; border: none; border-radius: 15px; padding: 0 12px; }}"
        )
        self.todo_input.returnPressed.connect(self.add_todo)
        add_layout.addWidget(self.todo_input, 1)
        self.todo_add_button = FlatButton("+", add_bar)
        self.todo_add_button.setFixedSize(32, 32)
        self.todo_add_button.setFont(font(20, QFont.Normal))
        self.todo_add_button.setStyleSheet(
            f"""
            QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['orange']}; border: none; border-radius: 16px; }}
            QPushButton:hover {{ background: {PALETTE['orange_dark']}; }}
            """
        )
        self.todo_add_button.clicked.connect(self.add_todo)
        add_layout.addWidget(self.todo_add_button)
        page_layout.addWidget(add_bar)
        return page

    def build_habit_page(self) -> QWidget:
        page = QWidget(self.card)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(5)

        self.habit_scroll, self.habit_rows_layout = self.build_scroll_area()
        page_layout.addWidget(self.habit_scroll, 1)

        add_bar = QWidget(page)
        add_layout = QHBoxLayout(add_bar)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(5)
        self.habit_input = QLineEdit(add_bar)
        self.habit_input.setPlaceholderText("新增打卡习惯…")
        self.habit_input.setFont(font(11))
        self.habit_input.setFixedHeight(32)
        self.habit_input.setStyleSheet(
            f"QLineEdit {{ color: {PALETTE['brown']}; background: {PALETTE['white']}; border: none; border-radius: 15px; padding: 0 12px; }}"
        )
        self.habit_input.returnPressed.connect(self.add_habit)
        add_layout.addWidget(self.habit_input, 1)
        self.habit_add_button = FlatButton("+", add_bar)
        self.habit_add_button.setFixedSize(32, 32)
        self.habit_add_button.setFont(font(20, QFont.Normal))
        self.habit_add_button.setStyleSheet(
            f"""
            QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['mint_dark']}; border: none; border-radius: 16px; }}
            QPushButton:hover {{ background: #467f71; }}
            """
        )
        self.habit_add_button.clicked.connect(self.add_habit)
        add_layout.addWidget(self.habit_add_button)
        page_layout.addWidget(add_bar)
        return page

    def build_memo_page(self) -> QWidget:
        page = QWidget(self.card)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(5)

        header = QWidget(page)
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.memo_back_button = FlatButton("‹ 返回待办", header)
        self.memo_back_button.setFixedSize(88, 28)
        self.memo_back_button.setFont(font(10, QFont.Bold))
        self.memo_back_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['orange_dark']}; background: {PALETTE['peach']}; "
            "border: none; border-radius: 14px; padding: 0 5px; }"
            f"QPushButton:hover {{ background: {PALETTE['line']}; }}"
        )
        self.memo_back_button.clicked.connect(self.exit_memo)
        header_layout.addWidget(self.memo_back_button)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(0)
        self.memo_title = QLabel("备忘")
        self.memo_title.setFont(font(13, QFont.Bold))
        self.memo_title.setStyleSheet(f"color: {PALETTE['brown']}; background: transparent;")
        title_column.addWidget(self.memo_title)

        self.memo_updated = QLabel("最新更新：暂无更新时间")
        self.memo_updated.setFont(font(8))
        self.memo_updated.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        title_column.addWidget(self.memo_updated)
        header_layout.addLayout(title_column, 1)

        self.memo_export_button = FlatButton("工作日志", header)
        self.memo_export_button.setFixedSize(64, 28)
        self.memo_export_button.setFont(font(9, QFont.Bold))
        self.memo_export_button.setToolTip("一键生成今日工作日志")
        self.memo_export_button.setStyleSheet(
            f"QPushButton {{ color: {PALETTE['white']}; background: {PALETTE['mint_dark']}; "
            "border: none; border-radius: 14px; padding: 0; }"
            f"QPushButton:hover {{ background: {PALETTE['orange']}; }}"
        )
        self.memo_export_button.clicked.connect(self.generate_work_log)
        header_layout.addWidget(self.memo_export_button)

        self.memo_status = QLabel("自动保存")
        self.memo_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.memo_status.setFont(font(9))
        self.memo_status.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        header_layout.addWidget(self.memo_status)
        page_layout.addWidget(header)

        self.memo_editor = QPlainTextEdit(page)
        self.memo_editor.setPlaceholderText("把想记住的事情写在这里…")
        self.memo_editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.memo_editor.setFont(font(12))
        self.memo_editor.setStyleSheet(
            f"""
            QPlainTextEdit {{
                color: {PALETTE['brown']};
                background: {PALETTE['white']};
                border: none;
                border-radius: 15px;
                padding: 10px;
                selection-background-color: {PALETTE['peach']};
            }}
            QScrollBar:vertical {{ width: 4px; background: transparent; margin: 4px 0; }}
            QScrollBar::handle:vertical {{ background: {PALETTE['card_shadow']}; border-radius: 2px; min-height: 22px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            """
        )
        self.memo_editor.textChanged.connect(self.on_memo_text_changed)
        page_layout.addWidget(self.memo_editor, 1)
        return page

    def build_scroll_area(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea(self.card)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; margin: 2px 0 2px 2px; }}
            QScrollBar::handle:vertical {{ background: {PALETTE['card_shadow']}; border-radius: 2px; min-height: 22px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            """
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 1, 0)
        content_layout.setSpacing(5)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        return scroll, content_layout

    def change_tab(self, key: str) -> None:
        if self.memo_mode:
            self.save_current_memo()
            self.memo_mode = False
            self.state["memo_mode"] = False
        self.active_tab = key
        self.state["active_tab"] = key
        self.save()
        self.render_all()

    def render_all(self) -> None:
        for key, button in self.tab_buttons.items():
            button.setChecked(key == self.active_tab)
        self.memo_rail.render(self.state["memos"], self.active_memo_id)
        self.render_todos()
        self.render_habits()
        self.update_progress()
        memo_item = self.current_memo()
        if self.memo_mode and memo_item is not None:
            self.tabs.hide()
            self.progress_row.hide()
            self.pages.setCurrentWidget(self.memo_page)
            self.render_memo()
        else:
            self.memo_mode = False
            self.state["memo_mode"] = False
            self.tabs.show()
            self.progress_row.show()
            self.pages.setCurrentWidget(self.habit_page if self.active_tab == "habit" else self.todo_page)

    def current_memo(self) -> dict | None:
        for item in self.state["memos"]:
            if item["id"] == self.active_memo_id:
                return item
        return None

    def render_memo(self) -> None:
        item = self.current_memo()
        if item is None:
            return
        self.memo_title.setText(item["label"])
        self.memo_updated.setText(f"最新更新：{format_memo_timestamp(item.get('updated_at', ''))}")
        self.memo_editor.blockSignals(True)
        self.memo_editor.setPlainText(item.get("content", ""))
        self.memo_editor.blockSignals(False)
        self.memo_status.setText("自动保存")

    def enter_memo(self, memo_id: str) -> None:
        if self.memo_mode:
            self.save_current_memo()
        self.active_memo_id = memo_id
        self.memo_mode = True
        self.state["active_memo_id"] = memo_id
        self.state["memo_mode"] = True
        self.save()
        self.render_all()
        self.memo_editor.setFocus()

    def exit_memo(self) -> None:
        self.save_current_memo()
        self.memo_mode = False
        self.state["memo_mode"] = False
        self.save()
        self.render_all()

    def add_memo(self, label: str) -> None:
        if self.memo_mode:
            self.save_current_memo()
        item = {
            "id": new_id(),
            "label": label.strip() or "新备忘",
            "content": "",
            "updated_at": memo_timestamp(),
        }
        self.state["memos"].append(item)
        self.active_memo_id = item["id"]
        self.memo_mode = True
        self.state["active_memo_id"] = self.active_memo_id
        self.state["memo_mode"] = True
        self.save()
        self.render_all()
        self.memo_editor.setFocus()

    def rename_memo(self, memo_id: str, label: str) -> None:
        label = label.strip()
        if not label:
            return
        for item in self.state["memos"]:
            if item["id"] == memo_id:
                item["label"] = label
                item["updated_at"] = memo_timestamp()
                break
        self.save()
        self.render_all()

    def remove_memo(self, memo_id: str) -> None:
        if memo_id == self.active_memo_id:
            self.save_current_memo()
        self.state["memos"] = [item for item in self.state["memos"] if item["id"] != memo_id]
        if memo_id == self.active_memo_id:
            next_item = self.state["memos"][0] if self.state["memos"] else None
            self.active_memo_id = next_item["id"] if next_item else None
            self.memo_mode = next_item is not None
        self.state["active_memo_id"] = self.active_memo_id
        self.state["memo_mode"] = self.memo_mode
        self.save()
        self.render_all()

    def on_memo_text_changed(self) -> None:
        self.memo_status.setText("正在保存…")
        if self.memo_save_timer is not None:
            self.memo_save_timer.start(350)

    def render_todos(self) -> None:
        clear_layout(self.todo_rows_layout)
        visible = [
            item
            for item in self.state["todos"]
            if self.active_tab == "todo" and not item["done"] or self.active_tab == "done" and item["done"]
        ]
        if not visible:
            empty = QLabel("这里还没有内容，先记下一件小事吧")
            empty.setAlignment(Qt.AlignCenter)
            empty.setFont(font(10))
            empty.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
            self.todo_rows_layout.insertWidget(0, empty)
        else:
            for item in visible:
                row = TodoRow(item)
                row.toggled.connect(self.toggle_todo)
                row.text_changed.connect(self.edit_todo)
                row.removed.connect(self.remove_todo)
                self.todo_rows_layout.insertWidget(self.todo_rows_layout.count() - 1, row)
        self.todo_rows_layout.addStretch(1)

    def render_habits(self) -> None:
        clear_layout(self.habit_rows_layout)
        habits = self.state["habits"]
        if not habits:
            empty = QLabel("每周想坚持什么？在下面添加吧")
            empty.setAlignment(Qt.AlignCenter)
            empty.setFont(font(10))
            empty.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
            self.habit_rows_layout.insertWidget(0, empty)
        else:
            for item in habits:
                row = HabitRow(item)
                row.day_changed.connect(self.toggle_habit_day)
                row.name_changed.connect(self.edit_habit)
                row.removed.connect(self.remove_habit)
                self.habit_rows_layout.insertWidget(self.habit_rows_layout.count() - 1, row)
        self.habit_rows_layout.addStretch(1)

    def update_progress(self) -> None:
        todos = self.state["todos"]
        total = len(todos)
        done = sum(1 for item in todos if item["done"])
        self.progress_text.setText(f"完成 {done}/{total}")
        self.progress_bar.setValue(round(done * 100 / total) if total else 0)

    def save(self) -> None:
        save_state(self.state)

    def save_current_memo(self) -> None:
        if self.memo_save_timer is not None:
            self.memo_save_timer.stop()
        item = self.current_memo()
        if item is None:
            return
        content = self.memo_editor.toPlainText()
        if item.get("content", "") != content:
            item["content"] = content
            item["updated_at"] = memo_timestamp()
        self.save()
        if hasattr(self, "memo_status"):
            self.memo_status.setText("已保存")

    def generate_work_log(self) -> None:
        """Generate a dated Markdown work log from all memo entries."""
        self.save_current_memo()
        memos = self.state.get("memos", [])
        if not memos:
            self.memo_status.setText("暂无记录")
            return

        log_time = datetime.now()
        weekdays = "一二三四五六日"
        date_text = log_time.strftime("%Y年%m月%d日")
        filename = f"工作日志-{log_time.strftime('%Y%m%d')}.md"
        path = os.path.join(EXPORT_DIR, filename)
        lines = [
            f"# 工作日志｜{date_text} 星期{weekdays[log_time.weekday()]}",
            "",
            f"> 生成时间：{log_time.strftime('%Y年%m月%d日 %H:%M')}",
            f"> 记录条目：{len(memos)} 条",
            "",
            "## 今日工作记录",
            "",
        ]
        for item in memos:
            lines.extend(
                [
                    f"## {item.get('label', '未命名备忘')}",
                    f"**最新更新时间：{format_memo_timestamp(item.get('updated_at', ''))}**",
                    "",
                    item.get("content", "").strip() or "（暂无内容）",
                    "",
                    "---",
                    "",
                ]
            )

        try:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
        except OSError:
            self.memo_status.setText("生成失败")
            return

        self.memo_status.setText("已生成")
        self.memo_status.setToolTip(f"工作日志位置：{path}")

    def add_todo(self) -> None:
        text = self.todo_input.text().strip()
        if not text:
            return
        self.state["todos"].append({"id": new_id(), "text": text, "done": False})
        self.todo_input.clear()
        self.active_tab = "todo"
        self.state["active_tab"] = "todo"
        self.save()
        self.render_all()

    def toggle_todo(self, item_id: str, done: bool) -> None:
        for item in self.state["todos"]:
            if item["id"] == item_id:
                item["done"] = bool(done)
                break
        self.save()
        self.render_all()

    def edit_todo(self, item_id: str, text: str) -> None:
        for item in self.state["todos"]:
            if item["id"] == item_id:
                if text:
                    item["text"] = text
                break
        self.save()
        self.render_all()

    def remove_todo(self, item_id: str) -> None:
        self.state["todos"] = [item for item in self.state["todos"] if item["id"] != item_id]
        self.save()
        self.render_all()

    def add_habit(self) -> None:
        name = self.habit_input.text().strip()
        if not name:
            return
        self.state["habits"].append({"id": new_id(), "name": name, "days": [False] * 7})
        self.habit_input.clear()
        self.active_tab = "habit"
        self.state["active_tab"] = "habit"
        self.save()
        self.render_all()

    def toggle_habit_day(self, item_id: str, day: int, checked: bool) -> None:
        for item in self.state["habits"]:
            if item["id"] == item_id:
                item["days"][day] = bool(checked)
                break
        self.save()

    def edit_habit(self, item_id: str, name: str) -> None:
        for item in self.state["habits"]:
            if item["id"] == item_id:
                if name:
                    item["name"] = name
                break
        self.save()
        self.render_all()

    def remove_habit(self, item_id: str) -> None:
        self.state["habits"] = [item for item in self.state["habits"] if item["id"] != item_id]
        self.save()
        self.render_all()

    def update_clock(self) -> None:
        now = datetime.now()
        weekdays = "一二三四五六日"
        self.clock_label.setText(now.strftime("%H:%M"))
        self.date_label.setText(now.strftime("%Y-%m-%d") + f"  周{weekdays[now.weekday()]}")
        if self.bubble.isVisible():
            self.update_bubble_text()

    def ensure_location(self) -> None:
        if self.location is not None:
            return
        dialog = LocationDialog(self, DEFAULT_LOCATION)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_location is not None:
            self.apply_location(dialog.selected_location)
        else:
            self.apply_location(DEFAULT_LOCATION)

    def open_location_dialog(self) -> None:
        dialog = LocationDialog(self, self.location or DEFAULT_LOCATION)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_location is not None:
            self.apply_location(dialog.selected_location)

    def apply_location(self, location: dict) -> None:
        normalized = normalize_location(location)
        if normalized is None:
            return
        self.location = normalized
        self.state["location"] = normalized
        self.weather_location = normalized["name"]
        self.weather_latitude = normalized["latitude"]
        self.weather_longitude = normalized["longitude"]
        self.weather_condition = ""
        self.save()
        self.update_weather_label()
        self.refresh_weather()

    def refresh_weather(self) -> None:
        """Read current weather for the selected city."""
        if self.weather_reply is not None and self.weather_reply.isRunning():
            return
        request = QNetworkRequest(
            QUrl(
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={self.weather_latitude}&longitude={self.weather_longitude}"
                "&current=temperature_2m,weather_code&timezone=Asia%2FShanghai"
            )
        )
        request.setRawHeader(b"User-Agent", b"FoxTodoWidget/1.0")
        self.weather_reply = self.weather_manager.get(request)
        self.weather_reply.finished.connect(self.on_weather_finished)

    def update_weather_label(self) -> None:
        condition = self.weather_condition or "获取中…"
        self.weather_label.setText(f"{self.weather_location} · {condition}")
        self.weather_label.setToolTip(
            f"天气地点：{self.weather_location}；点击可切换城市"
        )

    def on_weather_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return

        try:
            if reply.error() != QNetworkReply.NoError:
                raise ValueError("weather request failed")
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            current = payload.get("current") or {}
            weather_code = int(current.get("weather_code", -1))
            code_map = {
                0: ("☀", "晴"),
                1: ("⛅", "少云"),
                2: ("⛅", "多云"),
                3: ("☁", "阴"),
                45: ("☁", "雾"),
                48: ("☁", "雾"),
                51: ("☂", "毛毛雨"),
                53: ("☂", "毛毛雨"),
                55: ("☂", "毛毛雨"),
                56: ("☂", "冻雨"),
                57: ("☂", "冻雨"),
                61: ("☂", "小雨"),
                63: ("☂", "中雨"),
                65: ("☂", "大雨"),
                66: ("☂", "冻雨"),
                67: ("☂", "冻雨"),
                71: ("❄", "小雪"),
                73: ("❄", "中雪"),
                75: ("❄", "大雪"),
                77: ("❄", "雪粒"),
                80: ("☂", "阵雨"),
                81: ("☂", "阵雨"),
                82: ("☂", "强阵雨"),
                85: ("❄", "阵雪"),
                86: ("❄", "阵雪"),
                95: ("⚡", "雷雨"),
                96: ("⚡", "雷雨冰雹"),
                99: ("⚡", "雷雨冰雹"),
            }
            icon, condition = code_map.get(weather_code, ("☁", "天气未知"))
            temperature = current.get("temperature_2m")
            suffix = ""
            if temperature is not None:
                suffix = f" {float(temperature):.1f}°C"
                suffix = suffix.replace(".0°C", "°C")
            self.weather_condition = f"{icon} {condition}{suffix}"
            self.update_weather_label()
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            self.weather_condition = "—"
            self.update_weather_label()
        finally:
            if self.weather_reply is reply:
                self.weather_reply = None
            reply.deleteLater()

    def update_bubble_text(self) -> None:
        now = datetime.now()
        target = now.replace(hour=18, minute=30, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        remaining = target - now
        total_seconds = max(0, int(remaining.total_seconds()))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        quote = random.choice(
            [
                "稳稳攒下每一步～",
                "再做一件小事，就更接近下班啦！",
                "钱来，灵感也来！",
                "今天也要轻轻松松完成呀。",
            ]
        )
        self.bubble.title.setText("距离下班")
        self.bubble.body.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}  ·  {quote}")

    def on_character_clicked(self) -> None:
        if self.collapsed:
            self.restore_window()
            return
        self.update_bubble_text()
        self.bubble.show()
        self.bubble.raise_()
        if self.bubble_timer is not None:
            self.bubble_timer.stop()
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.bubble.hide)
        self.bubble_timer.start(5000)

    def start_effects(self) -> None:
        if self.effect_started or not self.character_pixmaps:
            return
        self.effect_started = True
        self.float_timer = QTimer(self)
        self.float_timer.timeout.connect(self.update_float)
        self.float_timer.start(180)

        self.money_effect.show()
        self.money_effect.raise_()
        self.money_effect.start()

        self.carousel_timer = QTimer(self)
        self.carousel_timer.timeout.connect(self.next_character_frame)
        self.carousel_timer.start(7200)
        self.schedule_blink()

    def update_float(self) -> None:
        if self.collapsed:
            return
        offset = round(math.sin(self.float_phase) * 2.0)
        self.character.move(MEMO_RAIL_WIDTH + 3, offset)
        self.float_phase += 0.11

    def set_character_frame(self, index: int, update_carousel: bool = True) -> None:
        if not self.character_pixmaps:
            return
        frame_index = index % len(self.character_pixmaps)
        if update_carousel:
            self.carousel_index = frame_index
        pixmap = self.character_pixmaps[frame_index]
        self.character.setPixmap(
            pixmap.scaled(self.character.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def next_character_frame(self) -> None:
        self.set_character_frame(self.carousel_index + 1)

    def schedule_blink(self) -> None:
        if not self.effect_started:
            return
        delay = random.randint(3600, 6400)
        QTimer.singleShot(delay, self.do_blink)

    def do_blink(self) -> None:
        if not self.effect_started:
            return
        carousel_frame = self.carousel_index
        blink_frame = 1 if len(self.character_pixmaps) > 1 and random.random() < 0.55 else 2
        if blink_frame >= len(self.character_pixmaps):
            blink_frame = 0
        self.set_character_frame(blink_frame, update_carousel=False)
        QTimer.singleShot(230, lambda: self.set_character_frame(carousel_frame, update_carousel=False))
        self.schedule_blink()

    def begin_drag(self, global_pos: QPoint) -> None:
        if self.collapsed or self.resizing:
            return
        self.dragging = True
        self.drag_offset = global_pos - self.frameGeometry().topLeft()
        self.setCursor(Qt.ClosedHandCursor)

    def continue_drag(self, global_pos: QPoint) -> None:
        if self.dragging and not self.collapsed:
            self.move(global_pos - self.drag_offset)

    def finish_drag(self, global_pos: QPoint) -> None:
        if not self.dragging:
            return
        self.dragging = False
        self.setCursor(Qt.ArrowCursor)
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        current = self.frameGeometry()
        if current.left() <= available.left() + 9:
            self.collapse_to_edge("left")
        elif current.right() >= available.right() - 9:
            self.collapse_to_edge("right")
        elif current.top() <= available.top() + 9:
            self.collapse_to_edge("top")
        elif current.bottom() >= available.bottom() - 9:
            self.collapse_to_edge("bottom")

    def collapse_to_edge(self, side: str) -> None:
        if self.collapsed:
            return
        self.last_full_pos = self.pos()
        self.collapsed = True
        self.collapsed_side = side
        self.resizing = False
        self.set_resize_grips_visible(False)
        self.bubble.hide()
        self.money_effect.stop()
        self.money_effect.hide()
        self.bookmark.hide()
        self.memo_rail.hide()
        self.card.hide()
        # Keep the whole fox inside the compact window.  The old implementation
        # deliberately left most of this window outside the screen edge, which
        # made the collapsed state look like a pair of ears.
        self.resize(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        self.character.setGeometry(0, 0, COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        self.set_character_frame(self.carousel_index)
        self.character.raise_()
        screen = QApplication.screenAt(self.last_full_pos) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        margin = COLLAPSED_MARGIN
        min_x = available.left() + margin
        max_x = available.right() - self.width() + 1 - margin
        min_y = available.top() + margin
        max_y = available.bottom() - self.height() + 1 - margin
        x = max(min_x, min(self.x(), max_x))
        y = max(min_y, min(self.y(), max_y))
        if side == "left":
            x = min_x
        elif side == "right":
            x = max_x
        if side == "top":
            y = min_y
        elif side == "bottom":
            y = max_y
        self.move(x, y)
        self.raise_()

    def restore_window(self) -> None:
        if not self.collapsed:
            return
        self.collapsed = False
        self.resize(CARD_WIDTH + MEMO_RAIL_WIDTH, WINDOW_HEIGHT)
        self.card.setGeometry(
            MEMO_RAIL_WIDTH,
            FOX_OVERHANG,
            CARD_WIDTH,
            CARD_HEIGHT,
        )
        self.card.show()
        self.memo_rail.show()
        self.update_memo_rail_geometry()
        self.character.setGeometry(MEMO_RAIL_WIDTH + 3, 0, 112, 112)
        self.money_effect.setGeometry(MEMO_RAIL_WIDTH, 0, CARD_WIDTH, WINDOW_HEIGHT)
        self.money_effect.show()
        self.character.raise_()
        self.money_effect.raise_()
        self.memo_rail.raise_()
        self.money_effect.start()
        self.set_character_frame(self.carousel_index)
        self.set_resize_grips_visible(True)
        self.raise_resize_grips()
        target = self.last_full_pos or self.default_position()
        screen = QApplication.screenAt(target) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        x = max(available.left(), min(target.x(), available.right() - self.width() + 1))
        y = max(available.top(), min(target.y(), available.bottom() - self.height() + 1))
        self.move(x, y)
        self.raise_()
        self.activateWindow()

    def restore_and_raise(self) -> None:
        if self.collapsed:
            self.restore_window()
        else:
            self.raise_()
            self.activateWindow()
            self.showNormal()

    def default_position(self) -> QPoint:
        screen = QApplication.primaryScreen().availableGeometry()
        return QPoint(screen.right() - self.width() - 24, screen.top() + 38)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self.last_full_pos is None:
            self.move(self.default_position())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "card") and not self.collapsed:
            card_width = max(MIN_CARD_WIDTH, self.width() - MEMO_RAIL_WIDTH)
            self.card.setGeometry(
                MEMO_RAIL_WIDTH,
                FOX_OVERHANG,
                card_width,
                max(240, self.height() - FOX_OVERHANG),
            )
            self.update_memo_rail_geometry()
        if hasattr(self, "character") and not self.collapsed:
            self.character.setGeometry(MEMO_RAIL_WIDTH + 3, 0, 112, 112)
            self.set_character_frame(self.carousel_index)
        if hasattr(self, "money_effect") and not self.collapsed:
            card_width = max(MIN_CARD_WIDTH, self.width() - MEMO_RAIL_WIDTH)
            self.money_effect.setGeometry(MEMO_RAIL_WIDTH, 0, card_width, self.height())
        if hasattr(self, "resize_grips"):
            self.update_resize_grips()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.save_current_memo()
        self.save()
        super().closeEvent(event)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("狐狸待办小组件")
    app.setQuitOnLastWindowClosed(True)

    guard = InstanceGuard(app)
    if guard.already_running:
        return 0

    window = MainWindow(load_state(), guard)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
