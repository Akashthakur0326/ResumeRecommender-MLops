from sentence_transformers import SentenceTransformer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
print("🚀 DEBUG: Script has started...")
# 2. Define the path relative to the root
MODEL_PATH = PROJECT_ROOT / "models" / "all-mpnet-base-v2"

def bake_model():
    # Ensure the directory exists
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🔥 Baking model to {MODEL_PATH}...")
    
    # This downloads the model from HF
    model = SentenceTransformer("all-mpnet-base-v2")
    
    # This saves it LOCALLY as a self-contained artifact
    model.save(str(MODEL_PATH))
    print(f"✅ Model downloaded to: {MODEL_PATH}")

if __name__ == "__main__":
    bake_model()