import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv

# 1. Load Environment Variables
load_dotenv() 

# 2. Add Project Root to Path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from app.services.ai_insight import AIInsightEngine

def test_ai_insight_engine():
    print("\n🧠 TESTING AI INSIGHT ENGINE (With Colab Logic)...")
    
    # --- REAL DATA FROM COLAB TEST ---
    # These anchors are known to exist in your graph
    colab_anchors = [
        'Inference Pipeline', 'Robustness', 'Inference', 'Selenium', 'Scikit-learn', 
        'Naive Bayes', 'Machine Learning', 'ONNX Runtime', 'Embeddings', 'Model', 
        'Speed', 'Language Model', 'Retrieval System', 'Keras', 'SVM', 'Matplotlib', 
        'WebSockets', 'Latency', 'Deep Learning', 'MLOps', 'LLaMA', 'ONNX', 
        'Regression', 'Programmer', 'Programming', 'NumPy', 'Playwright', 'Pandas', 
        'Plotly', 'SQL', 'Retrieval', 'Hugging Face', 'Data Structures', 'Seaborn', 
        'Transformer', 'Clustering', 'PyTorch', 'Probability', 'Machine Learning Engineer', 
        'SpaCy', 'BERT', 'Scheduling', 'Data Augmentation', 'FAISS', 'FastAPI', 
        'Functionality', 'Audio', 'Transformers', 'TensorFlow', 'XGBoost', 
        'Large Language Model', 'Algorithms', 'Frontend'
    ]
    
    dummy_resume = "I am a Machine Learning Engineer with experience in " + ", ".join(colab_anchors[:10])
    
    # We test specifically for "Data Scientist" since your Colab results showed a great match there
    category = "Data Scientist"
    matched_jobs = ["Senior Data Scientist", "AI Researcher", "ML Engineer"]
    gap_jobs = ["Principal Architect", "Head of Data"]

    engine = None
    try:
        # 1. Initialize
        print("   1. Initializing Engine & Connecting to Neo4j...")
        engine = AIInsightEngine()
        
        # 2. Run Generation
        print(f"   2. Generating Insight for category: '{category}'...")
        start = time.time()
        
        result = engine.generate_insight(
            resume_text=dummy_resume,
            user_skills=colab_anchors, # Passing the working anchors
            category=category,
            matched_jobs=matched_jobs,
            gap_jobs=gap_jobs
        )
        
        duration = time.time() - start
        
        # 3. Output
        print("\n✅ INSIGHT GENERATED SUCCESSFULLY!")
        print(f"⏱️ Execution Time: {duration:.2f}s")
        print("-" * 50)
        print(json.dumps(result, indent=2))
        print("-" * 50)

    except Exception as e:
        print(f"\n❌ AI Engine Test Failed: {e}")
    finally:
        if engine:
            engine.close()

if __name__ == "__main__":
    test_ai_insight_engine()