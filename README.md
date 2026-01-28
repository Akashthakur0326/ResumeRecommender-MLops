ResumeRecommenderMLops/
├── .github/workflows/          # CI/CD Automation
│   ├── mlops_pipeline.yml      # Orchestrates DVC repro and model staging
│   └── serpapi_data_ingestion_monthly.yml # Automated JD scraping schedule
│
├── app/                        # Backend Service Layer (FastAPI)
│   ├── api/
│   │   └── main.py             # FastAPI entry point; handles model lifespan & routes
│   └── services/
│       └── score_resume.py     # Two-stage scoring logic (Category Match -> Job Match)
│
├── artifacts/                  # DVC-Tracked non-model assets
│   ├── nltk_data/              # Pre-downloaded NLTK corpora for text parsing
│   └── nltk_data.dvc           # DVC pointer for NLTK assets
│
├── data/                       # Data Tier (DVC Managed)
│   ├── raw/serpapi/            # Immutable storage for monthly raw JSON search results
│   ├── processed/serpapi/      # Cleaned/Normalized CSVs ready for labeling
│   ├── final/serpapi/          # Production CSVs with categories and vector flags
│   ├── constants/              # Reference datasets (Job titles, Locations, Knowledge Base)
│   └── labeled_jobs_for_training.csv # Ground truth for classification experiments
│
├── data_ingestion/             # ETL Pipelines
│   ├── jd_ingestion/           # Scripts to fetch Job Descriptions (SerpAPI/BrightData)
│   ├── resume_ingestion/       # Parser factory (PDF, DOCX, Image OCR, TXT)
│   ├── roles_ingestion/        # Script to populate 'role_definitions' in Postgres
│   └── processors/             # Data cleaning and JSON-to-CSV transformation
│
├── db/                         # Database schema and migration scripts
│   ├── cypher_defination.txt   # Graph DB/Neo4j query templates (if applicable)
│   └── DB.txt                  # General SQL schema and notes
│
├── logs/                       # Centralized System Logging
│   ├── scoring.log             # Tracks recommendation requests and scores
│   ├── vector_db_ingestion.log # Logs for pgvector indexing progress
│   ├── pipeline/               # Orchestration logs
│   └── serpapi/                # API-specific ingestion logs
│
├── mlruns/                     # MLflow experiment tracking data
│
├── models/                     # Model Registry (DVC Managed)
│   ├── all-mpnet-base-v2/      # Local weights for the Transformer encoder
│   └── all-mpnet-base-v2.dvc   # DVC pointer for model weights
│
├── notebooks/                  # R&D and Experimentation
│   ├── rr_categorizer_experimentation.ipynb # Local classifier testing
│   └── rr_categorizing_data_gemini.ipynb    # LLM-based zero-shot labeling R&D
│
├── prompts/                    # LLM Engineering
│   ├── gemini_based_labelling_prompt.txt    # System prompt for JD classification
│   └── text_to_triplets_for_cyphers_prompt.txt # Prompt for Knowledge Graph extraction
│
├── scripts/                    # Maintenance & Debugging
│   ├── debug_DB.py             # Checks database health and category alignment
│   └── download_model_OT.py    # One-time script to fetch models from HF
│
├── src/                        # Production Logic
│   ├── parser/                 # Resume parsing engine (Section extraction, cleaning)
│   ├── vector_db/              # pgvector Client, Encoder, and Ingestion logic
│   ├── label_jobs.py           # Production inference for JD labeling
│   └── update_params.py        # Syncs Regex and logic across the pipeline
│
├── ui/                         # User Interface Layer
│   └── app.py                  # Streamlit frontend for resume upload and job display
│
├── utils/                      # Shared Foundational Utilities
│   ├── dates.py                # Formatting for monthly ingestion cycles
│   ├── logger.py               # Standardized Loguru/Logging configuration
│   └── paths.py                # Centralized Pathlib management for local/Docker
│
├── .env                        # Secrets (API Keys, DB Credentials)
├── docker_compose.yml          # Local orchestration for FastAPI, Streamlit, & Postgres
├── dvc.yaml                    # DVC pipeline DAG (Ingest -> Process -> Embed -> Label)
├── params.yaml                 # Centralized hyperparameter and config management
├── requirements.txt            # Python dependency manifest
└── README.md                   # Project documentation and setup guide

concerns 
--> making a parameter based postgreSQL for proper jump bw local setup and cloud setup based db
--> setting up a corn job for the data ingestion for jd and setting them up with the dp 


REMINDER 
--> remember to take data/constants out of git ignore and add it to be tracked by git tracking it with dvc creates conflict 
--> always run python src/update_params.py before every dvc repro as that updates the params.yaml to current month-year


TO DO 

--> add the playwright based parser for naukri to current implementation
--> generate all the possible cyphers 
--> make a inference cycle using groq
--> add the reasoning layer 