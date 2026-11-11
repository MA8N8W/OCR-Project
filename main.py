import os
import sys
import webbrowser

from annotated_types import doc
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    EasyOcrOptions,
    OcrEngine,
    OcrOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from PyQt6.QtCore import QCoreApplication, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QGuiApplication, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
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


class OcrWorker(QThread):
    finished = pyqtSignal(bool,str)

    def __init__(self, input_path: str, output_path: str, selected_filter, selected_engine):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.selected_filter = selected_filter
        self.selected_engine = selected_engine

    def run(self):
        try:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True

            if self.selected_engine == "TesseractCLI":
                ocr_opts = TesseractCliOcrOptions(force_full_page_ocr=True)
            elif self.selected_engine == "EasyOCR":
                ocr_opts = EasyOcrOptions(force_full_page_ocr=True)
            elif self.selected_engine == "RapidOCR":
                ocr_opts = RapidOcrOptions(
                    force_full_page_ocr=True,
                    backend="openvino",
                    rapidocr_params={
                        "EngineConfig.openvino.inference_num_threads": 4
                    },
                )
            else:
                raise ValueError(f"Unsupported OCR engine: {self.selected_engine}")

            pipeline_options.ocr_options = ocr_opts

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

            if "Markdown" in self.selected_filter:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write(doc.export_to_markdown())

            elif "JSON Document Structure" in self.selected_filter:
                import json
                #with open(self.output_path, "w", encoding="utf-8") as f:
                #    f.write(doc.export_to_dict())

                with open(self.output_path, "w", encoding="utf-8") as f:
                    json.dump(doc.export_to_dict(), f, ensure_ascii=False, indent=2)

            elif "Plain Text" in self.selected_filter:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write(doc.export_to_text())

            self.finished.emit(True, "Success")
        except Exception as e:
            self.finished.emit(False, str(e))

class MainWindow(QMainWindow):

    # Get the application palette
    palette = QGuiApplication.palette()

    # For Qt >= 6.6, retrieve the true OS Accent color
    accent_color = palette.color(QPalette.ColorRole.Accent)

    # For Qt < 6.6, retrieve the fallback Highlight color (selection color)
    fallback_color = palette.color(QPalette.ColorRole.Highlight)

    # Convert to hex for stylesheets if needed (e.g., "#3daee9")
    accent_hex = accent_color.name()

    #print(f"Accent Color: {accent_color}, Fallback Color: {fallback_color}, Accent Hex: {accent_hex}")

    def __init__(self):
        super().__init__()
        self.input_path = None
        self.setWindowTitle("Document OCR")
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

        toolbar = self.addToolBar("OCR Engine")
        toolbar.addWidget(QLabel("OCR engine: "))

        self.engine_combo = QComboBox()
        self.engine_combo.addItems([
            "TesseractCLI",
            "EasyOCR",
            "RapidOCR",
        ])
        toolbar.addWidget(self.engine_combo)

    def open_triggered(self):
        input_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",  # Empty string defaults to the current working directory
            "PDF Files (*.pdf);;All Files (*)"
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
            "Markdown Document (*.md);;"
            "JSON Document Structure (*.json);;"
            "Plain Text (*.txt)"
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

            if "Markdown" in selected_filter and not output_path.endswith(".md"):
                output_path += ".md"
            elif "JSON Document Structure" in selected_filter and not output_path.endswith(".json"):
                output_path += ".json"
            elif "Plain Text" in selected_filter and not output_path.endswith(".txt"):
                output_path += ".txt"

            self.worker = OcrWorker(self.input_path, output_path, selected_filter, self.engine_combo.currentText())
            self.worker.finished.connect(self.on_processing_complete)
            self.worker.start()
        

    def home_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project")

    def issues_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project/issues/")

    def about_triggered(self):
        QMessageBox.information(self, "Action", "Made by: KNR Stephan - MA8N8W\nPowered by: Python and PyQt6\n2026\n\nAllergy Notice: May contain traces of AI generated code.")

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