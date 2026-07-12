# Phase 5 (No-Code Alternative): Azure Logic Apps Workflow

If you want to show orchestration visually (good for demos/screenshots in a
report), build this instead of/alongside the code-only `orchestrator` function.

## Steps in Azure Portal

1. **Create a Logic App**: Portal → Create a resource → search "Logic App" → Consumption plan → same resource group.
2. **Trigger**: "When a blob is added or modified" (Azure Blob Storage connector) → point at the `resumes` container.
3. **Action 1**: "Azure Function" connector → call `parse_resume` (or skip if blob trigger already handles it directly).
4. **Action 2**: "Azure Function" connector → call `extract_skills`.
5. **Action 3**: "Azure Function" connector → call `orchestrator` (scoring + SQL insert + notification), passing:
   - `candidate_blob_name`: from trigger metadata
   - `job_id`: hardcoded or looked up via a "Condition" step matching resume filename patterns
6. **Action 4 (optional)**: "Condition" step — if `final_score >= 0.6`, send a Teams/Slack message to the recruiter channel via the respective connector, in addition to the candidate email already sent inside the Function.
7. **Save and enable** the Logic App. Test by uploading a sample resume PDF into the `resumes` Blob container.

## Why mention both approaches in your report
- **Logic Apps** = visual proof of "multi-step orchestration" for the brief's "Additional Points" and is good to screenshot for a report/demo.
- **Code-only orchestrator Function** = easier to version-control, unit test, and demo live during a technical interview.

You can implement either one first; they are functionally interchangeable for this project. If time is short, the code-only orchestrator alone satisfies the requirement.
