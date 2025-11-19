"""
Export services for generating PDF and DOCX reports
Handles document generation with tracking information including status codes
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import List, Dict, Any
from datetime import datetime
import os
from pathlib import Path
import logging

from app.utils.config import settings
from app.models.database import TrackingRecord

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for exporting tracking data to PDF and DOCX
    NOW WITH STATUS CODE COLUMN!
    """
    
    def __init__(self):
        self.export_dir = settings.EXPORT_DIR
        Path(self.export_dir).mkdir(parents=True, exist_ok=True)
    
    def generate_filename(self, format: str) -> str:
        """Generate unique filename for export"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tracking_report_{timestamp}.{format}"
        return os.path.join(self.export_dir, filename)
    
    def generate_pdf(self, tracking_records: List[TrackingRecord], include_details: bool = True) -> str:
        """
        Generate PDF report from tracking records with STATUS CODE column
        
        Args:
            tracking_records: List of TrackingRecord objects
            include_details: Include detailed information
            
        Returns:
            Path to generated PDF file
        """
        try:
            filename = self.generate_filename('pdf')
            doc = SimpleDocTemplate(filename, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=30,
                alignment=1  # Center
            )
            title = Paragraph("DHL Tracking Report", title_style)
            elements.append(title)
            
            # Generation info
            info_style = styles['Normal']
            info_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
            info_text += f"Total Records: {len(tracking_records)}"
            info = Paragraph(info_text, info_style)
            elements.append(info)
            elements.append(Spacer(1, 0.3*inch))
            
            # Table data - NOW WITH STATUS CODE!
            if include_details:
                # DETAILED TABLE: 6 columns including Status Code
                data = [['Tracking #', 'Status Code', 'Status', 'Origin', 'Destination', 'Last Checked']]
                for record in tracking_records:
                    data.append([
                        record.tracking_number,
                        record.status_code or 'N/A',  # STATUS CODE COLUMN
                        record.status or 'N/A',
                        record.origin or 'N/A',
                        record.destination or 'N/A',
                        record.last_checked.strftime('%Y-%m-%d %H:%M') if record.last_checked else 'N/A'
                    ])
            else:
                # SIMPLE TABLE: 4 columns including Status Code
                data = [['Tracking #', 'Status Code', 'Status', 'Last Checked']]
                for record in tracking_records:
                    data.append([
                        record.tracking_number,
                        record.status_code or 'N/A',  # STATUS CODE COLUMN
                        record.status or 'N/A',
                        record.last_checked.strftime('%Y-%m-%d %H:%M') if record.last_checked else 'N/A'
                    ])
            
            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            
            elements.append(table)
            
            # Build PDF
            doc.build(elements)
            logger.info(f"PDF generated with STATUS CODE column: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise
    
    def generate_docx(self, tracking_records: List[TrackingRecord], include_details: bool = True) -> str:
        """
        Generate DOCX report from tracking records with STATUS CODE column
        
        Args:
            tracking_records: List of TrackingRecord objects
            include_details: Include detailed information
            
        Returns:
            Path to generated DOCX file
        """
        try:
            filename = self.generate_filename('docx')
            doc = Document()
            
            # Title
            title = doc.add_heading('DHL Tracking Report', 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Generation info
            info_para = doc.add_paragraph()
            info_para.add_run(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n").bold = True
            info_para.add_run(f"Total Records: {len(tracking_records)}").bold = True
            doc.add_paragraph()  # Spacer
            
            # Create table - NOW WITH STATUS CODE!
            if include_details:
                # DETAILED TABLE: 6 columns
                table = doc.add_table(rows=1, cols=6)
                table.style = 'Light Grid Accent 1'
                
                # Header row
                header_cells = table.rows[0].cells
                headers = ['Tracking #', 'Status Code', 'Status', 'Origin', 'Destination', 'Last Checked']
                for idx, header in enumerate(headers):
                    cell = header_cells[idx]
                    cell.text = header
                    cell.paragraphs[0].runs[0].font.bold = True
                    cell.paragraphs[0].runs[0].font.size = Pt(11)
                
                # Data rows
                for record in tracking_records:
                    row_cells = table.add_row().cells
                    row_cells[0].text = record.tracking_number
                    row_cells[1].text = record.status_code or 'N/A'  # STATUS CODE COLUMN
                    row_cells[2].text = record.status or 'N/A'
                    row_cells[3].text = record.origin or 'N/A'
                    row_cells[4].text = record.destination or 'N/A'
                    row_cells[5].text = record.last_checked.strftime('%Y-%m-%d %H:%M') if record.last_checked else 'N/A'
            else:
                # SIMPLE TABLE: 4 columns
                table = doc.add_table(rows=1, cols=4)
                table.style = 'Light Grid Accent 1'
                
                # Header row
                header_cells = table.rows[0].cells
                headers = ['Tracking #', 'Status Code', 'Status', 'Last Checked']
                for idx, header in enumerate(headers):
                    cell = header_cells[idx]
                    cell.text = header
                    cell.paragraphs[0].runs[0].font.bold = True
                    cell.paragraphs[0].runs[0].font.size = Pt(11)
                
                # Data rows
                for record in tracking_records:
                    row_cells = table.add_row().cells
                    row_cells[0].text = record.tracking_number
                    row_cells[1].text = record.status_code or 'N/A'  # STATUS CODE COLUMN
                    row_cells[2].text = record.status or 'N/A'
                    row_cells[3].text = record.last_checked.strftime('%Y-%m-%d %H:%M') if record.last_checked else 'N/A'
            
            # Save document
            doc.save(filename)
            logger.info(f"DOCX generated with STATUS CODE column: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error generating DOCX: {str(e)}")
            raise
    
    def cleanup_old_exports(self, days: int = 7):
        """
        Clean up export files older than specified days
        
        Args:
            days: Number of days to keep files
        """
        try:
            cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for file in os.listdir(self.export_dir):
                file_path = os.path.join(self.export_dir, file)
                if os.path.isfile(file_path):
                    if os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
                        logger.info(f"Cleaned up old export: {file}")
        except Exception as e:
            logger.error(f"Error cleaning up exports: {str(e)}")


# Create export service instance
export_service = ExportService()

