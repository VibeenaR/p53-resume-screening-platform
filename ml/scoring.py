"""
PHASE 3a: Candidate-Job Matching via Sentence Embeddings

Computes semantic similarity between a candidate's extracted resume text
and a job description, plus rule-based features (skill overlap %,
years of experience match). This is designed to run either:
  - Locally/inside an Azure Function (lightweight model, CPU-only)
  - As an Azure ML managed endpoint (for heavier models, batch scoring)

Model: 'all-MiniLM-L6-v2' — small (80MB), fast on CPU, good enough for
resume/JD similarity. Swap for a domain fine-tuned model later if you
want to reuse your TriSense BERT experience.
"""
from sentence_transformers import SentenceTransformer, util
import re

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def semantic_similarity(resume_text: str, job_description: str) -> float:
    model = get_model()
    embeddings = model.encode([resume_text, job_description], convert_to_tensor=True)
    score = util.cos_sim(embeddings[0], embeddings[1]).item()
    return round(score, 4)


def skill_overlap_score(candidate_skills: list[str], required_skills: list[str]) -> float:
    if not required_skills:
        return 0.0
    candidate_set = {s.lower() for s in candidate_skills}
    required_set = {s.lower() for s in required_skills}
    overlap = candidate_set & required_set
    return round(len(overlap) / len(required_set), 4)


def extract_years_experience(text: str) -> float:
    """Rough heuristic: find patterns like '3 years', '2+ years of experience'."""
    matches = re.findall(r"(\d+)\+?\s*years?", text.lower())
    return max([int(m) for m in matches], default=0)


def compute_features(resume_text: str, candidate_skills: list[str],
                      job_description: str, required_skills: list[str],
                      min_years_required: int = 0) -> dict:
    """Combine all signals into one feature dict — this is what
    feeds the ranking model in rank_model.py"""
    sim = semantic_similarity(resume_text, job_description)
    skill_score = skill_overlap_score(candidate_skills, required_skills)
    years = extract_years_experience(resume_text)
    experience_match = 1.0 if years >= min_years_required else years / max(min_years_required, 1)

    return {
        "semantic_similarity": sim,
        "skill_overlap": skill_score,
        "years_experience": years,
        "experience_match": round(experience_match, 4),
    }
