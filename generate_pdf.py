from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, PageBreak, Frame, PageTemplate, KeepTogether, Spacer
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import sqlite3
from reportlab.lib.units import inch
import sys
import os
import qrcode
from io import BytesIO
import logging

# Configure logging to stderr (captured by Flask logs)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s: PDF_GEN: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Get the absolute path of the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Register the Gothic font using absolute path
font_path = os.path.join(SCRIPT_DIR, 'static', 'fonts', 'Century Gothic.ttf')
pdfmetrics.registerFont(TTFont('Gothic', font_path))

def fetch_songs(tenant_id):
    # Connect to the database using absolute path
    db_path = os.path.join(SCRIPT_DIR, 'songs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch songs sorted by author (then title), excluding popularity, filtered by tenant_id
    cursor.execute("SELECT title, author FROM songs WHERE tenant_id = ? ORDER BY author, title", (tenant_id,))
    songs = cursor.fetchall()
    
    conn.close()
    return songs

def get_tenant_info(tenant_id):
    # Connect to the database using absolute path
    db_path = os.path.join(SCRIPT_DIR, 'songs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch tenant information
    cursor.execute("SELECT name, slug, logo_image, banner_image FROM tenants WHERE id = ?", (tenant_id,))
    tenant = cursor.fetchone()
    
    conn.close()
    if tenant:
        return {
            'name': tenant[0],
            'slug': tenant[1],
            'logo_image': tenant[2],
            'banner_image': tenant[3]
        }
    return None

def get_app_url():
    # Connect to the database
    conn = sqlite3.connect('songs.db')
    cursor = conn.cursor()
    
    # Fetch app URL from system settings
    cursor.execute("SELECT value FROM system_settings WHERE key = 'app_url'")
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else 'http://localhost:5001'

def add_background(canvas, doc, tenant_info):
    # Get the size of the page
    page_width, page_height = doc.pagesize
    tenant_name = tenant_info['name'] if tenant_info else 'Sergio Chiappa'
    page_num = canvas.getPageNumber()
    
    # Only draw the black background and image on page 1 (cover page)
    if page_num == 1:
        # First, save the canvas state
        canvas.saveState()
        
        # Draw a black background for the cover page
        canvas.setFillColor(colors.black)
        canvas.rect(0, 0, page_width, page_height, fill=1)
        
        # Path to the background image - use tenant's banner or default (using absolute paths)
        image_path = None
        default_image = os.path.join(SCRIPT_DIR, 'static', 'img', 'musician-welcome-stock-photo.jpg')
        
        # Try tenant's banner first
        if tenant_info and tenant_info.get('banner_image'):
            tenant_image = os.path.join(SCRIPT_DIR, 'static', tenant_info['banner_image'])
            logger.info(f"Looking for tenant banner at: {tenant_image}")
            if os.path.exists(tenant_image):
                image_path = tenant_image
                logger.info(f"✓ Tenant banner found")
            else:
                logger.warning(f"✗ Tenant banner NOT found at: {tenant_image}")
        
        # Fallback to default image if tenant image doesn't exist
        if not image_path:
            logger.info(f"Trying default image at: {default_image}")
            if os.path.exists(default_image):
                image_path = default_image
                logger.info(f"✓ Default image found")
            else:
                logger.warning(f"✗ Default image NOT found")
        
        # Try to load and draw the image
        if image_path:
            try:
                logger.info(f"Loading image: {image_path}")
                # Load the image
                img = Image(image_path)
                
                # Calculate the aspect ratio of the image
                img_width, img_height = img.drawWidth, img.drawHeight
                img_aspect = img_width / img_height
                
                # Determine the dimensions to draw the image
                draw_width = page_width
                draw_height = page_width / img_aspect
                
                # Draw the image at the top of the page
                canvas.drawImage(image_path, 0, page_height - draw_height, width=draw_width, height=draw_height, mask='auto')
                logger.info(f"✓ Image drawn successfully")
            except Exception as e:
                logger.error(f"✗ Could not load/draw image {image_path}: {e}")
                draw_height = 200  # Default height if image fails to load
        else:
            # No image available, use simple gradient background
            logger.warning("No image available, using black background only")
            draw_height = 200
        
        # Add the text in Gothic font, white color, 30 points, centered
        text = f"L'Universo Musicale di<br/>{tenant_name}"
        
        # Create a Paragraph with the desired text and style
        style = ParagraphStyle(name='GothicStyle', fontName='Gothic', fontSize=30, textColor=colors.white, leading=36, alignment=1)
        paragraph = Paragraph(text, style)
        
        # Set the width and height for the paragraph
        width, height = paragraph.wrap(page_width - 100, page_height)
        
        # Draw the paragraph on the canvas
        paragraph.drawOn(canvas, (page_width - width) / 2, page_height - draw_height - height - 50)
        
        # Restore canvas state
        canvas.restoreState()

def add_footer(canvas, doc, tenant_info):
    """Draw footer on every page - called AFTER page content is drawn"""
    page_width, page_height = doc.pagesize
    tenant_name = tenant_info['name'] if tenant_info else 'Sergio Chiappa'
    page_num = canvas.getPageNumber()
    
    # Save canvas state
    canvas.saveState()
    
    # Draw a dark gray footer bar (clean, professional look)
    canvas.setFillColor(colors.HexColor('#2c2c2c'))
    canvas.rect(0, 0, page_width, 45, fill=1, stroke=0)
    
    # Add footer text in white on top of the bar
    canvas.setFont('Gothic', 10)
    canvas.setFillColor(colors.white)
    
    # Page number on the left
    canvas.drawString(50, 18, f"Page {page_num}")
    
    # Performer name on the right
    canvas.drawRightString(page_width - 50, 18, tenant_name)
    
    # Restore canvas state
    canvas.restoreState()

def add_qr_code_message(elements, tenant_info, base_url="http://localhost:5001"):
    # Create an empty paragraph for spacing
    empty_paragraph = Paragraph("<br/><br/>", ParagraphStyle(name='EmptySpace'))
    
    # Add the message
    message_text = "You can also request your favorite songs<br/>By scanning this QR code"
    message_style = ParagraphStyle(name='MessageStyle', fontName='Gothic', fontSize=14, textColor=colors.black, alignment=1)
    message_paragraph = Paragraph(message_text, message_style)
    
    # Generate QR code dynamically for this tenant
    tenant_slug = tenant_info['slug'] if tenant_info and tenant_info.get('slug') else 'default'
    qr_url = f"{base_url}/{tenant_slug}"
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    # Create an image from the QR code
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert PIL image to bytes
    img_buffer = BytesIO()
    qr_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Create reportlab Image from bytes
    qr_code_image = Image(img_buffer)
    qr_code_image.drawHeight = 2 * inch  # Adjust the height as needed
    qr_code_image.drawWidth = 2 * inch   # Adjust the width as needed
    qr_code_image.hAlign = 'CENTER'
    
    # Create a table with the QR code message and image
    data = [
        [message_paragraph],
        [qr_code_image]
    ]
    
    table = Table(data, colWidths=[6.5 * inch])  # Adjust column width as needed
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Thin black border around the table
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Center the content
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertically center the content
        ('TOPPADDING', (0, 0), (-1, 0), 12),  # Add padding above the message text
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  # Add padding below the message text
        ('TOPPADDING', (0, 1), (-1, 1), 12),  # Add padding above the QR code image
        ('BOTTOMPADDING', (0, 1), (-1, 1), 12),  # Add padding below the QR code image
    ]))
    
    # Add the empty paragraph, table, and another empty paragraph to the elements
    elements.append(empty_paragraph)
    elements.append(table)
    elements.append(empty_paragraph)

