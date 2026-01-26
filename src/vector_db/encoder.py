import logging
import torch
import sys
import os
from pathlib import Path
from typing import List
from sentence_transformers import SentenceTransformer

# 1. Path Management: Add Project Root to Path
# This is still needed for direct execution, but now we use utils.paths for logic
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Import your helper
from utils.paths import get_model_path

class SemanticEncoder:
    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        """
        Initializes the encoder. 
        Prioritizes loading from the local 'models/' directory (DVC tracked) via utils.paths.
        """
        self.logger = logging.getLogger("mlops_pipeline")
        
        # Determine compute backend
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.logger.info(f"⚙️ Initializing SemanticEncoder on device: {self.device}")

        # --- MLOPS LOGIC: LOCAL VS CLOUD ---
        # 1. Check if the argument is already a direct path (e.g., from Docker env var)
        if os.path.isdir(model_name):
            model_source = model_name
            print(f"🚀 [LOCAL LOAD] Using explicit directory: {model_source}")
            self.logger.info(f"📂 Loading model from provided directory: {model_source}")
        
        else:
            # 2. Use utils.paths to find the local DVC artifact
            local_path = get_model_path(model_name)
            
            if local_path.exists():
                model_source = str(local_path)
                # HIGH VISIBILITY PRINT
                print(f"✅ [SUCCESS] Found local DVC artifact at: {model_source}")
                print(f"🤖 Backend: {self.device}")

                self.logger.info(f"📂 Found local DVC artifact: {model_source}")
            else:
                # 3. Fallback to Hugging Face (Cloud Download)
                model_source = model_name
                # HIGH VISIBILITY WARNING
                print(f"⚠️  [FALLBACK] Local artifact NOT found at {local_path}")
                print(f"🌐 Downloading '{model_name}' from Hugging Face Hub...")

                self.logger.warning(
                    f"🌐 Local artifact not found at {local_path}. "
                    f"Downloading from Hugging Face: {model_source}"
                )

        # Initialize model
        try:
            self.model = SentenceTransformer(model_source, device=self.device)#download if model is not there and if its present locally use that 
            print(f"🌟 Model loaded and ready for inference.")

            self.logger.info(f"✅ Model successfully loaded: {model_source}")
        except Exception as e:
            self.logger.error(f"❌ Failed to load model: {str(e)}")
            print(f"❌ FATAL: Failed to load model from {model_source}")
            
            raise e

    def encode_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        Generates normalized 768-dim embeddings for a list of strings.
        Normalization is CRITICAL for Cosine Similarity.
        """
        if not texts:
            self.logger.warning("⚠️ encode_batch received empty text list.")
            return []

        self.logger.info(f"🔢 Encoding {len(texts)} documents...")

        # SentenceTransformers handles internal batching and GPU transfer
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True  # Keep this consistent across the project
        )

        # Ensure output is a Python list for JSON serialization (FastAPI/Postgres)
        if hasattr(embeddings, 'tolist'):
            return embeddings.tolist()
        return embeddings