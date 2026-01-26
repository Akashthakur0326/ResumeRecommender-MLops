import nltk
from utils.paths import NLTK_DATA_PATH

# 1. Force NLTK to use local DVC Artifacts
nltk.data.path.append(str(NLTK_DATA_PATH))

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    STOPWORDS = set(nltk.corpus.stopwords.words("english"))
except LookupError:
    print(f"⚠️ NLTK data not found. Fallback download to {NLTK_DATA_PATH}")
    nltk.download("stopwords", download_dir=str(NLTK_DATA_PATH))
    STOPWORDS = set(nltk.corpus.stopwords.words("english"))

# 2. Regex Patterns
EMAIL_REGEX = r"([^@|\s]+@[^@]+\.[^@|\s]+)"
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
