import docx
import io
from .base_ingestor import BaseIngestor

class DOCXIngestor(BaseIngestor):
    def extract(self, file_stream) -> str:
        # Wrap bytes in BytesIO if it's not already a stream
        if isinstance(file_stream, bytes):
            file_stream = io.BytesIO(file_stream)
        
        doc = docx.Document(file_stream)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()