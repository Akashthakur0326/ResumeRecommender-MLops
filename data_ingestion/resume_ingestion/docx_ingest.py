import io
import docx
from .base_ingestor import BaseIngestor

class DOCXIngestor(BaseIngestor):
    def extract(self, file_content: bytes) -> str:
        """Wraps bytes in a BytesIO stream for python-docx compatibility."""
        try:
            stream = io.BytesIO(file_content)
            doc = docx.Document(stream)
            return "\n".join([p.text for p in doc.paragraphs]).strip()
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {str(e)}")