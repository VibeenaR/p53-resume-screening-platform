# P53 — AI-Powered Resume Screening & Recruitment Platform

End-to-end pipeline: Resume (PDF/DOCX) → Parse → Extract Skills → Score/Rank → Store → Notify.

---

## PHASE 0 — Azure Account & Resource Setup (do this first)

### 0.1 Create Azure Account
1. Go to https://azure.microsoft.com/free/students (use student tier — free with your VIT email, no card needed) or the normal free tier ($200 credit, 12 months).
2. Sign in to https://portal.azure.com once approved.

### 0.2 Create a Resource Group
Everything you build should live inside one Resource Group so you can delete it all at once later.

```bash
# Using Azure CLI (install: https://learn.microsoft.com/cli/azure/install-azure-cli)
az login
az group create --name rg-resume-screening --location centralindia
```

### 0.3 Create each Azure resource (CLI commands — run after az login)

```bash
# 1. Storage account (for resumes + function app storage)
az storage account create \
  --name resumescreeningstorage \
  --resource-group rg-resume-screening \
  --location centralindia \
  --sku Standard_LRS

# 2. Blob container for raw resumes
az storage container create \
  --name resumes \
  --account-name resumescreeningstorage

# 3. Document Intelligence (Form Recognizer) resource
az cognitiveservices account create \
  --name resume-doc-intelligence \
  --resource-group rg-resume-screening \
  --kind FormRecognizer \
  --sku F0 \
  --location centralindia \
  --yes

# 4. Language service resource
az cognitiveservices account create \
  --name resume-language-service \
  --resource-group rg-resume-screening \
  --kind TextAnalytics \
  --sku F0 \
  --location centralindia \
  --yes

# 5. Azure SQL Server + Database
az sql server create \
  --name resume-sql-server \
  --resource-group rg-resume-screening \
  --location centralindia \
  --admin-user sqladmin \
  --admin-password "ChooseAStrongPassword123!"

az sql db create \
  --resource-group rg-resume-screening \
  --server resume-sql-server \
  --name ResumeScreeningDB \
  --service-objective Basic

# Allow your IP + Azure services to access SQL
az sql server firewall-rule create \
  --resource-group rg-resume-screening \
  --server resume-sql-server \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# 6. Function App (Python, Consumption plan = free-ish)
az storage account create --name resumefuncstorage --resource-group rg-resume-screening --sku Standard_LRS
az functionapp create \
  --resource-group rg-resume-screening \
  --consumption-plan-location centralindia \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --name resume-screening-func \
  --storage-account resumefuncstorage \
  --os-type linux

# 7. Communication Services (for email/SMS notifications)
az communication create \
  --name resume-comm-service \
  --location global \
  --data-location India \
  --resource-group rg-resume-screening
```

> Everything above can *also* be done by clicking "Create a resource" in the Azure Portal search bar and typing each service name — CLI is just faster and reproducible.

### 0.4 Collect your keys
After creating each resource, go to its page in the portal → **Keys and Endpoint** (for Cognitive Services) and copy:
- `DOC_INTELLIGENCE_ENDPOINT`, `DOC_INTELLIGENCE_KEY`
- `LANGUAGE_ENDPOINT`, `LANGUAGE_KEY`
- `SQL_CONNECTION_STRING` (Portal → SQL DB → Connection Strings → ODBC)
- `STORAGE_CONNECTION_STRING` (Storage account → Access keys)
- `COMMUNICATION_CONNECTION_STRING` (Communication Services → Keys)

Put them all in a `.env` file (see `.env.example` in this repo) — **never commit this file**.

---

## PHASE 1 — Resume Parsing (Document Intelligence)
See `azure_functions/parse_resume/`. Uses the prebuilt "layout" model to extract raw text + tables from PDF/DOCX resumes uploaded to Blob Storage.

## PHASE 2 — Skill/Entity Extraction (Language Service)
See `azure_functions/extract_skills/`. Runs NER + key-phrase extraction on the parsed text to isolate skills, tools, years of experience.

## PHASE 3 — Scoring & Ranking (ML)
See `ml/`. Builds embeddings for resume text and job description, computes similarity, trains a simple ranking model (Gradient Boosting) on top of similarity + rule-based features.

## PHASE 4 — Database
See `sql/schema.sql`. Run this against your Azure SQL DB to create the tables.

## PHASE 5 — Orchestration
`docs/logic_app_workflow.md` describes how to wire Blob upload → Function → Function → Function → Notification using Logic Apps (no-code) or pure Function chaining (code-only, simpler to demo).

## PHASE 6 — Notifications
See `notifications/send_notification.py`. Uses Azure Communication Services to email candidates.

## PHASE 7 — Bias Check
See `ml/bias_check.py`. Uses Fairlearn to check score disparity across name-inferred gender groups.

## Build order (do this in sequence)
1. Run Phase 0 (provision resources)
2. Test Phase 1 alone: upload one sample PDF resume, confirm text extraction works
3. Test Phase 2 alone: feed Phase 1's output text, confirm skills are extracted
4. Run Phase 4 SQL script to create your tables
5. Test Phase 3 with 5-10 dummy resumes + one job description, confirm ranking output makes sense
6. Wire Phases 1→2→3→4 together inside the Azure Function (`orchestrator` folder)
7. Add Phase 6 notifications last, once the pipeline works end-to-end
8. Build the React dashboard last, pointed at your SQL data via a simple API layer
