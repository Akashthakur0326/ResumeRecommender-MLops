import fitz
from .base_ingestor import BaseIngestor

class PDFIngestor(BaseIngestor):
    def extract(self, file_stream) -> str:
        text = ""
        with fitz.open(stream=file_stream, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text() + "\n"
        return text.strip()