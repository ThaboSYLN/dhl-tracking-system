# Add this to your app/utils/email_sender.py (or create it if it doesn't exist)
# If it exists, integrate the function there.

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from typing import List

load_dotenv()  # Load from .env file

def send_bin_closure_email(team_leader_emails: List[str] , confirmed_waybills: List[str], company_domain: str = "asithandileludonga6@gmail.com"):
    """
    Sends an email to team leaders with confirmed waybills that need bin closure.
    
    :param team_leader_emails: List of team leader email addresses (e.g., ['leader1@yourcompany.com']).
    :param confirmed_waybills: List of waybills confirmed as with DHL.
    :param company_domain: Your company email domain (for production; use personal for testing).
    """
    if not confirmed_waybills:
        print("No confirmed waybills to report. Skipping email.")
        return

    # SMTP settings from .env (add these to your .env file)
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')  # Change to your company SMTP if available
    smtp_port = int(os.getenv('SMTP_PORT', 587))  # 587 for TLS, 465 for SSL
    from_email = os.getenv('FROM_EMAIL', f'noreply@{company_domain}')
    email_password = os.getenv('EMAIL_PASSWORD')

    # For testing with personal email (e.g., Gmail)
    # Comment out and use company SMTP details in production
    # from_email = 'yourpersonal@gmail.com'
    # Use app password for Gmail: https://support.google.com/accounts/answer/185833

    # Email content
    subject = "Action Required: Close Bins for Confirmed DHL Waybills"
    body_text = (
        "Dear Team Leaders,\n\n"
        "The following waybills have been verified as scanned and now in transit with DHL "
        "(no longer in our building). Please validate and close the associated bins promptly:\n\n"
        + "\n".join(confirmed_waybills) + "\n\n"
        "If any issues arise or if a waybill appears incorrectly listed, please contact support immediately.\n\n"
        "Best regards,\n"
        "DHL Tracking System Team\n"
        "Automated Notification - Do not reply"
    )

    # Create message
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = ', '.join(team_leader_emails)
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain'))

    try:
        # Connect and send (using STARTTLS for port 587)
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(from_email, email_password)
        server.sendmail(from_email, team_leader_emails, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {team_leader_emails} for waybills: {confirmed_waybills}")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")  # Log error; in production, use logging module

# Example usage (do not run directly; integrate below)
# send_bin_closure_email(['testpersonal@gmail.com'], ['WAYBILL123', 'WAYBILL456'], company_domain='gmail.com')