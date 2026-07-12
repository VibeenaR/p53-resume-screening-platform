"""
PHASE 5: End-to-End Orchestration (code-only alternative to Logic Apps)

Trigger: HTTP POST with { "candidate_blob_name": "...", "job_id": 1 }
This is the simplest way to demo the full pipeline in one call for your
portfolio/interview, without needing to set up Logic Apps visually.

Flow:
  1. Read parsed resume text + extracted skills from Blob Storage
     (assumes parse_resume and extract_skills functions already ran)
  2. Fetch job requirements from Azure SQL
  3. Compute features (scoring.py) and rank score (rank_model.py)
  4. Insert result into Applications table
  5. Trigger notification email

For true "Logic Apps" orchestration (drag-and-drop, no code), see
docs/logic_app_workflow.md instead -- functionally equivalent.
"""
import json
import logging
import os
import azure.functions as func
import pyodbc
import joblib

from azure.storage.blob import BlobServiceClient
import sys
sys.path.append("../../ml")
from scoring import compute_features
from rank_model import predict_score, FEATURE_COLUMNS

import sys as _sys
_sys.path.append("../../notifications")
from send_notification import send_status_email


def get_sql_connection():
    server = os.environ["SQL_SERVER"]
    database = os.environ["SQL_DATABASE"]
    username = os.environ["SQL_USERNAME"]
    password = os.environ["SQL_PASSWORD"]
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
        f"DATABASE={database};UID={username};PWD={password}"
    )
    return pyodbc.connect(conn_str)


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        candidate_blob_name = body["candidate_blob_name"]  # e.g. "john_doe.json"
        job_id = body["job_id"]

        storage_conn = os.environ["STORAGE_CONNECTION_STRING"]
        blob_service = BlobServiceClient.from_connection_string(storage_conn)

        # Step 1: read parsed text (from Phase 1 output)
        parsed_client = blob_service.get_blob_client(container="parsed", blob=candidate_blob_name)
        parsed_data = json.loads(parsed_client.download_blob().readall())
        resume_text = parsed_data["full_text"]

        # Step 1b: read extracted skills (from Phase 2 output)
        extracted_client = blob_service.get_blob_client(container="extracted", blob=candidate_blob_name)
        extracted_data = json.loads(extracted_client.download_blob().readall())
        candidate_skills = extracted_data["matched_skills"]

        # Step 2: fetch job info from SQL
        conn = get_sql_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Description, RequiredSkills, MinYearsExperience FROM JobPostings WHERE JobID = ?",
            job_id,
        )
        row = cursor.fetchone()
        job_description, required_skills_str, min_years = row
        required_skills = [s.strip() for s in required_skills_str.split(",")]

        # Step 3: compute features + rank score
        features = compute_features(
            resume_text=resume_text,
            candidate_skills=candidate_skills,
            job_description=job_description,
            required_skills=required_skills,
            min_years_required=min_years,
        )

        model = joblib.load("../../ml/rank_model.joblib")
        final_score = predict_score(model, features)

        status = "Shortlisted" if final_score >= 0.6 else "Received"

        # Step 4: insert into Applications table
        cursor.execute(
            """INSERT INTO Applications
               (CandidateID, JobID, SemanticSimilarity, SkillOverlapScore,
                ExperienceMatchScore, FinalRankScore, Status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            body["candidate_id"], job_id, features["semantic_similarity"],
            features["skill_overlap"], features["experience_match"],
            final_score, status,
        )
        conn.commit()

        # Step 5: notify candidate
        send_status_email(
            recipient_email=body["candidate_email"],
            candidate_name=body["candidate_name"],
            status=status,
            job_title=body.get("job_title", "the position"),
        )

        return func.HttpResponse(
            json.dumps({"final_score": final_score, "status": status}),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        logging.exception("Orchestrator failed")
        return func.HttpResponse(str(e), status_code=500)
