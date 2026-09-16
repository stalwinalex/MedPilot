import os
import uuid
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


class PDFService:
    STORAGE_DIR = "generated_pdfs"

    @classmethod
    def ensure_storage_dir(cls):
        os.makedirs(cls.STORAGE_DIR, exist_ok=True)

    @classmethod
    def generate_study_resource_pdf(
        cls,
        title: str,
        subject_name: str,
        resource_type: str,
        content: Dict[str, Any],
        citations: List[str]
    ) -> str:
        cls.ensure_storage_dir()
        filename = f"{cls.STORAGE_DIR}/{uuid.uuid4().hex}_{resource_type}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'MedPilotTitle',
            parent=styles['Heading1'],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#0F766E'),
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'MedPilotSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#475569'),
            spaceAfter=15
        )
        heading_style = ParagraphStyle(
            'MedPilotHeading',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#1E293B'),
            spaceBefore=10,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'MedPilotBody',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#334155'),
            spaceAfter=6
        )
        disclaimer_style = ParagraphStyle(
            'MedPilotDisclaimer',
            parent=styles['Normal'],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#64748B'),
            spaceBefore=20
        )

        # Header
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"<b>MedPilot Academic Resource</b> | Subject: {subject_name} | Type: {resource_type.replace('_', ' ').title()}", subtitle_style))
        story.append(Spacer(1, 10))

        # Content based on resource type
        if resource_type in ["summary", "study_notes", "revision_sheet"]:
            summary_text = content.get("summary") or content.get("notes") or str(content)
            for paragraph in str(summary_text).split("\n\n"):
                if paragraph.strip():
                    story.append(Paragraph(paragraph.replace("\n", "<br/>"), body_style))
                    story.append(Spacer(1, 4))

            key_points = content.get("key_points", [])
            if key_points:
                story.append(Spacer(1, 10))
                story.append(Paragraph("<b>Key High-Yield Concepts:</b>", heading_style))
                for pt in key_points:
                    story.append(Paragraph(f"&bull; {pt}", body_style))

        elif resource_type == "flashcards":
            cards = content.get("cards", [])
            story.append(Paragraph("<b>Revision Flashcards:</b>", heading_style))
            table_data = [["Front (Question / Prompt)", "Back (Answer / Clinical Key)"]]
            for c in cards:
                q = Paragraph(c.get("front", ""), body_style)
                a = Paragraph(c.get("back", ""), body_style)
                table_data.append([q, a])
            
            t = Table(table_data, colWidths=[260, 260])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CCFBF1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F766E')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t)

        elif resource_type == "mcq_bank":
            questions = content.get("questions", [])
            story.append(Paragraph("<b>High-Yield Academic MCQs:</b>", heading_style))
            for idx, q in enumerate(questions, 1):
                story.append(Paragraph(f"<b>Q{idx}: {q.get('question', '')}</b>", heading_style))
                options = q.get("options", [])
                for opt_idx, opt in enumerate(options):
                    letter_opt = chr(65 + opt_idx)
                    story.append(Paragraph(f"{letter_opt}. {opt}", body_style))
                story.append(Paragraph(f"<i>Correct Answer: {q.get('correct_answer', '')}</i>", body_style))
                if q.get("explanation"):
                    story.append(Paragraph(f"<b>Explanation:</b> {q.get('explanation', '')}", body_style))
                story.append(Spacer(1, 8))

        # Citations
        if citations:
            story.append(Spacer(1, 15))
            story.append(Paragraph("<b>Academic References & Sources:</b>", heading_style))
            for cite in citations:
                story.append(Paragraph(f"&bull; {cite}", body_style))

        # Mandatory Educational Disclaimer
        story.append(Spacer(1, 20))
        story.append(Paragraph(
            "<b>Disclaimer:</b> MedPilot is strictly an academic educational study tool for MBBS students. "
            "It does NOT provide medical advice, diagnosis, treatment guidelines, or clinical prescriptions. "
            "Always refer to standard approved medical textbooks and clinical mentors.",
            disclaimer_style
        ))

        doc.build(story)
        return filename
