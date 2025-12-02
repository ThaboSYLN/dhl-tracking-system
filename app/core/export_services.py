"""
Export services for generating PDF and DOCX reports
Handles document generation with tracking information

CHANGES MADE:
1. generate_pdf: Added binID column to PDF table (Lines 67-87, 91-102)
2. generate_docx: Added binID column to DOCX table (Lines 155-185, 189-210)
3. Both detailed and simple views now include binID
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
    """Service for exporting tracking data to PDF and DOCX"""
    
    def __init__(self):
        self.export_dir = settings.EXPORT_DIR
        Path(self.export_dir).mkdir(parents=True, exist_ok=True)
    
    def _get_last_event_date(self, record: TrackingRecord) -> str:
        """Extract the most recent event timestamp from tracking details"""
        try:
            if record.tracking_details and isinstance(record.tracking_details, dict):
                events = record.tracking_details.get('events', [])
                
                if events and len(events) > 0:
                    most_recent_event = events[0]
                    timestamp = most_recent_event.get('timestamp')
                    
                    if timestamp:
                        return timestamp
            
            if record.last_checked:
                return record.last_checked.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            
            return 'N/A'
            
        except Exception as e:
            logger.error(f"Error extracting last event date: {str(e)}")
            return 'N/A'
    
    def generate_filename(self, format: str) -> str:
        """Generate unique filename for export"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tracking_report_{timestamp}.{format}"
        return os.path.join(self.export_dir, filename)
    
    def generate_pdf(self, tracking_records: List[TrackingRecord], include_details: bool = True) -> str:
        """
        Generate PDF report
        
        UPDATED: Now includes binID column in table
        
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
                alignment=1
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
            
            # Table data with binID column
            if include_details:
                data = [[
                    'Tracking #',
                    'Bin ID',  # NEW COLUMN
                    'Status Code', 
                    'Origin', 
                    'Destination', 
                    'Last Event Date'
                ]]
                
                for record in tracking_records:
                    last_event_date = self._get_last_event_date(record)
                    data.append([
                        record.tracking_number,
                        record.bin_id or 'N/A',  # NEW: binID column
                        record.status_code or 'N/A',
                        record.origin or 'N/A',
                        record.destination or 'N/A',
                        last_event_date
                    ])
            else:
                data = [[
                    'Tracking #',
                    'Bin ID',  # NEW COLUMN
                    'Status Code', 
                    'Last Event Date'
                ]]
                
                for record in tracking_records:
                    last_event_date = self._get_last_event_date(record)
                    data.append([
                        record.tracking_number,
                        record.bin_id or 'N/A',  # NEW: binID column
                        record.status_code or 'N/A',
                        last_event_date
                    ])
            
            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            
            elements.append(table)
            
            # Build PDF
            doc.build(elements)
            logger.info(f"PDF generated: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise
    
    def generate_docx(self, tracking_records: List[TrackingRecord], include_details: bool = True) -> str:
        """
        Generate DOCX report
        
        UPDATED: Now includes binID column in table
        
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
            doc.add_paragraph()
            
            # Create table with binID column
            if include_details:
                table = doc.add_table(rows=1, cols=6)  # UPDATED: 6 columns now
                table.style = 'Light Grid Accent 1'
                
                # Header row
                header_cells = table.rows[0].cells
                headers = [
                    'Tracking #',
                    'Bin ID',  # NEW COLUMN
                    'Status Code', 
                    'Origin', 
                    'Destination', 
                    'Last Event Date'
                ]
                
                for idx, header in enumerate(headers):
                    cell = header_cells[idx]
                    cell.text = header
                    cell.paragraphs[0].runs[0].font.bold = True
                    cell.paragraphs[0].runs[0].font.size = Pt(10)
                
                # Data rows
                for record in tracking_records:
                    last_event_date = self._get_last_event_date(record)
                    row_cells = table.add_row().cells
                    row_cells[0].text = record.tracking_number
                    row_cells[1].text = record.bin_id or 'N/A'  # NEW: binID column
                    row_cells[2].text = record.status_code or 'N/A'
                    row_cells[3].text = record.origin or 'N/A'
                    row_cells[4].text = record.destination or 'N/A'
                    row_cells[5].text = last_event_date
            else:
                table = doc.add_table(rows=1, cols=4)  # UPDATED: 4 columns now
                table.style = 'Light Grid Accent 1'
                
                # Header row
                header_cells = table.rows[0].cells
                headers = [
                    'Tracking #',
                    'Bin ID',  # NEW COLUMN
                    'Status Code', 
                    'Last Event Date'
                ]
                
                for idx, header in enumerate(headers):
                    cell = header_cells[idx]
                    cell.text = header
                    cell.paragraphs[0].runs[0].font.bold = True
                    cell.paragraphs[0].runs[0].font.size = Pt(10)
                
                # Data rows
                for record in tracking_records:
                    last_event_date = self._get_last_event_date(record)
                    row_cells = table.add_row().cells
                    row_cells[0].text = record.tracking_number
                    row_cells[1].text = record.bin_id or 'N/A'  # NEW: binID column
                    row_cells[2].text = record.status_code or 'N/A'
                    row_cells[3].text = last_event_date
            
            # Save document
            doc.save(filename)
            logger.info(f"DOCX generated: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error generating DOCX: {str(e)}")
            raise
    
    def cleanup_old_exports(self, days: int = 7):
        """Clean up export files older than specified days"""
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

