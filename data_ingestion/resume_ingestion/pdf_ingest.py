#PDF → PyMuPDF → text

import fitz  # PyMuPDF

doc = fitz.open("resume.pdf")
text = "".join(page.get_text() for page in doc)
