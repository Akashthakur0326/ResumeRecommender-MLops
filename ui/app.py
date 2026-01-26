import streamlit as st
import sys
from pathlib import Path

# 1. Path Management
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.services.resume_extractor import ResumeExtractor

# --- PAGE CONFIG ---
st.set_page_config(page_title="Resume Parser Pro", layout="wide")

# --- CACHING LOGIC ---
@st.cache_resource(show_spinner="⚙️ Loading Extraction Models (OCR + PDF)...")
def load_extractor():
    """
    Initializes the ResumeExtractor singleton.
    Cached because loading PaddleOCR takes 2-5 seconds.
    """
    return ResumeExtractor()

# Initialize Logic (This is now instant on re-runs)
extractor = load_extractor()

# --- UI LAYOUT ---
st.title("📄 Resume Ingestion & Parsing")
st.markdown("Upload your resume (PDF, DOCX, or Image) to extract raw text.")

# Drag & Drop Widget
uploaded_file = st.file_uploader(
    "Drag and drop file here", 
    type=["pdf", "docx", "jpg", "png", "jpeg"],
    help="Limit 200MB per file"
)

if uploaded_file:
    with st.spinner('Parsing document...'):
        # Get file type (MIME or extension)
        file_type = uploaded_file.type if uploaded_file.type else uploaded_file.name.split('.')[-1]
        
        # Call the Service Layer
        extracted_text = extractor.extract(uploaded_file, file_type)
        
        # UI Layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("✅ Extraction Complete")
            st.info(f"File: {uploaded_file.name}")
            st.info(f"Size: {uploaded_file.size / 1024:.2f} KB")

        with col2:
            st.subheader("Extracted Content Preview")
            st.text_area("Raw Text", extracted_text, height=400)
            
            # Future Hook for Scorer
            if st.button(" Analyze & Score (Coming Soon)"):
                st.warning("⚠️ Scorer module not connected yet.")