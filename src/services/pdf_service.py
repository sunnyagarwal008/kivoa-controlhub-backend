import os
import tempfile
import uuid
from io import BytesIO
from collections import defaultdict
from datetime import datetime

import requests
from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas

from src.services.s3_service import s3_service


class PDFService:
    """Service class for PDF generation operations"""

    def __init__(self):
        pass

    def generate_product_catalog(self, products_by_category):
        """
        Generate a PDF catalog of products grouped by category
        
        Args:
            products_by_category: Dictionary with category names as keys and list of products as values
            
        Returns:
            str: Path to the generated PDF file
        """
        # Create a temporary file for the PDF
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = temp_file.name
        temp_file.close()

        # Create the PDF document
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        # Container for the 'Flowable' objects
        elements = []

        # Add cover page
        elements.extend(self._create_cover_page())
        elements.append(PageBreak())

        # Add products by category
        for category_name, products in products_by_category.items():
            if products:
                elements.extend(self._create_category_section(category_name, products))
                elements.append(PageBreak())

        # Build the PDF
        doc.build(elements)

        return pdf_path

    def _create_cover_page(self):
        """Create the cover page with dark green background and KIVOA branding"""
        elements = []
        
        # Create a custom canvas for the cover page with dark green background
        # We'll use a table to create the colored background effect
        
        # Get page dimensions
        page_width = letter[0]
        page_height = letter[1]
        
        # Create styles
        styles = getSampleStyleSheet()
        
        # Logo style - large, centered, white text
        logo_style = ParagraphStyle(
            'LogoStyle',
            parent=styles['Heading1'],
            fontSize=72,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=30,
            fontName='Helvetica-Bold'
        )
        
        # Subtitle style - centered, white text
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.white,
            alignment=TA_CENTER,
            leading=24,
            fontName='Helvetica'
        )
        
        # Add spacer to center content vertically
        elements.append(Spacer(1, 2.5*inch))
        
        # Create a table for the background color
        # We'll create the text elements separately
        logo_text = Paragraph("KIVOA", logo_style)
        subtitle_text = Paragraph(
            "We create modern elegance through exquisite designs,<br/>ensuring every piece reflects your individuality.",
            subtitle_style
        )
        
        # Create a colored table to simulate background
        cover_data = [
            [logo_text],
            [Spacer(1, 0.3*inch)],
            [subtitle_text]
        ]
        
        cover_table = Table(cover_data, colWidths=[page_width - inch])
        cover_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1B4D3E')),  # Dark green
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 50),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 50),
        ]))
        
        elements.append(cover_table)
        
        return elements

    def _create_category_section(self, category_name, products):
        """Create a section for a category with products in 2-column grid"""
        elements = []
        
        # Create styles
        styles = getSampleStyleSheet()
        
        # Category header style
        category_style = ParagraphStyle(
            'CategoryHeader',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1B4D3E'),  # Dark green
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )
        
        # Add category header
        elements.append(Paragraph(category_name, category_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Create product grid (2 columns)
        products_data = []
        row = []
        
        for idx, product in enumerate(products):
            product_cell = self._create_product_cell(product)
            row.append(product_cell)
            
            # Add row when we have 2 products or it's the last product
            if len(row) == 2 or idx == len(products) - 1:
                # Pad the last row if it has only 1 product
                if len(row) == 1:
                    row.append('')
                products_data.append(row)
                row = []
        
        # Create table with 2 columns
        if products_data:
            col_width = (letter[0] - inch) / 2 - 0.2*inch
            products_table = Table(products_data, colWidths=[col_width, col_width])
            products_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ]))
            
            elements.append(products_table)
        
        return elements

    def _create_product_cell(self, product):
        """Create a cell for a single product with image and SKU"""
        cell_elements = []
        
        # Get the first image URL
        image_url = None
        if product.product_images and len(product.product_images) > 0:
            # Get the first image
            image_url = product.product_images[0].image_url
        
        # Download and add image if available
        if image_url:
            try:
                img = self._download_and_create_image(image_url, max_width=2.5*inch, max_height=2.5*inch)
                if img:
                    cell_elements.append(img)
                    cell_elements.append(Spacer(1, 0.1*inch))
            except Exception as e:
                current_app.logger.error(f"Error loading image for product {product.sku}: {str(e)}")
        
        # Add SKU as title
        styles = getSampleStyleSheet()
        sku_style = ParagraphStyle(
            'SKUStyle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        sku_text = Paragraph(product.sku, sku_style)
        cell_elements.append(sku_text)
        
        # Create a nested table for the cell content
        cell_table = Table([[elem] for elem in cell_elements], colWidths=[2.8*inch])
        cell_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        return cell_table

    def _download_and_create_image(self, image_url, max_width=2.5*inch, max_height=2.5*inch):
        """Download an image from URL and create a ReportLab Image object"""
        try:
            # Download the image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Create Image object from bytes
            img_data = BytesIO(response.content)
            img = Image(img_data)
            
            # Calculate aspect ratio and resize
            aspect = img.imageWidth / img.imageHeight
            
            if aspect > 1:  # Wider than tall
                img.drawWidth = min(max_width, img.imageWidth)
                img.drawHeight = img.drawWidth / aspect
            else:  # Taller than wide
                img.drawHeight = min(max_height, img.imageHeight)
                img.drawWidth = img.drawHeight * aspect
            
            # Ensure it doesn't exceed max dimensions
            if img.drawWidth > max_width:
                img.drawWidth = max_width
                img.drawHeight = img.drawWidth / aspect
            if img.drawHeight > max_height:
                img.drawHeight = max_height
                img.drawWidth = img.drawHeight * aspect
            
            return img
        except Exception as e:
            current_app.logger.error(f"Error downloading image from {image_url}: {str(e)}")
            return None

    def upload_pdf_to_s3(self, pdf_path, filename=None):
        """
        Upload a PDF file to S3 and return the public URL
        
        Args:
            pdf_path: Local path to the PDF file
            filename: Optional custom filename for S3 (default: auto-generated)
            
        Returns:
            str: Public S3 URL of the uploaded PDF
        """
        bucket_name = current_app.config['S3_BUCKET_NAME']
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"catalog_{timestamp}_{uuid.uuid4().hex[:8]}.pdf"
        
        # Create S3 key
        key = f"catalogs/{filename}"
        
        # Upload to S3
        file_url = s3_service.upload_file(pdf_path, bucket_name=bucket_name, key=key)
        
        return file_url


# Create a singleton instance
pdf_service = PDFService()

