# 🎵 Setly - Live Music Song Request Platform

A multi-tenant platform that allows musicians and artists to receive song requests from their audience in real-time during live performances.

## ✨ Features

- 🎤 **Multi-Tenant System**: Each artist gets their own branded page
- 🌍 **Multi-Language**: Italian, English, French, German, Spanish
- 📱 **Mobile Responsive**: Works on all devices
- 🎯 **Real-Time Queue**: Live song request management
- 🎨 **Customizable Branding**: Logo, banner, colors
- 📊 **Song Management**: CSV import, Spotify integration
- 📄 **PDF Generation**: Printable song lists with QR codes
- ⚙️ **Setup Wizard**: Easy onboarding for new artists
- 👥 **Super Admin**: Centralized tenant management

## 🚀 Quick Start

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from app import init_db; init_db()"

# Compile translations
pybabel compile -d translations

# Run app
python app.py
```

Visit: `http://localhost:5001`

## 📦 Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite (PostgreSQL ready)
- **Frontend**: Vanilla JS, CSS
- **i18n**: Flask-Babel
- **PDF**: ReportLab
- **APIs**: Spotify Web API

## 📝 License

Proprietary - All Rights Reserved

## 👨‍💻 Author

Vittorio Viarengo

---

For deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)
