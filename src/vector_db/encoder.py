import logging
import torch
import sys
from pathlib import Path
from typing import List
from sentence_transformers import SentenceTransformer

# 1. Path Management
# Ensures this file can be part of the 'src' package even if run directly
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

class SemanticEncoder:
    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        self.logger = logging.getLogger("mlops_pipeline")
        
        # Determine compute backend
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.logger.info(
            f"🧠 Loading AI Model ({model_name}) on {self.device}..."
        )

        # Initialize model with explicit device mapping
        self.model = SentenceTransformer(model_name, device=self.device)

    def encode_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        Generates normalized 768-dim embeddings for a list of strings.
        Normalization is CRITICAL for Cosine Similarity.
        """
        self.logger.info(f"🔢 Encoding {len(texts)} documents...")

        # SentenceTransformers handles internal batching and GPU transfer
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True  # 🔥 Keep this consistent across the project
        )

        return embeddings.tolist()