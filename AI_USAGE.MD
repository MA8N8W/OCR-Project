AI Use Disclosure; some parts of this software were written with AI assistance, specifically Github Copilot.


----------------------------------------------------------------------------------------------------------------------------------
Prompt 01
----------------------------------------------------------------------------------------------------------------------------------
This is a Python PyQt6 application built around Docling, it's primary purpose is performing OCR on scanned documents (in either PDF or Image format), to then (if the user chooses to do so) translate the OCR output.

Currently save_triggered is what triggers the actual OCR process. I want the OCR process to start when the user pushes the ocr_start_button (which triggers the start_ocr_clicked method).

ocr_start_button
is grayed out/disabled on startup; when both an input file and ocr engine are selected the button should be enabled

start_ocr_clicked
will convert the ocr input to json (which supposedly is a lossless docling format suitable for further processing and conversion)

save_triggered 
will take the json formatted OCR output and convert it to the file format chosen in the save file dialog, supposedly conversion is entirely handled by docling, if no ocr processing has taken place yet, then show a message box informing the user about this

In case there are any questions in regards to architecture first consult with me.
----------------------------------------------------------------------------------------------------------------------------------
