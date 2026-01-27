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
    """
    Finds degrees AND University names using NER.
    """
    # Use the Education section if found, else search the whole thing
    edu_text = " ".join(sections_dict.get("Education", [])) 
    if not edu_text:
        edu_text = raw_text

    nlp = get_nlp()
    doc = nlp(edu_text)
    
    results = {
        "degrees": [],
        "institutions": []
    }

    # 1. Extract Degrees (Regex/Keyword)
    clean_edu = re.sub(r'[?|$|.|!|,]', '', edu_text)
    for word in clean_edu.split():
        if word.upper() in EDUCATION_DEGREES:
            results["degrees"].append(word.upper())

    # 2. Extract Institutions (NER: ORG)
    # We look for Organizations within the education context
    for ent in doc.ents:
        if ent.label_ == "ORG":
            # Filter for keywords like 'Institute', 'University', 'School', 'College'
            if any(key in ent.text.lower() for key in ["institute", "university", "college", "school", "nie"]):
                results["institutions"].append(ent.text)

    # 3. Format for display
    # We combine them into a list of strings for the UI
    combined = list(set(results["degrees"])) + list(set(results["institutions"]))
    return combined

def extract_email(text: str):
    # Standard, robust email regex (RFC 5322 compatibleish)
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    
    matches = re.findall(email_pattern, text)
    if matches:
        # Return the first one found, stripped of any weird punctuation
        return matches[0].strip()
    return None

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

def extract_experience_refined(sections_dict, raw_text):
    """
    Better experience detection by prioritizing the 'Experience' section.
    """
    exp_text = " ".join(sections_dict.get("Experience", []))
    if not exp_text:
        exp_text = raw_text
        
    # Standard Regex for 'X years'
    regex_matches = re.findall(r'(\d+\+?\s?(?:years|yrs|year)\s(?:of\s)?experience)', exp_text, re.IGNORECASE)
    
    # NER for Date Ranges (e.g., "June 2022 - Present")
    nlp = get_nlp()
    doc = nlp(exp_text)
    ner_dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
    
    return list(set(regex_matches + ner_dates))