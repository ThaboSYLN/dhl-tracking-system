import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import logging

from app.utils.config import settings

logger = logging.getLogger(__name__)


def send_bin_closure_email(confirmed_waybills: List[str]):
    """
    Send bin closure email — SYNC version (works with correct name
    Works for single or multiple waybills
    """
    if not confirmed_waybills:
        logger.info("No waybills to report — skipping email")
        return

    team_emails = settings.TEAM_LEADER_EMAILS
    if not team_emails:
        logger.warning("TEAM_LEADER_EMAILS not set — cannot send email")
        return

    subject = "Action Required: Close Bins for Confirmed DHL Waybills"

    waybills_list = "\n".join(f"→  {wb}" for wb in confirmed_waybills)

    body = f"""
Dear Team Leaders,

The following waybill(s) have been scanned by DHL and are now in transit.
They are NO LONGER in our building.

Please close the associated bin(s) immediately:

{waybills_list}

If anything looks wrong, contact support ASAP.

Thank you!

Best regards,
DHL Tracking System
Pre-Prod Team
    """.strip()

    msg = MIMEMultipart()
    msg['From'] = settings.FROM_EMAIL
    msg['To'] = ', '.join(team_emails)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.FROM_EMAIL, settings.EMAIL_PASSWORD)
        server.sendmail(settings.FROM_EMAIL, team_emails, msg.as_string())
        server.quit()
        logger.info(f"BIN CLOSURE EMAIL SENT → {confirmed_waybills}")
    except Exception as e:
        logger.error(f"Failed to send bin closure email: {e}")


# THIS IS THE ONE YOUR dhl_services.py CALLS — SINGLE WAYBILL → LIST
"""def trigger_bin_closure_email(tracking_number: str):
    Simple wrapper so old code keeps working
    send_bin_closure_email([tracking_number])"""