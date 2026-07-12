"""
PHASE 2: Skill & Entity Extraction via Azure AI Language

Trigger: Blob Storage (new parsed JSON in 'parsed' container from Phase 1)
Output: Extracted skills/entities saved to 'extracted' container

Azure setup needed:
  - Language resource created (README Phase 0.3, step 4)
  - Blob container 'extracted' created
  - App Settings: LANGUAGE_ENDPOINT, LANGUAGE_KEY, STORAGE_CONNECTION_STRING
"""
import logging
import json
import os
import azure.functions as func
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient

# A simple seed skill vocabulary to boost recall alongside NER.
# Extend this list with domain-specific tech/skill keywords.
SKILL_KEYWORDS = [
    "python", "java", "c++", "react", "node.js", "aws", "azure", "docker",
    "kubernetes", "sql", "tensorflow", "pytorch", "nlp", "machine learning",
    "fastapi", "flask", "git", "ci/cd", "rest api", "mongodb", "postgresql",
]


def get_client() -> TextAnalyticsClient:
    endpoint = os.environ["LANGUAGE_ENDPOINT"]
    key = os.environ["LANGUAGE_KEY"]
    return TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))


def extract_entities_and_keyphrases(client: TextAnalyticsClient, text: str) -> dict:
    # Language API caps input around 5,120 characters per document — truncate if needed
    text = text[:5000]

    entities_result = client.recognize_entities(documents=[text])[0]
    keyphrase_result = client.extract_key_phrases(documents=[text])[0]

    entities = [
        {"text": e.text, "category": e.category, "confidence": e.confidence_score}
        for e in entities_result.entities
    ]
    key_phrases = keyphrase_result.key_phrases

    # Cross-check seed vocabulary against raw text (catches skills NER misses)
    lowered = text.lower()
    matched_skills = [kw for kw in SKILL_KEYWORDS if kw in lowered]

    return {
        "entities": entities,
        "key_phrases": key_phrases,
        "matched_skills": matched_skills,
    }


def main(myblob: func.InputStream):
    logging.info(f"Extracting skills from: {myblob.name}")

    parsed_data = json.loads(myblob.read().decode("utf-8"))
    text = parsed_data.get("full_text", "")

    client = get_client()
    extracted = extract_entities_and_keyphrases(client, text)

    storage_conn = os.environ["STORAGE_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(storage_conn)

    output_name = myblob.name.split("/")[-1]
    output_client = blob_service.get_blob_client(container="extracted", blob=output_name)
    output_client.upload_blob(json.dumps(extracted), overwrite=True)

    logging.info(f"Saved extracted skills to extracted/{output_name}")
