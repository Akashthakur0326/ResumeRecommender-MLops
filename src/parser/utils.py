import re
import pandas as pd
import nltk
import spacy
import sys
from pathlib import Path
from nltk.util import ngrams
from spacy.matcher import Matcher

# Reach Root logic
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils.paths import SKILLS_CSV_PATH, NLTK_DATA_PATH
from src.parser.constant import EDUCATION_DEGREES, NAME_PATTERN, EMAIL_REGEX

_nlp_instance = None

def get_nlp():
    global _nlp_instance
    if _nlp_instance is None:
        try:
            _nlp_instance = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp_instance = spacy.load("en_core_web_sm")
    return _nlp_instance

def clean_text(text: str) -> str:
    text = re.sub(r'http\S+\s*', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_name(text):
    nlp = get_nlp()
    # First 50 words is a good heuristic for name location
    doc = nlp(" ".join(text.split()[:50]))
    matcher = Matcher(nlp.vocab)
    matcher.add("NAME", NAME_PATTERN)
    matches = matcher(doc)
    
    for _, start, end in matches:
        span = doc[start:end]
        if "resume" not in span.text.lower():
            return span.text
    return None

def extract_education_refined(sections_dict, raw_text):
    # Prefer structured sections, fallback to raw string
    edu_text = " ".join(sections_dict.get("education", [])) if "education" in sections_dict else raw_text
    
    found_degrees = []
    clean_edu = re.sub(r'[?|$|.|!|,]', '', edu_text)
    for word in clean_edu.split():
        if word.upper() in EDUCATION_DEGREES:
            found_degrees.append(word.upper())
    return list(set(found_degrees))

def extract_email(text: str):
    email = re.findall(EMAIL_REGEX, text)
    return email[0].split()[0].strip() if email else None

def extract_skills(text: str, skills_list: list):
    text = clean_text(text).lower()
    tokens = nltk.word_tokenize(text)
    found_skills = set()

    for token in tokens:
        if token in skills_list: found_skills.add(token)
    for bg in ngrams(tokens, 2):
        bg_str = " ".join(bg)
        if bg_str in skills_list: found_skills.add(bg_str)
    for tg in ngrams(tokens, 3):
        tg_str = " ".join(tg)
        if tg_str in skills_list: found_skills.add(tg_str)
    return list(found_skills)

def extract_experience(text: str):
    regex_matches = re.findall(r'(\d+\+?\s?(?:years|yrs|year)\s(?:of\s)?experience)', text, re.IGNORECASE)
    nlp = get_nlp()
    doc = nlp(text)
    ner_matches = [ent.text for ent in doc.ents if ent.label_ == "DATE" and "experience" in text[max(ent.start_char-20,0):ent.end_char+20].lower()]
    return list(set(regex_matches + ner_matches))