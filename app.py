import os
import sys
import json
from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename

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
        MODEL = joblib.load("ml/rank_model.joblib")
    return MODEL

def get_sql_connection():
    # Fetching environment variables directly
    server = os.environ.get('SQL_SERVER')
    database = os.environ.get('SQL_DATABASE')
    username = os.environ.get('SQL_USERNAME')
    password = os.environ.get('SQL_PASSWORD')
    
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
        f"DATABASE={database};UID={username};PWD={password}"
    )
    return pyodbc.connect(conn_str)

def parse_resume(file_path: str) -> str:
    endpoint = os.environ.get("DOC_INTELLIGENCE_ENDPOINT")
    key = os.environ.get("DOC_INTELLIGENCE_KEY")
    client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)
        result = poller.result()
    return "\n".join(line.content for page in result.pages for line in page.lines)

def extract_skills(text: str) -> list:
    endpoint = os.environ.get("LANGUAGE_ENDPOINT")
    key = os.environ.get("LANGUAGE_KEY")
    client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    truncated = text[:5000]
    lowered = truncated.lower()
    return [kw for kw in SKILL_KEYWORDS if kw in lowered]

# ... [Keep your existing get_job, get_all_jobs, get_or_create_candidate, save_application functions here] ...

@app.route("/", methods=["GET", "POST"])
def upload():
    # ... [Keep your existing upload logic here] ...
    pass 

if __name__ == '__main__':
    app.run()