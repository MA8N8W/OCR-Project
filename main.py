import os
import sys
import tempfile
import webbrowser
from pathlib import Path

#from annotated_types import doc
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    EasyOcrOptions,
    #OcrEngine,
    OcrOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)
from PyQt6.QtCore import QCoreApplication, QSettings, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QGuiApplication, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from viewers import BaseViewer, InputViewer, MDViewer

def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

class Config:
    def __init__(self):
        self.app_root = get_app_root()
        self.ini_path = self.app_root / "config.ini"
        self.settings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)

    def has_config_file(self) -> bool:
        return self.ini_path.is_file()

class OCRWorker(QThread):
    completed = pyqtSignal(bool, str)

    def __init__(self, input_path: str, output_path: str, selected_engine, selected_config):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.selected_engine = selected_engine
        self.selected_config = selected_config
        #self.selected_lang = selected_lang

    def run(self):
        try:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True

            if self.selected_engine == "TesseractCLI":
                ocr_opts = TesseractCliOcrOptions(force_full_page_ocr=True)
                device = AcceleratorDevice.CPU

            elif self.selected_engine == "EasyOCR":
                use_cuda = self.selected_config == "cuda"
                ocr_opts = EasyOcrOptions(
                    force_full_page_ocr=True,
                    use_gpu=use_cuda,
                )
                device = AcceleratorDevice.CUDA if use_cuda else AcceleratorDevice.CPU
            
            elif self.selected_engine == "RapidOCR":
                '''ocr_opts = RapidOcrOptions(
                    force_full_page_ocr=True,
                    backend=self.selected_config
                    lang=list(self.selected_lang)
                )'''
                rapid_params = {}
                if self.selected_config == "openvino":
                    rapid_params["EngineConfig.openvino.inference_num_threads"] = 4
                    device = AcceleratorDevice.CPU
                elif self.selected_config == "torch":
                    device = AcceleratorDevice.CUDA
                else:
                    device = AcceleratorDevice.CPU

                ocr_opts = RapidOcrOptions(
                    force_full_page_ocr=True,
                    backend=self.selected_config,
                    rapidocr_params=rapid_params,
                )
            
            else:
                raise ValueError(f"Unsupported OCR engine: {self.selected_engine}")

            pipeline_options.ocr_options = ocr_opts
            pipeline_options.accelerator_options = AcceleratorOptions(
                num_threads=4,
                device=device,
            )

            converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    ),
                    InputFormat.IMAGE: ImageFormatOption(
                        pipeline_options=pipeline_options
                    ),
                },
            )

            result = converter.convert(self.input_path)
            result.document.save_as_json(self.output_path)
            self.completed.emit(True, self.output_path)
        except Exception as e:
            output_path = Path(self.output_path)
            try:
                if output_path.exists():
                    output_path.unlink()
            except OSError as cleanup_error:
                self.completed.emit(
                    False,
                    f"{e}; failed to remove incomplete OCR JSON: {cleanup_error}",
                )
            else:
                self.completed.emit(False, str(e))

class TranslationWorker(QThread):
    finished = pyqtSignal(bool,str)

    def __init__(self):
            super().__init__()

