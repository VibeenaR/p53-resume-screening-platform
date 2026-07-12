"""
PHASE 6: Automated Candidate Notifications via Azure Communication Services

Azure setup needed:
  - Communication Services resource created (README Phase 0.3, step 7)
  - A verified email domain attached to it (Portal -> Communication Services
    -> Email -> Provision domains -> use the free Azure-managed domain for
    testing, or connect your own domain for production)
"""
import os
from azure.communication.email import EmailClient


def send_status_email(recipient_email: str, candidate_name: str, status: str, job_title: str):
    """
    status: one of 'Received', 'Shortlisted', 'Rejected', 'Interviewed'
    """
    connection_string = os.environ["COMMUNICATION_CONNECTION_STRING"]
    sender = os.environ["SENDER_EMAIL"]
    client = EmailClient.from_connection_string(connection_string)

    subject_map = {
        "Received": f"Application received: {job_title}",
        "Shortlisted": f"You've been shortlisted for {job_title}!",
        "Rejected": f"Update on your application for {job_title}",
        "Interviewed": f"Next steps after your interview for {job_title}",
    }
    body_map = {
        "Received": f"Hi {candidate_name}, we've received your application for {job_title}. Our team will review it shortly.",
        "Shortlisted": f"Hi {candidate_name}, congratulations! You've been shortlisted for {job_title}. We'll reach out soon to schedule next steps.",
        "Rejected": f"Hi {candidate_name}, thank you for applying to {job_title}. We've decided to move forward with other candidates this time.",
        "Interviewed": f"Hi {candidate_name}, thank you for interviewing for {job_title}. We'll be in touch with next steps soon.",
    }

    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": recipient_email}]},
        "content": {
            "subject": subject_map[status],
            "plainText": body_map[status],
        },
    }

    poller = client.begin_send(message)
    result = poller.result()
    return result


if __name__ == "__main__":
    # quick manual test
    send_status_email(
        recipient_email="candidate@example.com",
        candidate_name="Test Candidate",
        status="Shortlisted",
        job_title="Data Scientist Intern",
    )
