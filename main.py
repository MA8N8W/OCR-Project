import os
import sys
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
from docling.document_converter import DocumentConverter, PdfFormatOption
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

#from viewers import InputViewer, MDViewer

BASE_DIR = Path(__file__).resolve().parent
PDFJS_VIEWER = BASE_DIR / "assets" / "pdfjs" / "web" / "viewer.html"

# Pass str(PDFJS_VIEWER) into InputViewer
#input_viewer = InputViewer(pdfjs_viewer_html=str(PDFJS_VIEWER))

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
    finished = pyqtSignal(bool,str)

    def __init__(self, input_path: str, output_path: str, selected_filter, selected_engine, selected_config):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.selected_filter = selected_filter
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
                allowed_formats=[InputFormat.PDF],
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    )
                },
            )

            result = converter.convert(self.input_path)
            doc = result.document

            if "Plain Text" in self.selected_filter:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write(doc.export_to_text())

            elif "Markdown" in self.selected_filter:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write(doc.export_to_markdown())

            elif "HTML" in self.selected_filter:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write(doc.export_to_html())

            elif "JSON Document Structure" in self.selected_filter:
                import json
                #with open(self.output_path, "w", encoding="utf-8") as f:
                #    f.write(doc.export_to_dict())

                with open(self.output_path, "w", encoding="utf-8") as f:
                    json.dump(doc.export_to_dict(), f, ensure_ascii=False, indent=2)


            self.finished.emit(True, "Success")
        except Exception as e:
            self.finished.emit(False, str(e))

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

        self.input_path = None
        self.config = Config()
        self.setWindowTitle("Document Scanning & Translation")
        self.setGeometry(100, 100, 800, 500)

        self.statusBar().showMessage("Welcome!")

        menu = self.menuBar()


        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel_content = QLabel("Left Panel Content Here")
        right_panel_content = QLabel("Right Panel Content Here")

        left_panel_layout = QVBoxLayout()
        right_panel_layout = QVBoxLayout()

        left_panel = QGroupBox("Document")
        left_panel.setLayout(left_panel_layout)
        left_panel.layout().addWidget(left_panel_content)

        right_panel = QGroupBox("OCR Result")
        right_panel.setLayout(right_panel_layout)
        right_panel.layout().addWidget(right_panel_content)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 400])
        splitter.setHandleWidth(1)

        self.setCentralWidget(splitter)

        button_open = QAction("&Open", self)
        button_open.triggered.connect(self.open_triggered)

        button_save = QAction("&Save", self)
        button_save.triggered.connect(self.save_triggered)
        button_save.setDisabled(True)

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
        self.ocr_start_button.setDisabled(True)
        
        self.translation_language_combo = QComboBox()
        self.translation_language_combo.setFixedWidth(90)
        self.translation_language_combo.setDisabled(True)

        self.translation_start_button = QPushButton("Start")
        self.translation_start_button.setDisabled(True)

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


        toolbar = self.addToolBar("Main Toolbar")
        #toolbar.layout().setContentsMargins(10, 5, 10, 5)  # Left, Top, Right, Bottom padding (in pixels)
        toolbar.layout().setSpacing(4)   
        #toolbar.addWidget(QLabel("OCR engine: "))
        toolbar.addWidget(toolbar_groupbox_ocr)
        toolbar.addWidget(toolbar_groupbox_translation)

        

    def open_triggered(self):
        input_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",  # Empty string defaults to the current working directory
            "PDF Files (*.pdf);;Image Files (*.bmp *.png *.jpg *.jpeg *.webp *.tiff);;All Files (*)"
        )

        button_save = self.menuBar().actions()[0].menu().actions()[1]  # Access the Save action
        button_save.setEnabled(bool(input_path))  # Enable Save if a file is selected

        if not input_path:
            print("User cancelled the dialog.") 
            self.statusBar().showMessage("No file selected")
            self.input_path = None
            return
        else:
            print(f"Selected file: {input_path}")
            self.statusBar().showMessage("File selected: " + input_path)
            self.input_path = input_path

    def save_triggered(self):
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
            print(f"Selected save path: {output_path}")
            self.statusBar().showMessage("File saved: " + output_path)

            if "Plain Text" in selected_filter and not output_path.endswith(".txt"):
                output_path += ".txt"
            elif "Markdown" in selected_filter and not output_path.endswith(".md"):
                output_path += ".md"
            elif "HTML" in selected_filter and not output_path.endswith(".html"):
                output_path += ".html"
            elif "JSON Document Structure" in selected_filter and not output_path.endswith(".json"):
                output_path += ".json"

            self.worker = OCRWorker(self.input_path, output_path, selected_filter, self.ocr_engine_combo.currentText(), self.ocr_config_combo.currentText().lower())
            self.worker.finished.connect(self.on_processing_complete)
            self.worker.start()
        
    def home_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project")

    def issues_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project/issues/")

    def about_triggered(self):
        QMessageBox.information(self, "Action", "Made by: KNR Stephan - MA8N8W\nPowered by: Python and PyQt6\n2026\n\nContains AI Generated Code")

    def on_engine_changed(self, engine_name: str):
        self.ocr_config_combo.clear()
        #if engine_name == "TesseractCLI":
        if engine_name == "EasyOCR":
            self.ocr_config_combo.addItems([
                "CPU",
                "CUDA",
            ])
        if engine_name == "RapidOCR":
            self.ocr_config_combo.addItems([
                "Torch",
                "OpenVino",
                "ONNXRuntime",
            ])
        self.ocr_config_combo.setEnabled(self.ocr_config_combo.count() > 1)

    def on_processing_complete(self, success, message):
        if success:
            QMessageBox.information(self, "Success", "OCR processing completed successfully.")
            self.statusBar().showMessage("OCR processing completed successfully.")
        else:
            QMessageBox.critical(self, "Error", f"OCR processing failed: {message}")
            self.statusBar().showMessage(f"OCR processing failed: {message}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "myicon.ico")))
    icon = QIcon("icon.ico")
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
