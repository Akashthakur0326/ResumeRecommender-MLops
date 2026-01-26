from abc import ABC, abstractmethod
from pathlib import Path
""" 
a interface
"""
class BaseIngestor(ABC):
    @abstractmethod
    def extract(self, file_path_or_bytes) -> str:
        """Must return cleaned text string."""
        pass