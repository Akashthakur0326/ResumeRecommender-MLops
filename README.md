ResumeRecommenderMLops/
│
├── .github/
│   └── workflows/
│       └── serpapi_data_ingestion_monthly.yml # Automated Monthly Ingestion (GitHub Actions)
│
├── artifacts/                                # DVC-tracked ML artifacts (Model weights, scalers)
│
├── data/                                     # Data storage (DVC managed)
│   ├── labeled_jobs_for_training.csv         # Historical ground-truth labels for classifiers
│   ├── synthetic_for_training.csv            # Generated data for model cold-starts
│   ├── constants/                            # Static reference configs
│   │   ├── jobs.csv                          # Canonical job titles for matching
│   │   ├── locations.yaml                    # Geography normalization rules
│   │   └── KB/
│   │       └── detailed_job_descriptions.json # Domain knowledge for LLM labeling
│   ├── final/                                # Production-ready labeled datasets
│   │   └── serpapi/
│   │       └── 2026-01.csv                   # Categorized job results
│   ├── processed/                            # Normalized intermediate data
│   │   └── serpapi/
│   │       ├── 2026-01.csv                   # Cleaned but unlabeled CSV
│   │       └── processing.log                # In-folder data transformation logs
│   └── raw/                                  # Immutable ingestion point
│       └── serpapi/
│           └── 2026-01/                      # Monthly folder containing raw JSON pages
│
├── data_ingestion/                           # Multi-source ingestion logic
│   ├── jd_ingestion/                         # Job Description (JD) sources
│   │   ├── bright_data/                      # Logic for alternate data scraping
│   │   └── serp_api/
│   │       ├── priority_scheduler.py          # Logic for job prioritization per run
│   │       ├── serpapi_client.py             # API wrapper for Google Jobs
│   │       └── serpapi_ingest.py             # Main execution script for JD fetch
│   ├── processors/
│   │   └── process_data.py                   # Normalizes raw JSON to clean CSV
│   └── resume_ingestion/                     # User-side data ingestion
│       ├── docx_ingest.py                    # Extraction logic for Word docs
│       ├── image_ingest.py                   # OCR logic for image-based resumes
│       └── pdf_ingest.py                     # Extraction logic for PDF resumes
│
├── db/                                       # (Placeholder) Persistent database storage
│
├── logs/                                     # System-wide logging
│   ├── pipeline/
│   │   └── pipeline_mgmt.log                 # Logs for update_params and DVC orchestration
│   └── serpapi/
│       └── 2026-01.log                       # Detailed API logs for specific months
│
├── mlruns/                                   # Local MLflow tracking data (Experiments)
│
├── notebooks/                                # Experimentation & EDA
│   ├── n1.ipynb                              # General scratchpad
│   ├── rr_categorizer_experimentation.ipynb  # Local model training testing
│   └── rr_categorizing_data_gemini.ipynb     # LLM-based labeling R&D
│
├── prompts/                                  # LLM Engineering (Prompt Management)
│   ├── gemini_based_labelling_prompt.txt     # System prompt for LLM categorization
│   └── job_description_KB.txt                # Context window data for RAG/Labeling
│
├── src/                                      # Core production logic
│   ├── label_jobs.py                         # Production inference for categorization
│   └── update_params.py                      # Automated Regex-based params sync
│
├── utils/                                    # Shared foundational utilities
│   ├── dates.py                              # UTC and string-date handling
│   ├── logger.py                             # Standardized logging setup
│   └── paths.py                              # Centralized Pathlib management
│
├── .dvcignore                                # DVC exclusion rules
├── .env                                      # Secrets (SERP_API_KEY, MLFLOW_URI)
├── .gitattributes                            # Git LFS/Config attributes
├── .gitignore                                # Git exclusion rules
├── dvc.lock                                  # DVC state hash (critical for reproducibility)
├── dvc.yaml                                  # Pipeline stage definitions (Ingest->Process->Label)
├── mlflow.db                                 # SQLite backend for MLflow tracking
├── params.yaml                               # Centralized configuration (Month, API limits)
├── pyproject.toml                            # Metadata & build system config
├── README.md                                 # Project documentation
├── requirements.txt                          # Production dependencies
├── resume_recommender_mlops.egg-info/        # Local package installation metadata
└── status.txt                                # Manual tracking of pipeline health/notes


concerns 
--> making a parameter based postgreSQL for proper jump bw local setup and cloud setup based db
--> setting up a corn job for the data ingestion for jd and setting them up with the dp 


REMINDER 
--> remember to take data/constants out of git ignore and add it to be tracked by git tracking it with dvc creates conflict 
--> always run python src/update_params.py before every dvc repro as that updates the params.yaml to current month-year


TO DO 
--> make a embedding space for each category
--> add it to postgreSQL as a faiss index 

--> make a resume ingetion cycle
--> make frontpage streamlit
--> make resume parser for docx,image,pdf
--> make a scorer for the given resume on each category 

--> make a KB out of all jd in csv and the categories define by gemini 
--> get cypher out of them 
--> add them to auraDB
--> make a connection bw auraDB and groq and try to infer and add reasoning 