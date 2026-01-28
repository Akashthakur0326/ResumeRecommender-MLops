import streamlit as st
import requests
import os

# --- CONFIG ---
# On Localhost, this defaults to "http://127.0.0.1:8000"
# On AWS Docker, we change this env var to "http://backend_container:8000"
API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Resume Intelligence", layout="wide", page_icon="🧠")

# --- INITIALIZE STATE ---
if "file_name" not in st.session_state:
    st.session_state.file_name = None
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = None
if "raw_text" not in st.session_state:
    st.session_state.raw_text = None

st.title("📄 Resume Intelligence Parser")

# --- UPLOAD & PARSE LOGIC ---
uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "txt"])

if uploaded_file:
    # 1. Size Safety Check (2MB)
    if uploaded_file.size > 2 * 1024 * 1024:
        st.error("File too large. Max size is 2MB.")
        st.stop()

    # 2. Trigger Parsing ONLY if the file is new
    if st.session_state.file_name != uploaded_file.name:
        with st.spinner("🧠 Extracting Resume Structure..."):
            try:
                # Prepare payload
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                
                # Hit the PARSE endpoint
                response = requests.post(f"{API_BASE_URL}/api/v1/parse_resume", files=files, timeout=30)
                
                if response.status_code == 200:
                    parsed_json = response.json()
                    
                    # Store in Session State
                    st.session_state.parsed_data = parsed_json
                    st.session_state.raw_text = parsed_json.get("raw_text", "")
                    st.session_state.file_name = uploaded_file.name
                    st.success("✅ Resume Parsed Successfully!")
                    st.rerun() # Force a rerun to update the UI immediately
                else:
                    st.error(f"Parsing Failed: {response.text}")
                    
            except Exception as e:
                st.error(f"❌ Connection Error: {e}")

# --- DISPLAY PARSED RESULTS ---
if st.session_state.parsed_data:
    data = st.session_state.parsed_data
    
    # 1. Candidate Header
    candidate_name = data.get('name', 'Unknown Candidate')
    st.header(f"👤 {candidate_name}")
    
    # 2. Key Details Columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📧 **Email:** {data.get('email', 'Not found')}")
    with col2:
        edu = data.get('education', [])
        st.info(f"🎓 **Education:** {', '.join(edu) if edu else 'Not detected'}")
    with col3:
        exp = data.get('experience', [])
        st.info(f"💼 **Experience:** {len(exp)} items detected")
        
        # Experience Details Expander
        if exp:
            with st.expander("View Experience Details"):
                for i, item in enumerate(exp, 1):
                    st.write(f"**{i}.** {item}")

    # 3. Skills & Structure Tabs
    tab1, tab2 = st.tabs(["🛠️ Skills Detected", "📑 Structure Analysis"])
    
    with tab1:
        skills = data.get('skills', [])
        if skills:
            st.write(", ".join([f"`{s}`" for s in skills]))
        else:
            st.warning("No skills detected.")

    with tab2:
        sections_content = data.get('sections_content', {}) 
        if sections_content:
            st.write("**Content by Section:**")
            for section_name, lines in sections_content.items():
                with st.expander(f"📍 {section_name}"):
                    st.text("\n".join(lines))
        else:
            st.warning("No structured sections found. Using raw text fallback.")
    
    st.divider()

    # --- SCORING ACTION (Find Jobs) ---
    if st.button("🚀 Find Matching Jobs", type="primary"):
        with st.spinner("Consulting the AI Engine..."):
            try:
                # We resend the file bytes to ensure the backend processes the exact binary
                # This is safer than sending raw text if there are encoding issues
                files = {
                    "file": (
                        st.session_state.file_name, 
                        uploaded_file.getvalue(), 
                        uploaded_file.type
                    )
                }
                
                # Hit the SCORE endpoint
                response = requests.post(f"{API_BASE_URL}/api/v1/score_file", files=files, timeout=45)
                
                if response.status_code == 200:
                    results_data = response.json()
                    
                    if "results" in results_data:
                        st.success("✅ Jobs Found! Here are your top matches:")
                        
                        for category_block in results_data["results"]:
                            cat_name = category_block['category']
                            match_score = category_block['category_match_score']
                            
                            # Category Header
                            st.markdown(f"### 📂 {cat_name} <small>(Match: {match_score*100:.0f}%)</small>", unsafe_allow_html=True)
                            st.info(f"🤖 **AI Insight:** Why you fit this role... (Coming Soon)")
                            
                            # Job Cards
                            jobs = category_block.get('recommended_jobs', [])
                            if jobs:
                                for job in jobs:
                                    label = f"**{job['title']}** | {job['company']} ({job['match_confidence']}% Match)"
                                    
                                    with st.expander(label):
                                        c1, c2 = st.columns(2)
                                        with c1:
                                            st.write(f"🏢 **Company:** {job['company']}")
                                            st.write(f"📍 **Location:** {job['location']}")
                                            st.write(f"💰 **Salary:** {job.get('salary', 'Not Disclosed')}")
                                        with c2:
                                            st.write(f"📅 **Posted:** {job['posted_at']}")
                                            st.write(f"🌐 **Source:** {job.get('source', 'Web')}")
                                            
                                            if job.get('apply_link') and job['apply_link'] != "#":
                                                st.markdown(f"🔗 [**Apply Now**]({job['apply_link']})")
                                            else:
                                                st.caption("No direct link available")
                                                
                                            # Debug info
                                            st.caption(f"Job ID: `{job['job_id']}`")
                            else:
                                st.warning("No active listings found for this category.")
                            
                            st.divider()
                    else:
                        st.warning("No matches found. Try adding more skills to your resume.")
                else:
                    st.error(f"Server Error ({response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the Backend. Is FastAPI running?")
            except Exception as e:
                st.error(f"❌ Client Error: {e}")