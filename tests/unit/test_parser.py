from src.parser.resume_parser import parse_resume # Update import path to match yours
import os

def test_parser_exists():
    # Simple sanity check
    file_path = "tests/data/dummy_resume.pdf"
    assert os.path.exists(file_path), "Dummy resume is missing!"

def test_parse_logic():
    # Since we can't easily parse a dummy PDF without real OCR libraries sometimes,
    # we can also test the text cleaning functions directly.
    from src.parser.cleaner import clean_text
    raw = "I know   Python  and \n SQL."
    cleaned = clean_text(raw)
    assert cleaned == "I know Python and SQL."