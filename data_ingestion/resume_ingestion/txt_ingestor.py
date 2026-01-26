from data_ingestion.resume_ingestion.base_ingestor import BaseIngestor

class TXTIngestor(BaseIngestor):  # Ensure CASE SENSITIVE match
    def extract(self, file_stream) -> str:
        try:
            content = file_stream.read()
            if isinstance(content, bytes):
                return content.decode("utf-8").strip()
            return content.strip()
        except Exception as e:
            return f"Error reading text file: {str(e)}"