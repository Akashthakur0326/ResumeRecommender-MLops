import pandas as pd
from src.parser import constant
# ✅ Direct imports to avoid circular dependency
from src.parser.utils import (
    extract_name, extract_email, extract_skills, 
    extract_education_refined, extract_experience
)
from utils.paths import SKILLS_CSV_PATH

class ResumeParserEngine:
    def __init__(self):
        # ✅ Fixed the missing helper; logic is now internal
        self.skills_list = self._load_skills()

    def _load_skills(self):
        if SKILLS_CSV_PATH.exists():
            df = pd.read_csv(SKILLS_CSV_PATH)
            return [str(s).lower().strip() for s in df.columns.values]
        return []

    def parse(self, raw_text: str) -> dict:
            sections = self.classify_sections(raw_text)
            
            # We pass 'sections' to our refined utils functions
            return {
                "name": utils.extract_name(raw_text),
                "email": utils.extract_email(raw_text),
                "education": utils.extract_education_refined(sections, raw_text), # Updated
                "skills": utils.extract_skills(raw_text, self.skills_list),
                "experience": utils.extract_experience_refined(sections, raw_text), # Updated
                "sections_found": list(sections.keys()),
                "sections_content": sections 
            }

    def classify_sections(self, text):
        line_split = [line.strip() for line in text.split("\n") if line.strip()]
        entity = {}
        key = None
        # Use lowercase for robust matching
        section_set = set([s.lower() for s in constant.RESUME_SECTIONS])

        for line in line_split:
            if len(line) == 1: continue
            line_lower = line.lower()
            # Matching section headers
            curr_key_set = set(line_lower.split(" ")) & section_set
            
            if curr_key_set:
                curr_key = list(curr_key_set)[0]
                # Map back to original casing
                orig_key = next((s for s in constant.RESUME_SECTIONS if s.lower() == curr_key), curr_key)
                entity[orig_key] = []
                key = orig_key
            elif key is not None:
                entity[key].append(line)
        
        return {k: v for k, v in entity.items() if v}