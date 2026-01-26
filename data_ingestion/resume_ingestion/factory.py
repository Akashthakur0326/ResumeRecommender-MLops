import sys
from pathlib import Path

# 1. Reach the Root
# File: root/data_ingestion/resume_ingestion/factory.py
# .parent(resume_ingestion) -> .parent(data_ingestion) -> .parent(root)
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# 2. Absolute Imports from Root
from data_ingestion.resume_ingestion.pdf_ingest import PDFIngestor
from data_ingestion.resume_ingestion.docx_ingest import DOCXIngestor
from data_ingestion.resume_ingestion.txt_ingestor import TXTIngestor

class IngestorFactory:
    _ingestors = {
        ".pdf": PDFIngestor(),
        ".docx": DOCXIngestor(),
        ".txt": TXTIngestor()
    }

    @classmethod
    def get_ingestor(cls, extension: str):
        ext = extension.lower()
        if not ext.startswith("."): ext = f".{ext}"
        
        ingestor = cls._ingestors.get(ext)
        if not ingestor:
            raise ValueError(f"Unsupported file type: {ext}")
        return ingestor