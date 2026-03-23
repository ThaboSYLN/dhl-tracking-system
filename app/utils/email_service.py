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

        # Path to your constant PDF
        constant_pdf = Path("data/trainingPDF/training.pdf")

        if not constant_pdf.exists():
            logger.error(f"Constant PDF not found: {constant_pdf}")
            # continue anyway, since it's optional

        # ✅ These must ALWAYS run — OUTSIDE the IF block
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

        # Attach dynamic PDF
        with open(pdf_path, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header("Content-Disposition", "attachment", filename=Path(pdf_path).name)
            msg.attach(attach)

        # Attach constant PDF (optional)
        if constant_pdf.exists():
            with open(constant_pdf, "rb") as f:
                const_attach = MIMEApplication(f.read(), _subtype="pdf")
                const_attach.add_header("Content-Disposition", "attachment", filename=constant_pdf.name)
                msg.attach(const_attach)

        try:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.sendmail(settings.EMAIL_FROM, self.recipients, msg.as_string())
            logger.info(f"Auto-email sent → {', '.join(self.recipients)}")
        except Exception as e:
            logger.error(f"Email failed: {e}")