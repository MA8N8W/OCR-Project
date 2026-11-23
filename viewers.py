import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QGuiApplication,
    QIcon,
    QPalette,
    QPixmap,
    QTextCursor,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from pdfjs_viewer import PDFViewerWidget


class BaseViewer(QWidget):
    closed_requested = pyqtSignal(str)

    def __init__(self, stage_id: str, title: str, parent=None):
        super().__init__(parent)
        self.stage_id = stage_id

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)

        self.header = QWidget()
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(6, 2, 6, 2)

        self.title_label = QLabel(f"<b>{title}</b>")
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()

        self.toolbar_slot = QHBoxLayout()
        self.header_layout.addLayout(self.toolbar_slot)

        self.hide_btn = QPushButton("X")
        self.hide_btn.setFixedWidth(26)
        self.hide_btn.setToolTip("Hide View")
        self.hide_btn.clicked.connect(self.deactivate_view)
        self.header_layout.addWidget(self.hide_btn)

        self.main_layout.addWidget(self.header)

    def set_content_widget(self, widget: QWidget):
        self.main_layout.addWidget(widget, stretch=1)

    def deactivate_view(self):
        self.hide()
        self.closed_requested.emit(self.stage_id)

    def activate_view(self):
        self.show()

class ZoomableTextBrowser(QTextBrowser):
    """QTextBrowser that zooms text only when Ctrl is held while scrolling."""

    def wheelEvent(self, event: QWheelEvent):
        if (
            self.underMouse()
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoomIn(1)
            elif delta < 0:
                self.zoomOut(1)
            event.accept()
            return

        # Normal scrolling when Ctrl is not pressed
        super().wheelEvent(event)

class ZoomableImageCanvas(QGraphicsView):
    """QGraphicsView with Ctrl+Wheel zoom and click-drag panning."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def load_image(self, file_path: str):
        pixmap = QPixmap(file_path)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent):
        if (
            self.underMouse()
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return

        # Normal scrolling when Ctrl is not pressed
        super().wheelEvent(event)

class MDViewer(BaseViewer):
    """Displays Markdown output with formatting toggle, Ctrl+zoom, and block sync."""

    # Emits (stage_id, block_number, intra_block_ratio)
    scroll_block_changed = pyqtSignal(str, int, float)

    def __init__(self, stage_id: str, title: str, parent=None):
        super().__init__(stage_id, title, parent)
        self._raw_markdown = ""
        self._is_formatted = True
        self._is_syncing = False  # Prevents feedback loops

        self.toggle_md_btn = QPushButton("Raw MD")
        self.toggle_md_btn.setCheckable(True)
        self.toggle_md_btn.clicked.connect(self._on_toggle_format)
        self.toolbar_slot.addWidget(self.toggle_md_btn)

        self.browser = ZoomableTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.set_content_widget(self.browser)

        # Listen to user scrollbar movement
        self.browser.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_content(self, markdown_text: str):
        self._raw_markdown = markdown_text
        self._render()

    def _on_toggle_format(self, checked: bool):
        self._is_formatted = not checked
        self.toggle_md_btn.setText("Formatted" if checked else "Raw MD")
        self._render()

    def _render(self):
        self._is_syncing = True
        v_scroll = self.browser.verticalScrollBar().value()
        if self._is_formatted:
            self.browser.setMarkdown(self._raw_markdown)
        else:
            self.browser.setPlainText(self._raw_markdown)
        self.browser.verticalScrollBar().setValue(v_scroll)
        self._is_syncing = False

    def _on_scroll(self, _value: int):
        if self._is_syncing:
            return

        vbar = self.browser.verticalScrollBar()
        # Handle exact top or bottom edge cleanly
        if vbar.maximum() == 0 or vbar.value() == 0:
            self.scroll_block_changed.emit(self.stage_id, 0, 0.0)
            return
        if vbar.value() >= vbar.maximum():
            total_blocks = self.browser.document().blockCount()
            self.scroll_block_changed.emit(self.stage_id, max(0, total_blocks - 1), 1.0)
            return

        # Find the QTextBlock at the top-left of the visible viewport
        cursor = self.browser.cursorForPosition(QPoint(0, 0))
        block = cursor.block()
        block_rect = self.browser.cursorRect(cursor)

        # Calculate how far into this specific block we have scrolled (0.0 to 1.0)
        block_height = max(1, block_rect.height())
        intra_ratio = min(1.0, max(0.0, -block_rect.top() / block_height))

        self.scroll_block_changed.emit(self.stage_id, block.blockNumber(), intra_ratio)

    def sync_to_block(self, source_block_num: int, source_total_blocks: int, intra_ratio: float):
        """Scrolls this viewer to the matching block index without re-emitting signals."""
        self._is_syncing = True
        try:
            doc = self.browser.document()
            target_total = doc.blockCount()
            if target_total == 0:
                return

            # Scale block index proportionally in case LLM slightly merged/split a line
            if source_total_blocks > 1 and target_total != source_total_blocks:
                ratio = source_block_num / (source_total_blocks - 1)
                target_idx = round(ratio * (target_total - 1))
            else:
                target_idx = min(source_block_num, target_total - 1)

            target_block = doc.findBlockByNumber(target_idx)
            if not target_block.isValid():
                return

            # Move cursor to target block to compute its vertical Y coordinate
            cursor = QTextCursor(target_block)
            rect = self.browser.cursorRect(cursor)

            vbar = self.browser.verticalScrollBar()
            offset = int(rect.height() * intra_ratio)
            new_scroll = vbar.value() + rect.top() + offset
            vbar.setValue(max(0, min(vbar.maximum(), new_scroll)))
        finally:
            self._is_syncing = False

class InputViewer(BaseViewer):
    """Switches seamlessly between QGraphicsView (images) and the bundled PDF.js widget."""

    def __init__(self, parent=None):
        super().__init__("input", "1. Source Document", parent)

        self.stack = QStackedWidget()

        # Page 0: Image Viewer
        self.image_view = ZoomableImageCanvas()
        self.stack.addWidget(self.image_view)

        # Page 1: bundled PDF.js widget
        self.pdf_view = PDFViewerWidget(preset="kiosk")
        self.stack.addWidget(self.pdf_view)

        self.set_content_widget(self.stack)

    def load_file(self, file_path: str):
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            self.stack.setCurrentWidget(self.pdf_view)
            self.pdf_view.load_pdf(file_path)
        else:
            self.stack.setCurrentWidget(self.image_view)
            self.image_view.load_image(file_path)



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Docling OCR & Translation Pipeline")
        self.resize(1400, 800)

        self.sync_scroll_enabled = True
        self.sync_btn = QPushButton("Synced Scrolling")
        self.sync_btn.setCheckable(True)
        self.sync_btn.setChecked(True)
        self.sync_btn.toggled.connect(self._toggle_sync_scroll)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # Top Toggle Bar for the 4 Views
        toggle_bar = QHBoxLayout()
        toggle_bar.addWidget(self.sync_btn)
        root_layout.addLayout(toggle_bar)

        # Splitter holding all 4 viewers side by side
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(self.splitter, stretch=1)

        # Instantiate the 4 views (ensure BaseStageViewer matches your base class name)
        self.viewers: dict[str, BaseViewer] = {
            "view_input": InputViewer(),
            "view_ocr": MDViewer("ocr", "OCR Output"),
            "view_translation": MDViewer("mt", "Initial Translation"),
            "view_verification": MDViewer("llm", "LLM Verified Translation"),
        }

        self.toggle_buttons: dict[str, QPushButton] = {}

        for stage_id, viewer in self.viewers.items():
            self.splitter.addWidget(viewer)
            viewer.closed_requested.connect(self._sync_toggle_button)

            btn = QPushButton(viewer.title_label.text().replace("<b>", "").replace("</b>", ""))
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.toggled.connect(lambda checked, v=viewer: v.setVisible(checked))
            toggle_bar.addWidget(btn)
            self.toggle_buttons[stage_id] = btn

        # Wire up synchronized scrolling across the 3 MDViewers
        self.md_viewers: list[MDViewer] = [
            self.viewers["view_ocr"],
            self.viewers["view_translation"],
            self.viewers["view_verification"],
        ]
        for md_view in self.md_viewers:
            md_view.scroll_block_changed.connect(self._on_md_scrolled)

        # Populate sample Markdown data
        self.viewers["view_ocr"].set_content("# OCR Result\n\nExtracted text from **Docling**.")
        self.viewers["view_translation"].set_content("# Machine Translation\n\nNon-context-aware output.")
        self.viewers["view_verification"].set_content("# Verified Output\n\nContext-aware **LLM pass**.")

    def _sync_toggle_button(self, stage_id: str):
        self.toggle_buttons[stage_id].setChecked(False)

    def _toggle_sync_scroll(self, checked: bool):
        self.sync_scroll_enabled = checked

    def _on_md_scrolled(self, source_id: str, block_num: int, intra_ratio: float):
        if not self.sync_scroll_enabled:
            return

        source_viewer: MDViewer = self.viewers[source_id]
        source_total = source_viewer.browser.document().blockCount()

        for target_viewer in self.md_viewers:
            if target_viewer.stage_id != source_id and target_viewer.isVisible():
                target_viewer.sync_to_block(block_num, source_total, intra_ratio)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())