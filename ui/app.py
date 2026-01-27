import streamlit as st
import sys
import requests
from pathlib import Path

"""
Accepts File -> Extracts Text -> Sends JSON Payload -> Displays Score
"""
import os

# 1. Path Management
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data_ingestion.resume_ingestion.factory import IngestorFactory
from src.parser.engine import ResumeParserEngine

# --- CONFIG ---
# On Localhost, this defaults to "http://127.0.0.1:8000"
# On AWS Docker, we change this env var to "http://backend_container:8000"
API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

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
        # Display the count as a label
        st.info(f"💼 **Experience:** {len(exp)} items detected")
        
        # NEW: Actually show the items inside an expander
        if exp:
            with st.expander("View Experience Details"):
                for i, item in enumerate(exp, 1):
                    st.write(f"**{i}.** {item}")

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
    # ... inside ui/app.py ...

    # --- SCORING ACTION ---
    # --- SCORING ACTION ---
    if st.button("🚀 Find Matching Jobs", type="primary"):
        if not st.session_state.raw_text:
            st.error("Please process a resume first.")
        else:
            with st.spinner("Consulting the AI Engine..."):
                try:
                    # 1. Send Request to FastAPI
                    payload = {"resume_text": st.session_state.raw_text}
                    # Ensure API_URL is defined (e.g. from os.getenv)
                    response = requests.post(f"{API_BASE_URL}/api/v1/score", json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if "results" in data:
                            st.success("✅ Jobs Found! Here are your top matches:")
                            
                            # 2. Iterate through Top Categories
                            for category_block in data["results"]:
                                cat_name = category_block['category']
                                match_score = category_block['category_match_score']
                                
                                # Category Header
                                st.markdown(f"### 📂 {cat_name} <small>(Match: {match_score*100:.0f}%)</small>", unsafe_allow_html=True)
                                st.info(f"🤖 **AI Insight:** Why you fit this role... (Coming Soon)")
                                
                                # 3. Job Cards
                                jobs = category_block.get('recommended_jobs', [])
                                if jobs:
                                    for job in jobs:
                                        # Expander Title: Role | Company | Score
                                        label = f"**{job['title']}** | {job['company']} ({job['match_confidence']}% Match)"
                                        
                                        with st.expander(label):
                                            # Create two columns for clean layout
                                            c1, c2 = st.columns(2)
                                            
                                            with c1:
                                                st.write(f"🏢 **Company:** {job['company']}")
                                                st.write(f"📍 **Location:** {job['location']}")
                                                st.write(f"💰 **Salary:** {job.get('salary', 'Not Disclosed')}")
                                                
                                            with c2:
                                                st.write(f"📅 **Posted:** {job['posted_at']}")
                                                st.write(f"🌐 **Source:** {job.get('source', 'Web')}")
                                                
                                                # Clickable Link
                                                if job['apply_link'] and job['apply_link'] != "#":
                                                    st.markdown(f"🔗 [**Apply Now**]({job['apply_link']})")
                                                else:
                                                    st.caption("No direct link available")
                                            
                                            # Debug info (optional, good for dev)
                                            st.caption(f"Job ID: `{job['job_id']}`")
                                else:
                                    st.warning("No active listings found for this category.")
                                
                                st.divider() # Visual separation
                        else:
                            st.warning("No matches found. Try adding more skills to your resume.")
                            
                    else:
                        st.error(f"Server Error: {response.text}")
                        
                except requests.exceptions.ConnectionError:
                    st.error("❌ Could not connect to the Backend. Is FastAPI running?")
                except Exception as e:
                    st.error(f"❌ Unexpected Error: {e}")