def generate_pdf(output_path, tenant_id):
    # Fetch tenant info and songs data
    tenant_info = get_tenant_info(tenant_id)
    songs = fetch_songs(tenant_id)
    app_url = get_app_url()
    
    tenant_name = tenant_info['name'] if tenant_info else 'Artist'
    
    # Create a PDF document with proper margins for footer
    pdf = SimpleDocTemplate(
        output_path, 
        pagesize=letter,
        leftMargin=72,
        rightMargin=72,
        topMargin=72,
        bottomMargin=50  # Space for footer (reduced to give more room for content)
    )
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']

    # Page 1: Cover page (drawn by onFirstPage callback - no content needed)
    elements.append(PageBreak())  # Move to page 2 for intro text
    
    intro_text = f"""
    <strong>Italiano:</strong><br/>
    Goditi una selezione delle canzoni preferite di {tenant_name}. Rendi questa serata ancora più speciale richiedendo o dedicando una canzone a una persona cara scannerizzando il codice qui sotto.<br/><br/><br/>

    <strong>English:</strong><br/>
    Enjoy a selection of {tenant_name}'s favorite songs. Make this evening more special by requesting or dedicating a song to a loved one by scanning the code below.<br/><br/><br/>
    
    <strong>Français:</strong><br/>
    Profitez d'une sélection des chansons préférées de {tenant_name}. Rendez cette soirée encore plus spéciale en demandant ou en dédiant une chanson à un être cher en scannant le code ci-dessous.<br/><br/><br/>

    <strong>Deutsch:</strong><br/>
    Genießen Sie eine Auswahl von {tenant_name}'s Lieblingsliedern. Machen Sie diesen Abend noch besonderer, indem Sie ein Lied für einen geliebten Menschen anfordern oder widmen, indem Sie den untenstehenden Code scannen.<br/><br/><br/>

    <strong>Español:</strong><br/>
    Disfrute de una selección de las canciones favoritas de {tenant_name}. Haga esta noche aún más especial solicitando o dedicando una canción a un ser querido escaneando el código a continuación.
    """
    intro_style = ParagraphStyle(name='IntroStyle', fontName='Gothic', fontSize=14, textColor=colors.black, alignment=1, leading=12)
    intro_paragraph = Paragraph(intro_text, intro_style)

    elements.append(intro_paragraph)
    add_qr_code_message(elements, tenant_info, app_url)

    # Prepare data for the table on the third page
    data = songs  # No header row

    # Define column widths
    col_widths = [3.25 * inch, 3.25 * inch]  # Adjust column widths as needed

    # Add a page break after the first page
    elements.append(PageBreak())

    # Create a table in chunks and insert QR code message every 3 pages
    chunk_size = 42  # Increased from 38 - more rows fit with reduced footer space
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        table = Table(chunk, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),  # Align title to the right
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),   # Align author to the left
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),  # Increased font size from default (10) to 11
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # Slightly increased padding for better readability
            ('TOPPADDING', (0, 0), (-1, -1), 2),     # Slightly increased padding for better readability
        ]))
        elements.append(table)

        # Insert the QR code message every 3 pages
        if (i // chunk_size + 1) % 3 == 0:
            qr_code_elements = []
            add_qr_code_message(qr_code_elements, tenant_info, app_url)
            elements.append(KeepTogether(qr_code_elements))

    # Build the PDF with callbacks for first page and later pages
    # This ensures footer is drawn AFTER content, not before
    def first_page(canvas, doc):
        canvas.saveState()
        add_background(canvas, doc, tenant_info)  # Draw cover on page 1
        add_footer(canvas, doc, tenant_info)      # Draw footer
        canvas.restoreState()
    
    def later_pages(canvas, doc):
        canvas.saveState()
        add_footer(canvas, doc, tenant_info)      # Draw footer on all other pages
        canvas.restoreState()
    
    # Build with custom callbacks
    pdf.build(elements, onFirstPage=first_page, onLaterPages=later_pages)

# Generate the PDF
if __name__ == "__main__":
    # Default to tenant_id=1 (Sergio) if run standalone
    tenant_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    logger.info(f"========== Starting PDF generation for tenant_id={tenant_id} ==========")
    tenant_info = get_tenant_info(tenant_id)
    if tenant_info:
        logger.info(f"Tenant info: name={tenant_info['name']}, slug={tenant_info['slug']}")
        logger.info(f"Banner: {tenant_info.get('banner_image', 'None')}")
        logger.info(f"Logo: {tenant_info.get('logo_image', 'None')}")
    else:
        logger.error(f"Tenant with ID {tenant_id} not found!")
    tenant_name = tenant_info['name'] if tenant_info else 'Artist'
    output_filename = f"{tenant_name} Repertorio.pdf"
    generate_pdf(output_filename, tenant_id)
    logger.info(f"========== PDF generation completed: {output_filename} ==========")

