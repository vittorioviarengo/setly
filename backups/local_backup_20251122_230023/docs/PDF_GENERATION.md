# PDF Generation Feature

## Overview
The PDF generation feature creates a printable song repertoire for each tenant.

## Current Status
⚠️ **Requires Additional Setup**

## Requirements

The PDF generation feature requires the `reportlab` library, which is not currently installed.

### Installation

To enable PDF generation, run:

```bash
pip3 install reportlab
```

### What's Included

- **Script**: `generate_pdf.py`
- **Route**: `/<tenant_slug>/generate_pdf`
- **Font**: `static/fonts/Century Gothic.ttf` (required)

### How It Works

1. Fetches all songs for the specified tenant
2. Generates a multi-page PDF with:
   - Cover page with tenant logo/banner
   - Introductory text in multiple languages (IT, EN, FR, DE, ES)
   - Song list sorted alphabetically by title
   - QR code message placeholders
3. Saves the PDF as `{Tenant Name} Repertorio.pdf`

### Testing

Once reportlab is installed, test the feature:

1. Go to: `http://127.0.0.1:5001/{tenant_slug}/generate_pdf`
2. The PDF will be generated and downloaded automatically

### Known Issues

- The font file path is hardcoded to `static/fonts/Century Gothic.ttf`
- Make sure this font file exists, or update the font registration in `generate_pdf.py`

### Alternative: Disable the Feature

If you don't need PDF generation, you can:

1. Comment out the `/generate_pdf` routes in `app.py` (lines 166-246)
2. Remove the PDF generation button from your templates (if any)

## Notes

- PDF generation is synchronous and may take a few seconds for large song libraries
- The generated PDF is stored in the project root directory
- Consider adding PDF cleanup scripts if generating many PDFs

