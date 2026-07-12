import os
import sys
import json
from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Update path to include subdirectories for modules
sys.path.append("ml")
sys.path.append("notifications")

# Azure and ML imports
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import pyodbc
import joblib

from scoring import compute_features
from rank_model import predict_score
from send_notification import send_status_email

# Initialize Flask App
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configuration Constants
SKILL_KEYWORDS = [
    "python", "java", "c++", "react", "node.js", "aws", "azure", "docker",
    "kubernetes", "sql", "tensorflow", "pytorch", "nlp", "machine learning",
    "fastapi", "flask", "git", "ci/cd", "rest api", "mongodb", "postgresql",
]

MODEL = None

def get_model():
    global MODEL
    if MODEL is None:
        # Ensure the path matches your project structure
        MODEL = joblib.load("ml/rank_model.joblib")
    return MODEL

def get_sql_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={os.environ['SQL_SERVER']};"
        f"DATABASE={os.environ['SQL_DATABASE']};UID={os.environ['SQL_USERNAME']};"
        f"PWD={os.environ['SQL_PASSWORD']}"
    )
    return pyodbc.connect(conn_str)

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
    conn = get_sql_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT Title, Description, RequiredSkills, MinYearsExperience FROM JobPostings WHERE JobID = ?",
        job_id,
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    title, description, required_skills_str, min_years = row
    return {
        "title": title,
        "description": description,
        "required_skills": [s.strip() for s in required_skills_str.split(",")],
        "min_years": min_years,
    }

def get_all_jobs() -> list:
    conn = get_sql_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT JobID, Title FROM JobPostings ORDER BY JobID")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1]} for r in rows]

def get_or_create_candidate(name: str, email: str, resume_path: str, parsed_text: str, skills: list) -> int:
    conn = get_sql_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CandidateID FROM Candidates WHERE Email = ?", email)
    row = cursor.fetchone()
    if row:
        candidate_id = row[0]
    else:
        cursor.execute(
            """INSERT INTO Candidates (FullName, Email, ResumeBlobPath, ParsedText, ExtractedSkills)
               OUTPUT INSERTED.CandidateID
               VALUES (?, ?, ?, ?, ?)""",
            name, email, resume_path, parsed_text[:4000], json.dumps(skills),
        )
        candidate_id = cursor.fetchone()[0]
        conn.commit()
    conn.close()
    return candidate_id

def save_application(candidate_id: int, job_id: int, features: dict, final_score: float, status: str):
    conn = get_sql_connection()
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

UPLOAD_FORM = """
<!doctype html>
<html>
<head>
  <title>P53 - Resume Screening</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
    h1 { color: #2c3e50; }
    label { display: block; margin-top: 16px; font-weight: bold; }
    input, select { width: 100%; padding: 8px; margin-top: 6px; box-sizing: border-box; }
    button { margin-top: 24px; padding: 12px 24px; background: #2c7be5; color: white;
             border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
    .result { margin-top: 30px; padding: 20px; border-radius: 6px; }
    .shortlisted { background: #d4edda; border: 1px solid #c3e6cb; }
    .received { background: #fff3cd; border: 1px solid #ffeeba; }
    .error { background: #f8d7da; border: 1px solid #f5c6cb; }
  </style>
</head>
<body>
  <h1>P53 — AI Resume Screening</h1>
  <form method="POST" enctype="multipart/form-data">
    <label>Resume (PDF)</label>
    <input type="file" name="resume" accept=".pdf" required>

    <label>Your Name</label>
    <input type="text" name="candidate_name" required>

    <label>Your Email</label>
    <input type="email" name="candidate_email" required>

    <label>Job Posting</label>
    <select name="job_id" required>
      {% for job in jobs %}
        <option value="{{ job.id }}">{{ job.title }} (Job ID {{ job.id }})</option>
      {% endfor %}
    </select>

    <button type="submit">Submit Application</button>
  </form>

  {% if result %}
    <div class="result {{ result.css_class }}">
      <h3>{{ result.heading }}</h3>
      <p>{{ result.message }}</p>
      {% if result.features %}
        <ul>
          <li>Semantic similarity: {{ result.features.semantic_similarity }}</li>
          <li>Skill overlap: {{ result.features.skill_overlap }}</li>
          <li>Experience match: {{ result.features.experience_match }}</li>
          <li>Final score: {{ result.final_score }}</li>
        </ul>
      {% endif %}
    </div>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload():
    jobs = get_all_jobs()
    result = None

    if request.method == "POST":
        try:
            file = request.files["resume"]
            candidate_name = request.form["candidate_name"]
            candidate_email = request.form["candidate_email"]
            job_id = int(request.form["job_id"])

            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            resume_text = parse_resume(file_path)
            candidate_skills = extract_skills(resume_text)

            job = get_job(job_id)
            if job is None:
                raise ValueError(f"No job found with ID {job_id}")

            features = compute_features(
                resume_text=resume_text,
                candidate_skills=candidate_skills,
                job_description=job["description"],
                required_skills=job["required_skills"],
                min_years_required=job["min_years"],
            )
            model = get_model()
            final_score = predict_score(model, features)
            status = "Shortlisted" if final_score >= 0.6 else "Received"

            candidate_id = get_or_create_candidate(
                candidate_name, candidate_email, file_path, resume_text, candidate_skills
            )
            save_application(candidate_id, job_id, features, final_score, status)

            send_status_email(
                recipient_email=candidate_email,
                candidate_name=candidate_name,
                status=status,
                job_title=job["title"],
            )

            css_class = "shortlisted" if status == "Shortlisted" else "received"
            heading = "🎉 You've been Shortlisted!" if status == "Shortlisted" else "Application Received"
            message = (
                f"Your application for '{job['title']}' has been processed. "
                f"An email confirmation has been sent to {candidate_email}."
            )

            result = {
                "css_class": css_class,
                "heading": heading,
                "message": message,
                "features": features,
                "final_score": final_score,
            }

        except Exception as e:
            result = {
                "css_class": "error",
                "heading": "Something went wrong",
                "message": str(e),
                "features": None,
                "final_score": None,
            }

    return render_template_string(UPLOAD_FORM, jobs=jobs, result=result)