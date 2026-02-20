# app/utils/email_service.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import logging

from app.utils.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.enabled = all([
                settings.SMTP_SERVER,
                settings.EMAIL_FROM,
                settings.EMAIL_TO
            ])
            cls._instance.recipients = [e.strip() for e in settings.EMAIL_TO.split(",")] if settings.EMAIL_TO else []
        return cls._instance

    def send_report(self, pdf_path: str, source_file: str = None):
        if not self.enabled or not self.recipients:
            logger.info("Email service disabled or no recipients → skipping")
            return

        if not Path(pdf_path).exists():
            logger.error(f"PDF not found: {pdf_path}")
            return

        subject = f"DHL Tracking Report - {Path(pdf_path).stem}"
        body = "Hi team,\n\nA new tracking file has been processed.\n"
        if source_file:
            body += f"Source file: {source_file}\n"
        body += "\nKindly assist to close the undispatched BINs for Stanbic DHL so that their status can be updated to Shipped. \n\nThese BINs were unfortunately missed during the dispatch process and are currently preventing the status change which is affecting API push to CMS system for Stanbic to receive the cards on the system. \n\nPlease let us know once this has been completed, or if any additional information is required from our side. \n\nThank you for your support.\n\nPre-Production"

        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with open(pdf_path, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header("Content-Disposition", "attachment", filename=Path(pdf_path).name)
            msg.attach(attach)

        try:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.sendmail(settings.EMAIL_FROM, self.recipients, msg.as_string())
            logger.info(f"Auto-email sent → {', '.join(self.recipients)}")
        except Exception as e:
            logger.error(f"Email failed: {e}")

    def send_empty_report_alert(self, source_file: str = None):
        """
        Send an alert email when all records were filtered out of a report.
        This fires when every record in the processed file had a status
        that is excluded from reports (e.g. pre-transit).
        The alert always goes to thabospenser@gmail.com.
        """
        alert_recipient = "thabo.mthethwa@external.idemia.com"

        subject = "⚠️ DHL Report Alert — No Records Included in Report"

        body = "Hi,\n\n"
        body += "A tracking file was processed but the generated report contains NO records.\n\n"
        body += "This means every entry in the file had a status that is excluded from reports\n"
        body += "(e.g. pre-transit or any other status on the exclusion list).\n\n"

        if source_file:
            body += f"Source file: {source_file}\n\n"

        body += "Please review the file and check whether the statuses are expected.\n\n"
        body += "If this keeps happening, consider updating the exclusion list in:\n"
        body += "  app/core/export_services.py → PRE_TRANSIT_STATUSES\n\n"
        body += "Pre-Production Team"

        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = alert_recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.sendmail(settings.EMAIL_FROM, [alert_recipient], msg.as_string())
            logger.info(f"Empty-report alert sent → {alert_recipient}")
        except Exception as e:
            logger.error(f"Failed to send empty-report alert: {e}")

