import fitz
from .base_ingestor import BaseIngestor

class PDFIngestor(BaseIngestor):
    def extract(self, file_content: bytes) -> str:
        """Extracts text from PDF bytes using PyMuPDF."""
        text = ""
        # We pass the bytes directly to the stream parameter
        with fitz.open(stream=file_content, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text() + "\n"
        
        return text.strip()