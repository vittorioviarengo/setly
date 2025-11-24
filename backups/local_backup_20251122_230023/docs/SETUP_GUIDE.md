# 🎵 Musium App - Complete Setup Guide

**A multi-tenant song request management system for musicians**

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Fresh Installation](#fresh-installation)
3. [Email System Setup](#email-system-setup)
4. [Database Setup](#database-setup)
5. [Running the App](#running-the-app)
6. [Deployment to PythonAnywhere](#deployment-to-pythonanywhere)
7. [Troubleshooting](#troubleshooting)

---

## 🔧 Prerequisites

Before you begin, ensure you have:

- **Python 3.9+** installed
- **pip** (Python package manager)
- **Git** (optional, for cloning)
- **Gmail account** with 2-Factor Authentication enabled

---

## 🚀 Fresh Installation

### Step 1: Clone or Download the Project

```bash
cd ~/Code
git clone <your-repo-url> "Songs 2.0"
cd "Songs 2.0"
```

### Step 2: Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

**Required packages:**
- Flask==3.0.3
- Flask-Babel==4.0.0
- Flask-SQLAlchemy==3.1.1
- Flask-Mail==0.9.1
- spotipy==2.23.0
- requests==2.32.3
- Werkzeug==3.0.1
- SQLAlchemy==2.0.30
- python-dotenv==1.0.0
- polib==1.2.0

### Step 3: Set Up Environment Variables

The `.env` file is already configured with your email credentials:

```bash
# Email is already set up:
MAIL_USERNAME=vittorio@gmail.com
MAIL_PASSWORD=jtaelrnqafraeeeq
```

**⚠️ Security Note:** Never commit the `.env` file to Git. It's already in `.gitignore`.

---

## 📧 Email System Setup

### How the Email System Works

The app sends email invitations to new tenants with password setup links. The system uses:

- **Gmail SMTP** (smtp.gmail.com:587)
- **App Password** (not your regular Gmail password)
- **Flask-Mail** for sending emails

### Your Current Configuration

✅ **Already configured!**

- Email: `vittorio@gmail.com`
- App Password: `jtaelrnqafraeeeq`
- From Address: `noreply@musium.app`

### If You Need to Change Email Settings

1. **Get a new Gmail App Password:**
   - Visit: https://myaccount.google.com/apppasswords
   - Enable 2-Factor Auth if not already enabled
   - Generate a new password for "Mail"

2. **Update `.env` file:**
   ```bash
   MAIL_USERNAME=your-new-email@gmail.com
   MAIL_PASSWORD=your-new-app-password
   ```

3. **Restart the app** for changes to take effect

---

## 🎵 Spotify API Setup

### What Spotify Does

The app uses Spotify's API to automatically fetch:
- **Artist images** (high-quality profile photos)
- **Music genres** (pop, rock, jazz, etc.)
- **Song language** (inferred from artist's markets)

This saves you time when adding new songs to your database!

### Your Current Configuration

✅ **Already configured!**

- Client ID: `4dd130b8c960408798e64c30f04d67ad`
- Client Secret: `96c2357eea1e400e9921799f45581370`
- Status: READY TO USE

### How to Get Your Own Spotify API Credentials (Optional)

If you want to use your own Spotify Developer account:

#### Step 1: Create Spotify Developer Account

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account (or create one)
3. Accept the Terms of Service

#### Step 2: Create an App

1. Click **"Create app"**
2. Fill in:
   - **App name:** Musium Song Manager
   - **App description:** Multi-tenant song request management system
   - **Redirect URI:** `http://localhost:5001/callback` (required but not used)
   - Check **"Web API"**
3. Click **"Save"**

#### Step 3: Get Your Credentials

1. Click on your new app
2. Click **"Settings"**
3. You'll see:
   - **Client ID** (copy this)
   - **Client Secret** (click "View client secret" and copy)

#### Step 4: Update `.env` File

```bash
SPOTIFY_CLIENT_ID=your-client-id-here
SPOTIFY_CLIENT_SECRET=your-client-secret-here
```

#### Step 5: Restart the App

```bash
lsof -ti:5001 | xargs kill -9 2>/dev/null
python3 app.py
```

### Spotify API Limits

- **Free tier:** 100 requests per hour
- **More than enough** for normal usage
- No credit card required

### What If Spotify API Fails?

Don't worry! The app gracefully handles API failures:
- You can still manually enter artist images
- Song additions work without Spotify data
- App continues to function normally

---

## 🗄️ Database Setup

### Create the Database

The app will auto-create the database on first run, but you can also run:

```bash
# Create superadmin database
python3 create_superadmin_db.py
```

This creates:
- `songs.db` - Main database with:
  - `superadmin` table (credentials: admin@musium.app / password: admin123)
  - `tenants` table (for musicians/artists)
  - `songs` table (tenant-specific song catalogs)
  - `requests` table (song requests per tenant)

### Default Superadmin Credentials

```
Email: admin@musium.app
Password: admin123
URL: http://localhost:5001/superadmin/login
```

**⚠️ Change this password after first login!**

---

## ▶️ Running the App

### Local Development

```bash
# Option 1: Simple start
python3 app.py

# Option 2: With cache clear (recommended during development)
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
find . -name "*.pyc" -delete 2>/dev/null; \
lsof -ti:5001 | xargs kill -9 2>/dev/null; \
sleep 1; \
python3 app.py
```

The app runs on: **http://127.0.0.1:5001**

### Access Points

1. **Superadmin Panel**: http://127.0.0.1:5001/superadmin/login
   - Manage tenants (musicians)
   - View logs
   - System settings

2. **Tenant Admin** (example): http://127.0.0.1:5001/sergio/admin
   - Manage song database
   - View/manage requests
   - Upload logo & banner
   - Change password

3. **Customer Interface** (example): http://127.0.0.1:5001/sergio
   - Browse songs
   - Request songs
   - View request queue

---

## 🌐 Deployment to PythonAnywhere

### Step 1: Create PythonAnywhere Account

1. Go to https://www.pythonanywhere.com
2. Sign up for a free account (Beginner plan)
3. Confirm your email

### Step 2: Upload Your Code

**Option A: Via Git (Recommended)**

```bash
# In PythonAnywhere Bash console:
cd ~
git clone <your-repo-url> musium
cd musium
```

**Option B: Via File Upload**

1. Zip your project folder (exclude `__pycache__`, `.pyc` files, `instance/`)
2. Upload via PythonAnywhere Files tab
3. Unzip in bash console

### Step 3: Set Up Virtual Environment

```bash
cd ~/musium
python3.9 -m virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Paste your configuration:
```
SECRET_KEY=3L+nc\xcd\x02e/\x88\xbf\x9e\xfc\xb5\xa2
DEBUG=False
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=vittorio@gmail.com
MAIL_PASSWORD=jtaelrnqafraeeeq
MAIL_DEFAULT_SENDER=noreply@musium.app
SPOTIFY_CLIENT_ID=4dd130b8c960408798e64c30f04d67ad
SPOTIFY_CLIENT_SECRET=96c2357eea1e400e9921799f45581370
```

**Press:** `Ctrl+X`, then `Y`, then `Enter` to save

### Step 5: Set Up Database

```bash
python3 create_superadmin_db.py
```

### Step 6: Configure WSGI

1. Go to **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Choose **Manual configuration**
4. Select **Python 3.9**
5. Edit the WSGI configuration file:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/yourusername/musium'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

# Import Flask app
from app import app as application
```

### Step 7: Configure Static Files

In the **Web** tab, add static file mappings:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/yourusername/musium/static/` |

### Step 8: Set Up Virtual Environment Path

In the **Web** tab:
- **Virtualenv:** `/home/yourusername/musium/venv`

### Step 9: Reload and Test

1. Click **Reload** button
2. Visit: `https://yourusername.pythonanywhere.com`
3. Test all functionality

---

## 🛠️ Troubleshooting

### Email Not Sending

**Symptom:** "Email not configured" message

**Solution:**
1. Check `.env` file has `MAIL_USERNAME` and `MAIL_PASSWORD` filled in
2. Verify App Password is correct (no spaces)
3. Restart the app
4. Check Gmail hasn't revoked the App Password

### Database Errors

**Symptom:** "no such table" or "database locked"

**Solution:**
```bash
# Recreate database
rm songs.db
python3 create_superadmin_db.py
```

### Port Already in Use

**Symptom:** "Address already in use"

**Solution:**
```bash
lsof -ti:5001 | xargs kill -9
python3 app.py
```

### CSS/JS Not Loading

**Symptom:** Unstyled pages

**Solution:**
- Clear browser cache (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
- Check browser console for 404 errors
- Verify static file paths in templates

### PythonAnywhere 502 Error

**Symptom:** "502 Bad Gateway"

**Solution:**
1. Check WSGI file configuration
2. Check error log in PythonAnywhere
3. Ensure virtual environment is set correctly
4. Check Python version matches (3.9)

---

## 📁 Project Structure

```
Songs 2.0/
├── app.py                      # Main Flask application
├── superadmin_routes.py        # Superadmin panel routes
├── create_superadmin_db.py     # Database initialization
├── .env                        # Environment variables (not in git)
├── songs.db                    # SQLite database
├── requirements.txt            # Python dependencies
├── static/                     # CSS, JS, images
│   ├── css/
│   ├── img/
│   ├── tenants/               # Per-tenant assets
│   └── author_images/         # Artist images from Spotify
├── templates/                  # HTML templates
│   ├── superadmin/
│   └── *.html
├── translations/              # Multilingual support
│   ├── en/, it/, es/, de/, fr/
│   └── */LC_MESSAGES/*.po
└── utils/                     # Utility modules
    └── password_utils.py
```

---

## 🔐 Security Considerations

### Local Development
- ✅ `.env` is in `.gitignore`
- ✅ App Passwords instead of real passwords
- ⚠️ Change default superadmin password

### Production Deployment
- ✅ Set `DEBUG=False` in `.env`
- ✅ Use strong `SECRET_KEY`
- ✅ Use HTTPS (PythonAnywhere provides this)
- ✅ Regular backups of `songs.db`
- ⚠️ Consider using environment variables instead of `.env` on PythonAnywhere

---

## 📞 Support

For issues or questions:
1. Check this guide's Troubleshooting section
2. Read `QUICK_START_EMAIL.txt` for email setup
3. Read `SETUP_EMAIL.md` for detailed email configuration

---

## 🎉 You're Ready!

Your Musium app is now configured and ready to use. Start the app and begin managing your music catalog!

```bash
python3 app.py
```

Visit http://127.0.0.1:5001 to get started! 🚀

