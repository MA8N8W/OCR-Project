import os
import sys
import webbrowser

from PyQt6.QtCore import QCoreApplication

from PyQt6.QtGui import QAction, QIcon

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QMainWindow,
    QStatusBar,
    QToolBar,
    QFileDialog,
    QMessageBox,
)

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Document OCR")

        self.statusBar().showMessage("Welcome!")

        menu = self.menuBar()

        button_open = QAction("&Open", self)
        button_open.triggered.connect(self.open_triggered)

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
        file_menu.addSeparator()
        file_menu.addAction(button_exit)

        about_menu = menu.addMenu("&About")
        about_menu.addAction(button_home)
        about_menu.addAction(button_issues)
        about_menu.addSeparator()
        about_menu.addAction(button_about)

    def open_triggered(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",  # Empty string defaults to the current working directory
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            print(f"Selected file: {file_path}")
            self.statusBar().showMessage("File selected: " + file_path)
        else:
            print("User cancelled the dialog.") 
            self.statusBar().showMessage("No file selected")   

    def home_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project")

    def issues_triggered(self):
        webbrowser.open("https://github.com/MA8N8W/OCR-Project/issues/")

    def about_triggered(self):
        QMessageBox.information(self, "Action", "Made by: KNR Stephan - MA8N8W\nPowered by: Python and PyQt6\n2026\n\nAllergy Notice: May contain traces of AI generated code.")

def main():
    app = QApplication([])
    window = MainWindow()
    window.show()

    icon = QIcon("icon.ico")
    #app.setWindowIcon(icon)

    window.setWindowIcon(icon)
    window.show()

    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())