"""
STANDALONE PIPELINE — Alternative to Azure Functions hosting
"""
import argparse
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.append("ml")
sys.path.append("notifications")

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import pyodbc
import joblib

from scoring import compute_features
from rank_model import predict_score, FEATURE_COLUMNS
from send_notification import send_status_email

SKILL_KEYWORDS = [
    "python", "java", "c++", "react", "node.js", "aws", "azure", "docker",
    "kubernetes", "sql", "tensorflow", "pytorch", "nlp", "machine learning",
    "fastapi", "flask", "git", "ci/cd", "rest api", "mongodb", "postgresql",
]


def parse_resume(file_path: str) -> str:
    endpoint = os.environ["DOC_INTELLIGENCE_ENDPOINT"]
    key = os.environ["DOC_INTELLIGENCE_KEY"]
    client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)
        result = poller.result()

    full_text = "\n".join(line.content for page in result.pages for line in page.lines)
    print(f"[Phase 1] Parsed {len(full_text)} characters from resume.")
    return full_text


def extract_skills(text: str) -> list:
    endpoint = os.environ["LANGUAGE_ENDPOINT"]
    key = os.environ["LANGUAGE_KEY"]
    client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    truncated = text[:5000]
    entities_result = client.recognize_entities(documents=[truncated])[0]
    lowered = truncated.lower()
    matched = [kw for kw in SKILL_KEYWORDS if kw in lowered]

    print(f"[Phase 2] Found {len(entities_result.entities)} entities, "
          f"{len(matched)} skill keyword matches.")
    return matched


def get_job(job_id: int) -> dict:
    server = os.environ["SQL_SERVER"]
    database = os.environ["SQL_DATABASE"]
    username = os.environ["SQL_USERNAME"]
    password = os.environ["SQL_PASSWORD"]
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
        f"DATABASE={database};UID={username};PWD={password}"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT Description, RequiredSkills, MinYearsExperience FROM JobPostings WHERE JobID = ?",
        job_id,
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"No job found with JobID={job_id}. Insert one into JobPostings first.")

    description, required_skills_str, min_years = row
    return {
        "description": description,
        "required_skills": [s.strip() for s in required_skills_str.split(",")],
        "min_years": min_years,
    }


def save_application(candidate_id: int, job_id: int, features: dict, final_score: float, status: str):
    server = os.environ["SQL_SERVER"]
    database = os.environ["SQL_DATABASE"]
    username = os.environ["SQL_USERNAME"]
    password = os.environ["SQL_PASSWORD"]
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
        f"DATABASE={database};UID={username};PWD={password}"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO Applications
           (CandidateID, JobID, SemanticSimilarity, SkillOverlapScore,
            ExperienceMatchScore, FinalRankScore, Status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        candidate_id, job_id, features["semantic_similarity"],
        features["skill_overlap"], features["experience_match"],
        final_score, status,
    )
    conn.commit()
    conn.close()
    print(f"[Phase 4] Saved application record (score={final_score}, status={status})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", required=True, help="Path to resume PDF/DOCX")
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--candidate-id", type=int, default=1)
    parser.add_argument("--candidate-email", required=True)
    parser.add_argument("--candidate-name", required=True)
    parser.add_argument("--job-title", default="the position")
    args = parser.parse_args()

    resume_text = parse_resume(args.resume)
    candidate_skills = extract_skills(resume_text)
    job = get_job(args.job_id)

    features = compute_features(
        resume_text=resume_text,
        candidate_skills=candidate_skills,
        job_description=job["description"],
        required_skills=job["required_skills"],
        min_years_required=job["min_years"],
    )
    print(f"[Phase 3] Features: {json.dumps(features, indent=2)}")

    model = joblib.load("ml/rank_model.joblib")
    final_score = predict_score(model, features)
    status = "Shortlisted" if final_score >= 0.6 else "Received"
    print(f"[Phase 3] Final score: {final_score} -> Status: {status}")

    save_application(args.candidate_id, args.job_id, features, final_score, status)

    send_status_email(
        recipient_email=args.candidate_email,
        candidate_name=args.candidate_name,
        status=status,
        job_title=args.job_title,
    )
    print("[Phase 6] Notification email sent.")

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()