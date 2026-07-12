"""
Manual Labeling Tool — builds a small real-judgment training dataset

Instead of the synthetic bootstrap rule in rank_model.py, this lets you
manually score a handful of real (or realistic) resume/job pairs
yourself, so the model learns from actual judgment rather than an
automated rule.

Usage:
    python label_data.py --resume resume1.pdf --job-id 1

For each resume/job pair, it computes the same features as the real
pipeline, shows them to you, and asks you to decide: would you
shortlist this candidate? (yes/no). Your answer is appended to
manual_training_data.csv.

Do this for ~15-30 different resume/job combinations (mix strong and
weak matches) to get a dataset large enough to retrain on.

Once you have enough labeled rows, run:
    python ml/rank_model.py --data manual_training_data.csv
"""
import argparse
import csv
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.append("ml")

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import pyodbc

from scoring import compute_features

SKILL_KEYWORDS = [
    "python", "java", "c++", "react", "node.js", "aws", "azure", "docker",
    "kubernetes", "sql", "tensorflow", "pytorch", "nlp", "machine learning",
    "fastapi", "flask", "git", "ci/cd", "rest api", "mongodb", "postgresql",
]

OUTPUT_CSV = "manual_training_data.csv"


def parse_resume(file_path: str) -> str:
    endpoint = os.environ["DOC_INTELLIGENCE_ENDPOINT"]
    key = os.environ["DOC_INTELLIGENCE_KEY"]
    client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)
        result = poller.result()
    return "\n".join(line.content for page in result.pages for line in page.lines)


def extract_skills(text: str) -> list:
    endpoint = os.environ["LANGUAGE_ENDPOINT"]
    key = os.environ["LANGUAGE_KEY"]
    client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    truncated = text[:5000]
    lowered = truncated.lower()
    return [kw for kw in SKILL_KEYWORDS if kw in lowered]


def get_job(job_id: int) -> dict:
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={os.environ['SQL_SERVER']};"
        f"DATABASE={os.environ['SQL_DATABASE']};UID={os.environ['SQL_USERNAME']};"
        f"PWD={os.environ['SQL_PASSWORD']}"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT Description, RequiredSkills, MinYearsExperience FROM JobPostings WHERE JobID = ?",
        job_id,
    )
    row = cursor.fetchone()
    conn.close()
    description, required_skills_str, min_years = row
    return {
        "description": description,
        "required_skills": [s.strip() for s in required_skills_str.split(",")],
        "min_years": min_years,
    }


def append_row(features: dict, label: int):
    file_exists = os.path.isfile(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "semantic_similarity", "skill_overlap", "experience_match", "label"
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "semantic_similarity": features["semantic_similarity"],
            "skill_overlap": features["skill_overlap"],
            "experience_match": features["experience_match"],
            "label": label,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", required=True)
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()

    print("Parsing resume and job...")
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

    print("\n--- Candidate Features ---")
    print(f"Semantic similarity : {features['semantic_similarity']}")
    print(f"Skill overlap       : {features['skill_overlap']}")
    print(f"Experience match    : {features['experience_match']}")
    print(f"Job description     : {job['description'][:150]}...")
    print("---------------------------\n")

    answer = input("Would you shortlist this candidate? (y/n): ").strip().lower()
    label = 1 if answer == "y" else 0

    append_row(features, label)
    print(f"\nSaved to {OUTPUT_CSV} with label={label}. Repeat for more resume/job pairs.")


if __name__ == "__main__":
    main()