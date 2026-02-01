import nltk
from utils.paths import NLTK_DATA_PATH

# 1. Force NLTK to use local DVC Artifacts
nltk.data.path.append(str(NLTK_DATA_PATH))

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import nltk
import sys
from pathlib import Path

# Reach Root logic
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils.paths import NLTK_DATA_PATH

# 1. Force NLTK to use local path
nltk.data.path.append(str(NLTK_DATA_PATH))

# ---------------------------------------------------------
# SELF-HEALING NLTK DOWNLOADER
# ---------------------------------------------------------
def ensure_nltk_resources():
    """
    Checks for required NLTK resources and downloads them if missing.
    This acts as a backup if DVC or Docker build missed them.
    """
    resources = [
        ("corpora/stopwords", "stopwords"),
        ("tokenizers/punkt", "punkt"),
        ("tokenizers/punkt_tab", "punkt_tab") # <--- The critical missing piece
    ]

    for path_id, download_id in resources:
        try:
            nltk.data.find(path_id)
        except LookupError:
            print(f"⚠️ NLTK resource '{download_id}' not found. Downloading to {NLTK_DATA_PATH}...")
            try:
                nltk.download(download_id, download_dir=str(NLTK_DATA_PATH), quiet=True)
                print(f"✅ Downloaded {download_id}")
            except Exception as e:
                print(f"❌ Failed to download {download_id}: {e}")

# Run the check immediately on import
ensure_nltk_resources()

try:
    STOPWORDS = set(nltk.corpus.stopwords.words("english"))
except LookupError:
    # Fallback if download failed (shouldn't happen with above logic)
    STOPWORDS = set()

# 2. Regex Patterns
EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
PHONE_REGEX = r"(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})"


NAME_PATTERN = NAME_PATTERN = [
    [{'POS': 'PROPN'}, {'POS': 'PROPN'}],                      # Two words
    [{'POS': 'PROPN'}, {'POS': 'PROPN'}, {'POS': 'PROPN'}]    # Three words
]

# Education (Upper Case Mandatory)
EDUCATION_DEGREES = [
            'BE', 'B.E.', 'B.E', 'BS', 'B.S', 'ME', 'M.E',
            'M.E.', 'MS', 'M.S', 'BTECH', 'MTECH',
            'SSC', 'HSC', 'CBSE', 'ICSE', 'X', 'XII','B.TECH'
        ]

NOT_ALPHA_NUMERIC = r'[^a-zA-Z\d]'

NUMBER = r'\d+'

# For finding date ranges
MONTHS_SHORT = r'''(jan)|(feb)|(mar)|(apr)|(may)|(jun)|(jul)
                   |(aug)|(sep)|(oct)|(nov)|(dec)'''
MONTHS_LONG = r'''(january)|(february)|(march)|(april)|(may)|(june)|(july)|
                   (august)|(september)|(october)|(november)|(december)'''
MONTH = r'(' + MONTHS_SHORT + r'|' + MONTHS_LONG + r')'
YEAR = r'(((20|19)(\d{2})))'



RESUME_SECTIONS = [
                    'accomplishments',
                    'experience',
                    'education',
                    'interests',
                    'projects',
                    'professional experience',
                    'publications',
                    'skills',
                    'certifications',
                    'objective',
                    'career objective',
                    'summary',
                    'leadership'
                ]

JOB_SECTION = [
    "experiences",
    "skills",
    "education",
]
