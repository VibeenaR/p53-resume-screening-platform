"""
PHASE 1: Resume Parsing via Azure AI Document Intelligence

Trigger: Blob Storage (new resume uploaded to 'resumes' container)
Output: Raw text + tables saved as JSON to 'parsed' container

Azure setup needed before this runs:
  - Document Intelligence resource created (see README Phase 0.3, step 3)
  - Blob container 'resumes' (input) and 'parsed' (output) created
  - App Settings on the Function App must include:
      DOC_INTELLIGENCE_ENDPOINT, DOC_INTELLIGENCE_KEY, STORAGE_CONNECTION_STRING
    (Portal -> Function App -> Configuration -> Application Settings)
"""
import logging
import json
import os
import azure.functions as func
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient


def parse_resume_bytes(file_bytes: bytes) -> dict:
    """Send resume bytes to Document Intelligence prebuilt-layout model
    and return structured text + tables."""
    endpoint = os.environ["DOC_INTELLIGENCE_ENDPOINT"]
    key = os.environ["DOC_INTELLIGENCE_KEY"]

    client = DocumentAnalysisClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # prebuilt-layout extracts text, tables, and structure without training
    poller = client.begin_analyze_document("prebuilt-layout", document=file_bytes)
    result = poller.result()

    full_text = "\n".join([line.content for page in result.pages for line in page.lines])

    tables = []
    for table in result.tables:
        rows = {}
        for cell in table.cells:
            rows.setdefault(cell.row_index, {})[cell.column_index] = cell.content
        tables.append(rows)

    return {"full_text": full_text, "tables": tables}


def main(myblob: func.InputStream):
    """Blob-trigger entry point. Fires automatically when a new file
    lands in the 'resumes' container."""
    logging.info(f"Parsing resume: {myblob.name}, size: {myblob.length} bytes")

    file_bytes = myblob.read()
    parsed = parse_resume_bytes(file_bytes)

    # Save parsed JSON back to blob storage for the next stage (skill extraction)
    storage_conn = os.environ["STORAGE_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(storage_conn)

    output_name = myblob.name.split("/")[-1].rsplit(".", 1)[0] + ".json"
    output_client = blob_service.get_blob_client(container="parsed", blob=output_name)
    output_client.upload_blob(json.dumps(parsed), overwrite=True)

    logging.info(f"Saved parsed output to parsed/{output_name}")
