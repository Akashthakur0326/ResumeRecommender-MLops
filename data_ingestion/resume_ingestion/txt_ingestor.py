from .base_ingestor import BaseIngestor

class TXTIngestor(BaseIngestor):
    def extract(self, file_content: bytes) -> str:
        """Decodes raw bytes into a string with error handling."""
        try:
            # Safety: Resumes are never huge; truncate if someone sends a 100MB txt
            if len(file_content) > 1_000_000:
                file_content = file_content[:1_000_000]

            # Use errors="ignore" to prevent crashing on weird hidden characters
            return file_content.decode("utf-8", errors="ignore").strip()
            
        except Exception as e:
            # Raise exception instead of returning string to keep data clean
            raise ValueError(f"Failed to decode TXT file: {str(e)}")