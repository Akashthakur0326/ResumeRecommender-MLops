import streamlit as st
import sys
import requests
from pathlib import Path

# 1. Path Management
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data_ingestion.resume_ingestion.factory import IngestorFactory
from src.parser.engine import ResumeParserEngine

# --- CONFIG ---
API_BASE_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="Resume Intelligence", layout="wide", page_icon="🧠")

# --- CACHING ---
@st.cache_resource
def get_ingestor_factory():
    return IngestorFactory()

@st.cache_resource
def get_parser_engine():
    return ResumeParserEngine()

@st.cache_data(show_spinner="🧠 Analyzing Resume Structure...")
def parse_resume_content(file_name, _text):
    parser = get_parser_engine()
    return parser.parse(_text)

# --- STATE ---
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = None
if "raw_text" not in st.session_state:
    st.session_state.raw_text = None
if "file_name" not in st.session_state:
    st.session_state.file_name = None

st.title("📄 Resume Intelligence Parser")

# --- UPLOAD & PARSE ---
uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "txt"])

if uploaded_file:
    if st.session_state.file_name != uploaded_file.name:
        with st.spinner("Analyzing Document..."):
            try:
                factory = get_ingestor_factory() 
                ext = Path(uploaded_file.name).suffix.lower()
                ingestor = factory.get_ingestor(ext)
                raw_text = ingestor.extract(uploaded_file)
                
                # Store in session
                st.session_state.parsed_data = parse_resume_content(uploaded_file.name, raw_text)
                st.session_state.raw_text = raw_text 
                st.session_state.file_name = uploaded_file.name
                
            except Exception as e:
                st.error(f"❌ Error during ingestion/parsing: {e}")

# --- DISPLAY RESULTS ---
if st.session_state.parsed_data:
    data = st.session_state.parsed_data
    
    # NEW: Display Candidate Name prominently
    candidate_name = data.get('name', 'Unknown Candidate')
    st.header(f"👤 {candidate_name}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📧 **Email:** {data.get('email', 'Not found')}")
    with col2:
        edu = data.get('education', [])
        st.info(f"🎓 **Education:** {', '.join(edu) if edu else 'Not detected'}")
    with col3:
        exp = data.get('experience', [])
        st.info(f"💼 **Experience:** {len(exp)} entries found")

    # Layout for Skills and Sections
    tab1, tab2 = st.tabs(["🛠️ Skills Detected", "📑 Structure Analysis"])
    
    with tab1:
        skills = data.get('skills', [])
        if skills:
            st.write(", ".join([f"`{s}`" for s in skills]))
        else:
            st.warning("No skills detected.")

    with tab2:
    # We need to make sure engine.py returns the full sections dict, not just the keys
        sections_content = data.get('sections_content', {}) 
        
        if sections_content:
            st.write("**Content by Section:**")
            for section_name, lines in sections_content.items():
                with st.expander(f"📍 {section_name}"):
                    # Join the list of lines into a block of text
                    st.text("\n".join(lines))
        else:
            st.warning("No structured sections found. Using raw text fallback.")
    st.divider()

    # --- SCORING ACTION ---
    if st.button("🚀 Find Matching Jobs", type="primary"):
        with st.spinner("Talking to Inference Engine..."):
            try:
                payload = {
                    "name": candidate_name, # Use the extracted name
                    "text": st.session_state.raw_text,
                    "job_id": "job_123" 
                }
                res = requests.post(f"{API_BASE_URL}/candidates/score", json=payload, timeout=10)
                
                if res.status_code == 200:
                    result = res.json()
                    score = result.get('similarity_score', 0) * 100
                    st.success(f"✅ Match Score: {score:.1f}%")
                    with st.expander("View Similarity Metadata"):
                        st.json(result)
                else:
                    st.error(f"Backend Error: {res.text}")
            except Exception as e:
                st.error(f"❌ Connection Error: Ensure FastAPI server is running on port 8000")