class VerificationWorker(QThread):
    finished = pyqtSignal(bool,str)

    def __init__(self):
        super().__init__()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        palette = QGuiApplication.palette()
        self.accent_color = palette.color(QPalette.ColorRole.Accent)
        self.fallback_color = palette.color(QPalette.ColorRole.Highlight)
        self.accent_hex = self.accent_color.name()

        self.input_path: str | None = None
        self.ocr_json_path: Path | None = None
        self.ocr_running: bool = False
        self.sync_scroll_enabled = False
        self._ocr_temp_dir = tempfile.TemporaryDirectory(prefix="docling-ocr-")
        self.config = Config()
        self.setWindowTitle("Document Scanning & Translation")
        self.setGeometry(100, 100, 1400, 800)

        self.statusBar().showMessage("Welcome!")

        menu = self.menuBar()


        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        #left_panel_content = QLabel("Left Panel Content Here")
        #right_panel_content = QLabel("Right Panel Content Here")

        #left_panel_layout = QVBoxLayout()
        #right_panel_layout = QVBoxLayout()

        #left_panel = QGroupBox("Document")
        #left_panel.setLayout(left_panel_layout)
        #left_panel.layout().addWidget(left_panel_content)

        #right_panel = QGroupBox("OCR Result")
        #right_panel.setLayout(right_panel_layout)
        #right_panel.layout().addWidget(right_panel_content)



        #splitter.addWidget(left_panel)
        #splitter.addWidget(right_panel)

        #splitter.setSizes([400, 400])
        self.splitter.setHandleWidth(1)

        self.setCentralWidget(self.splitter)

        button_open = QAction("&Open", self)
        button_open.triggered.connect(self.open_triggered)
        self.open_action = button_open

        button_load_ocr_json = QAction("Load OCR JSON...", self)
        button_load_ocr_json.triggered.connect(self.load_ocr_json_triggered)
        self.load_ocr_json_action = button_load_ocr_json

        button_save = QAction("&Save", self)
        button_save.triggered.connect(self.save_triggered)
        button_save.setDisabled(True)
        self.save_action = button_save

        button_exit = QAction("&Exit", self)
        button_exit.triggered.connect(QApplication.instance().quit)

        button_home = QAction("&Home", self)
        button_home.triggered.connect(self.home_triggered)

        button_issues = QAction("&Issues", self)
        button_issues.triggered.connect(self.issues_triggered)

        button_about = QAction("&About", self)
        button_about.triggered.connect(self.about_triggered)

        file_menu = menu.addMenu("&File")
        file_menu.addAction(button_open)
        file_menu.addAction(button_load_ocr_json)
        file_menu.addAction(button_save)
        file_menu.addSeparator()
        file_menu.addAction(button_exit)

        about_menu = menu.addMenu("&About")
        about_menu.addAction(button_home)
        about_menu.addAction(button_issues)
        about_menu.addSeparator()
        about_menu.addAction(button_about)

        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.setFixedWidth(90)
        self.ocr_engine_combo.addItems([
            "TesseractCLI",
            "EasyOCR",
            "RapidOCR",
        ])
        self.ocr_engine_combo.currentTextChanged.connect(self.on_engine_changed)

        self.ocr_config_combo = QComboBox()
        self.ocr_config_combo.setFixedWidth(90)
        self.ocr_config_combo.setDisabled(True)

        self.ocr_hint_combo = QComboBox()
        self.ocr_hint_combo.setFixedWidth(90)
        self.ocr_hint_combo.setDisabled(True)

        self.ocr_start_button = QPushButton("Start")
        self.ocr_start_button.clicked.connect(self.start_ocr_clicked)
        self.ocr_start_button.setDisabled(True)
        
        self.translation_language_combo = QComboBox()
        self.translation_language_combo.setFixedWidth(90)
        self.translation_language_combo.setDisabled(True)

        self.translation_start_button = QPushButton("Start")
        self.translation_start_button.setDisabled(True)

        self.view_button_1 = QPushButton("1")
        self.view_button_1.setFixedWidth(25)
        self.view_button_2 = QPushButton("2")
        self.view_button_2.setFixedWidth(25)
        self.view_button_3 = QPushButton("3")
        self.view_button_3.setFixedWidth(25)
        self.view_button_4 = QPushButton("4")
        self.view_button_4.setFixedWidth(25)
        self.view_button_1.setCheckable(True)
        self.view_button_1.setChecked(True)
        self.view_button_2.setCheckable(True)
        self.view_button_3.setCheckable(True)
        self.view_button_4.setCheckable(True)
        self.view_synced_scrolling = QPushButton("Synced Scrolling")
        self.view_synced_scrolling.setCheckable(True)
        self.view_synced_scrolling.setChecked(False)
        self.view_synced_scrolling.toggled.connect(self._toggle_sync_scroll)

        self.input_viewer = InputViewer()
        self.ocr_viewer = MDViewer("ocr", "2. OCR Output")
        self.translation_viewer = MDViewer("mt", "3. Initial Translation")
        self.verification_viewer = MDViewer("llm", "4. LLM Verified Translation")
        self.viewers: dict[str, BaseViewer] = {
            "input": self.input_viewer,
            "ocr": self.ocr_viewer,
            "mt": self.translation_viewer,
            "llm": self.verification_viewer,
        }
        self.view_toggle_buttons: dict[str, QPushButton] = {
            "input": self.view_button_1,
            "ocr": self.view_button_2,
            "mt": self.view_button_3,
            "llm": self.view_button_4,
        }
        self.md_viewers: list[MDViewer] = [
            self.ocr_viewer,
            self.translation_viewer,
            self.verification_viewer,
        ]
        self.md_viewers_by_stage: dict[str, MDViewer] = {
            viewer.stage_id: viewer for viewer in self.md_viewers
        }

        for stage_id, viewer in self.viewers.items():
            self.splitter.addWidget(viewer)
            viewer.closed_requested.connect(self._sync_view_toggle)
            self.view_toggle_buttons[stage_id].toggled.connect(viewer.setVisible)
            viewer.setVisible(self.view_toggle_buttons[stage_id].isChecked())
        self.splitter.setSizes([500, 300, 300, 300])

        for markdown_viewer in self.md_viewers:
            markdown_viewer.scroll_block_changed.connect(self._on_md_scrolled)

        toolbar_groupbox_ocr = QGroupBox("Optical Character Recognition")
        toolbar_groupbox_ocr.setLayout(QGridLayout())
        toolbar_groupbox_ocr.layout().setContentsMargins(8, 0, 8, 8)
        toolbar_groupbox_ocr.layout().setVerticalSpacing(1)
        toolbar_groupbox_ocr.layout().addWidget(QLabel("Engine:"), 0, 0)
        toolbar_groupbox_ocr.layout().addWidget(self.ocr_engine_combo, 1, 0)
        toolbar_groupbox_ocr.layout().addWidget(QLabel("Configuration:"), 0, 1)
        toolbar_groupbox_ocr.layout().addWidget(self.ocr_config_combo, 1, 1)
        toolbar_groupbox_ocr.layout().addWidget(QLabel("Hint:"), 0, 2)
        toolbar_groupbox_ocr.layout().addWidget(self.ocr_hint_combo, 1, 2)
        toolbar_groupbox_ocr.layout().addWidget(self.ocr_start_button, 1, 3)

        toolbar_groupbox_translation = QGroupBox("Translation")
        toolbar_groupbox_translation.setLayout(QGridLayout())
        toolbar_groupbox_translation.layout().setContentsMargins(8, 0, 8, 8)
        toolbar_groupbox_translation.layout().setVerticalSpacing(1)
        toolbar_groupbox_translation.layout().addWidget(QLabel("Language:"), 0, 0)
        toolbar_groupbox_translation.layout().addWidget(self.translation_language_combo, 1, 0)
        toolbar_groupbox_translation.layout().addWidget(self.translation_start_button, 1, 1)

        toolbar_groupbox_views = QGroupBox("Views")
        toolbar_groupbox_views.setLayout(QHBoxLayout())
        #toolbar_groupbox_views.layout().setContentsMargins(8, 0, 8, 8)
        #toolbar_groupbox_views.layout().setVerticalSpacing(1)
        toolbar_groupbox_views.layout().addWidget(self.view_button_1)
        toolbar_groupbox_views.layout().addWidget(self.view_button_2)
        toolbar_groupbox_views.layout().addWidget(self.view_button_3)
        toolbar_groupbox_views.layout().addWidget(self.view_button_4)
        toolbar_groupbox_views.layout().addWidget(self.view_synced_scrolling)



        toolbar = self.addToolBar("Main Toolbar")
        #toolbar.layout().setContentsMargins(10, 5, 10, 5)  # Left, Top, Right, Bottom padding (in pixels)
        toolbar.layout().setSpacing(4)   
        #toolbar.addWidget(QLabel("OCR engine: "))
        toolbar.addWidget(toolbar_groupbox_ocr)
        toolbar.addWidget(toolbar_groupbox_translation)
        toolbar.addWidget(toolbar_groupbox_views)


    def start_ocr_clicked(self):
        if not self.input_path or not self.ocr_engine_combo.currentText():
            QMessageBox.warning(
                self,
                "OCR unavailable",
                "Select an input file and OCR engine before starting OCR.",
            )
            return

        if self.ocr_running:
            return

        self._clear_output_stages()
        with tempfile.NamedTemporaryFile(
            dir=self._ocr_temp_dir.name,
            prefix="ocr-result-",
            suffix=".json",
            delete=False,
        ) as json_file:
            output_path = json_file.name

        self.ocr_running = True
        self._update_ocr_button_state()
        self.open_action.setEnabled(False)
        self.load_ocr_json_action.setEnabled(False)

        self.ocr_worker = OCRWorker(
            self.input_path,
            output_path,
            self.ocr_engine_combo.currentText(),
            self.ocr_config_combo.currentText().lower(),
        )
        self.ocr_worker.completed.connect(self.on_ocr_complete)
        self.ocr_worker.start()

    def _update_ocr_button_state(self):
        self.ocr_start_button.setEnabled(
            bool(self.input_path and self.ocr_engine_combo.currentText())
            and not self.ocr_running
        )

    def open_triggered(self):
        input_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",  # Empty string defaults to the current working directory
            "PDF Files (*.pdf);;Image Files (*.bmp *.png *.jpg *.jpeg *.webp *.tiff);;All Files (*)"
        )

        if not input_path:
            print("User cancelled the dialog.") 
            self.statusBar().showMessage("Current document unchanged")
            return

        print(f"Selected file: {input_path}")
        self.statusBar().showMessage("File selected: " + input_path)
        self.input_path = input_path
        self.input_viewer.load_file(input_path)
        self._clear_output_stages()
        self.save_action.setEnabled(True)
        self._update_ocr_button_state()

    def load_ocr_json_triggered(self):
        json_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load OCR JSON",
            "",
            "Docling JSON (*.json);;All Files (*)",
        )

        if not json_path:
            self.statusBar().showMessage("No OCR JSON loaded")
            return

        try:
            document = self._load_docling_document(json_path)
            markdown = document.export_to_markdown()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load OCR JSON: {e}")
            self.statusBar().showMessage(f"Could not load OCR JSON: {e}")
            return

        self._clear_output_stages()
        self.ocr_json_path = Path(json_path)
        self._set_markdown_stage_content("ocr", markdown)
        self.save_action.setEnabled(True)
        self.statusBar().showMessage("OCR JSON loaded: " + json_path)

    def _load_docling_document(self, json_path: str | Path):
        result = DocumentConverter(
            allowed_formats=[InputFormat.JSON_DOCLING]
        ).convert(str(json_path))
        return result.document

    def _set_markdown_stage_content(self, stage_id: str, markdown: str):
        self.md_viewers_by_stage[stage_id].set_content(markdown)

    def _clear_output_stages(self):
        self.ocr_json_path = None
        for stage_id in ("ocr", "mt", "llm"):
            self.md_viewers_by_stage[stage_id].set_content("")

    def _sync_view_toggle(self, stage_id: str):
        button = self.view_toggle_buttons.get(stage_id)
        if button is not None:
            button.setChecked(False)

    def _toggle_sync_scroll(self, checked: bool):
        self.sync_scroll_enabled = checked

    def _on_md_scrolled(self, source_id: str, block_num: int, intra_ratio: float):
        if not self.sync_scroll_enabled:
            return

        source_viewer = self.md_viewers_by_stage.get(source_id)
        if source_viewer is None:
            return

        source_total = source_viewer.browser.document().blockCount()
        for target_viewer in self.md_viewers:
            if target_viewer is not source_viewer and target_viewer.isVisible():
                target_viewer.sync_to_block(block_num, source_total, intra_ratio)

    def save_triggered(self):
        if self.ocr_json_path is None:
            QMessageBox.warning(
                self,
                "No OCR output",
                "Run OCR before saving an output file.",
            )
            return

        filters = (
            "Plain Text (*.txt);;"
            "Markdown Document (*.md);;"
            "HTML (*.html);;"
            "JSON Document Structure (*.json)"
        )

        output_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save",
            "",  # Empty string defaults to the current working directory
            filters
        )

        if not output_path:
            print("User cancelled the save dialog.")
            self.statusBar().showMessage("No file saved")
            return
        else:
            if "Plain Text" in selected_filter and not output_path.endswith(".txt"):
                output_path += ".txt"
            elif "Markdown" in selected_filter and not output_path.endswith(".md"):
                output_path += ".md"
            elif "HTML" in selected_filter and not output_path.endswith(".html"):
                output_path += ".html"
            elif "JSON Document Structure" in selected_filter and not output_path.endswith(".json"):
                output_path += ".json"

            if (
                "JSON Document Structure" in selected_filter
                and Path(output_path).resolve() == self.ocr_json_path.resolve()
            ):
                QMessageBox.warning(
                    self,
                    "Source JSON",
                    "Choose a different destination to keep the loaded OCR JSON unchanged.",
                )
                return

            try:
                document = self._load_docling_document(self.ocr_json_path)

                if "Plain Text" in selected_filter:
                    Path(output_path).write_text(
                        document.export_to_text(),
                        encoding="utf-8",
                    )
                elif "Markdown" in selected_filter:
                    Path(output_path).write_text(
                        document.export_to_markdown(),
                        encoding="utf-8",
                    )
                elif "HTML" in selected_filter:
                    Path(output_path).write_text(
                        document.export_to_html(),
                        encoding="utf-8",
                    )
                elif "JSON Document Structure" in selected_filter:
                    document.save_as_json(output_path)
                else:
                    raise ValueError(f"Unsupported output format: {selected_filter}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Saving failed: {e}")
                self.statusBar().showMessage(f"Saving failed: {e}")
                return

            print(f"Selected save path: {output_path}")
            self.statusBar().showMessage("File saved: " + output_path)
        
    def home_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project")

    def issues_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project/issues/")

    def about_triggered(self):
        QMessageBox.information(self, "Action", "Made by: KNR Stephan - MA8N8W\nPowered by: Python and PyQt6\n2026\n\nContains AI Generated Code")

    def on_engine_changed(self, ocr_engine_name: str):
        self.ocr_config_combo.clear()
        #if engine_name == "TesseractCLI":
        if ocr_engine_name == "EasyOCR":
            self.ocr_config_combo.addItems([
                "CPU",
                "CUDA",
            ])
        if ocr_engine_name == "RapidOCR":
            self.ocr_config_combo.addItems([
                "Torch",
                "OpenVino",
                "ONNXRuntime",
            ])
        self.ocr_config_combo.setEnabled(self.ocr_config_combo.count() > 1)
        self._update_ocr_button_state()

    def on_ocr_complete(self, success, result):
        self.ocr_running = False
        if success:
            try:
                document = self._load_docling_document(result)
                markdown = document.export_to_markdown()
            except Exception as e:
                self.ocr_json_path = None
                QMessageBox.critical(self, "Error", f"OCR result could not be loaded: {e}")
                self.statusBar().showMessage(f"OCR result could not be loaded: {e}")
            else:
                self.ocr_json_path = Path(result)
                self._set_markdown_stage_content("ocr", markdown)
                QMessageBox.information(self, "Success", "OCR processing completed successfully.")
                self.statusBar().showMessage("OCR processing completed successfully.")
        else:
            self.ocr_json_path = None
            QMessageBox.critical(self, "Error", f"OCR processing failed: {result}")
            self.statusBar().showMessage(f"OCR processing failed: {result}")
        self.open_action.setEnabled(True)
        self.load_ocr_json_action.setEnabled(True)
        self._update_ocr_button_state()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "myicon.ico")))
    icon = QIcon("icon.ico")
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
