#DOCX → python-docx → text
from docx import Document

doc = Document("resume.docx")
text = "\n".join(p.text for p in doc.paragraphs)
