import streamlit as st
import requests
import os

# --- CONFIG ---
# On Localhost, this defaults to "http://127.0.0.1:8000"
# On AWS Docker, we change this env var to "http://backend_container:8000"
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Resume Intelligence", layout="wide", page_icon="🧠")

# --- INITIALIZE STATE ---
if "file_name" not in st.session_state: st.session_state.file_name = None
if "parsed_data" not in st.session_state: st.session_state.parsed_data = None
if "raw_text" not in st.session_state: st.session_state.raw_text = None
if "file_bytes" not in st.session_state: st.session_state.file_bytes = None
# ✅ NEW: Cache for the fast scoring results so they persist
if "results_cache" not in st.session_state: st.session_state.results_cache = None

st.title("📄 Resume Intelligence Parser")

# --- UPLOAD & PARSE LOGIC ---
uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "txt"])

if uploaded_file:
    # Save bytes to state immediately
    file_bytes = uploaded_file.getvalue()
    st.session_state.file_bytes = file_bytes

    # 1. Size Safety Check (2MB)
    if len(file_bytes) > 2 * 1024 * 1024:
        st.error("File too large. Max size is 2MB.")
        st.stop()

    # 2. Trigger Parsing ONLY if the file is new
    if st.session_state.file_name != uploaded_file.name:
        with st.spinner("🧠 Extracting Resume Structure..."):
            try:
                files = {"file": (uploaded_file.name, file_bytes, uploaded_file.type)}
                response = requests.post(f"{API_BASE_URL}/api/v1/parse_resume", files=files, timeout=30)
                
                if response.status_code == 200:
                    parsed_json = response.json()
                    
                    # Store in Session State
                    st.session_state.parsed_data = parsed_json
                    st.session_state.raw_text = parsed_json.get("raw_text", "")
                    st.session_state.file_name = uploaded_file.name
                    # Reset results when a new file is uploaded
                    st.session_state.results_cache = None 
                    
                    st.success("✅ Resume Parsed Successfully!")
                    st.rerun()
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
    with col1: st.info(f"📧 **Email:** {data.get('email', 'Not found')}")
    with col2: 
        edu = data.get('education', [])
        st.info(f"🎓 **Education:** {', '.join(edu) if edu else 'Not detected'}")
    with col3:
        exp = data.get('experience', [])
        st.info(f"💼 **Experience:** {len(exp)} items detected")

    # 3. Skills & Structure Tabs
    tab1, tab2 = st.tabs(["🛠️ Skills Detected", "📑 Structure Analysis"])
    with tab1:
        skills = data.get('skills', [])
        if skills: st.write(", ".join([f"`{s}`" for s in skills]))
        else: st.warning("No skills detected.")
    with tab2:
        sections_content = data.get('sections_content', {}) 
        if sections_content:
            for section_name, lines in sections_content.items():
                with st.expander(f"📍 {section_name}"):
                    st.text("\n".join(lines))
        else: st.warning("No structured sections found.")
    
    st.divider()

    # ============================================================
    # 🚀 FAST PATH: GET JOBS ONLY
    # ============================================================
    if st.button("🚀 Find Matching Jobs", type="primary"):
        with st.spinner("Scanning Job Market..."):
            try:
                files = {
                    "file": (st.session_state.file_name, st.session_state.file_bytes, uploaded_file.type)
                }
                # Call the FAST endpoint (No AI)
                response = requests.post(f"{API_BASE_URL}/api/v1/score_file", files=files, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.results_cache = data["results"]
                    st.rerun() # Refresh to show results below
                else:
                    st.error(f"Server Error ({response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the Backend.")
            except Exception as e:
                st.error(f"❌ Client Error: {e}")

    # ============================================================
    # 🧠 RESULTS DISPLAY (Lazy Loading)
    # ============================================================
    if st.session_state.results_cache:
        st.success("✅ Jobs Found! (Click 'Generate AI Analysis' for insights)")
        
        for i, category_block in enumerate(st.session_state.results_cache):
            cat_name = category_block['category']
            match_score = category_block['category_match_score']
            
            # --- 1. Category Header ---
            st.markdown(f"### 📂 {cat_name} <small>(Match: {match_score*100:.0f}%)</small>", unsafe_allow_html=True)
            
            # --- 2. LAZY AI BUTTON ---
            # Unique keys for state persistence
            insight_key = f"insight_{i}"
            btn_key = f"btn_ai_{i}"
            
            # Check if we already have the insight in session state
            if insight_key in st.session_state:
                ai_data = st.session_state[insight_key]
                
                # Display the Insight
                with st.container():
                    st.markdown("#### 🤖 AI Hiring Manager Feedback")
                    c1, c2 = st.columns(2)
                    with c1: st.success(f"**✅ Strengths:**\n\n{ai_data.get('strength_analysis')}")
                    with c2: st.error(f"**⚠️ Hard Truths:**\n\n{ai_data.get('hard_truth_gaps')}")
                    st.info(f"**🔄 Strategic Pivot:**\n\n{ai_data.get('strategic_pivot')}")
                    
            else:
                # Show Button if not loaded yet
                if st.button(f"✨ Generate AI Analysis for {cat_name}", key=btn_key):
                    with st.spinner("Consulting Knowledge Graph & Llama-3..."):
                        try:
                            # Prepare Payload from context saved in Fast Step
                            ctx = category_block['context_for_ai']
                            payload = {
                                "resume_text": st.session_state.raw_text,
                                "category": cat_name,
                                "user_skills": ctx['user_skills'],
                                "matched_jobs": ctx['matched_jobs'],
                                "gap_jobs": ctx['gap_jobs']
                            }
                            
                            # Call the SLOW endpoint
                            res = requests.post(f"{API_BASE_URL}/api/v1/generate_insight", json=payload, timeout=60)
                            
                            if res.status_code == 200:
                                st.session_state[insight_key] = res.json()
                                st.rerun() # Refresh to show the insight card
                            else:
                                st.error("AI Service Busy. Try again.")
                        except Exception as e:
                            st.error(f"AI Connection Failed: {e}")

            st.write("**📄 Recommended Roles:**")
            
            # --- 3. Job Cards ---
            jobs = category_block.get('recommended_jobs', [])
            if jobs:
                for job in jobs:
                    label = f"**{job['title']}** | {job['company']} ({job['match_confidence']}% Match)"
                    with st.expander(label):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"📍 **Location:** {job['location']}")
                            st.write(f"💰 **Salary:** {job.get('salary', 'N/A')}")
                        with c2:
                            st.write(f"📅 **Posted:** {job['posted_at']}")
                            if job.get('apply_link'):
                                st.markdown(f"🔗 [**Apply Now**]({job['apply_link']})")
            else:
                st.caption("No specific listings found.")
            
            st.divider()