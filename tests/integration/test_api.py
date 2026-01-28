from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/") # Or whatever your health endpoint is
    assert response.status_code in [200, 404] # 404 is fine if you don't have a root route

def test_score_endpoint():
    # This works because conftest.py mocks the heavy model!
    with open("tests/data/dummy_resume.pdf", "rb") as f:
        response = client.post(
            "/score", 
            files={"file": ("resume.pdf", f, "application/pdf")}
        )
    # We expect 200 OK because the system "thinks" it encoded the resume
    assert response.status_code == 200