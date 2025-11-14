# PythonAnywhere Deployment Guide

## Prerequisites
- PythonAnywhere account (https://www.pythonanywhere.com/)
- Your application code and database ready
- Spotify API credentials (if using Spotify features)
- Email credentials (if using email features)

## Step 1: Upload Your Code

### Option A: Using Git (Recommended)
```bash
# On PythonAnywhere Bash console:
cd ~
git clone YOUR_REPOSITORY_URL Songs_2.0
cd Songs_2.0
```

### Option B: Manual Upload
1. Go to Files tab in PythonAnywhere
2. Upload all your files (excluding venv, __pycache__, *.pyc, .git)
3. Or use "Upload a file" and then unzip

## Step 2: Create Virtual Environment
```bash
# In PythonAnywhere Bash console:
cd ~/Songs_2.0
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 3: Set Up the Database
```bash
# Make sure you're in the project directory with venv activated
cd ~/Songs_2.0
source venv/bin/activate

# Create the superadmin database structure
python create_superadmin_db.py

# If you have an existing database, upload it via Files tab
# Otherwise, populate with your CSV data using load_db.py
```

## Step 4: Configure Environment Variables
Create a file `.env` in your project root (or set in PythonAnywhere Web tab):

```bash
# Spotify API (optional, for fetching artist data)
export SPOTIPY_CLIENT_ID='your_spotify_client_id'
export SPOTIPY_CLIENT_SECRET='your_spotify_client_secret'

# Flask Secret Key (IMPORTANT: change this!)
export SECRET_KEY='your-super-secret-random-key-here'

# Email Configuration (optional, for password resets and invitations)
export MAIL_SERVER='smtp.gmail.com'
export MAIL_PORT=587
export MAIL_USE_TLS=True
export MAIL_USERNAME='your_email@gmail.com'
export MAIL_PASSWORD='your_app_password'
export MAIL_DEFAULT_SENDER='noreply@yourapp.com'
```

**Generate a secret key:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Step 5: Create WSGI Configuration File
1. Go to **Web** tab in PythonAnywhere
2. Click "Add a new web app"
3. Choose "Manual configuration" (not Django/Flask wizard)
4. Select Python 3.10
5. Once created, click on the WSGI configuration file link

Replace the contents with:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/YOUR_USERNAME/Songs_2.0'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables (or load from .env)
os.environ['SECRET_KEY'] = 'your-super-secret-key-here'
os.environ['SPOTIPY_CLIENT_ID'] = 'your_spotify_client_id'
os.environ['SPOTIPY_CLIENT_SECRET'] = 'your_spotify_client_secret'
os.environ['MAIL_USERNAME'] = 'your_email@gmail.com'
os.environ['MAIL_PASSWORD'] = 'your_app_password'

# Import your Flask app
from app import app as application
```

**Replace `YOUR_USERNAME` with your PythonAnywhere username!**

## Step 6: Configure Static Files
In the **Web** tab, scroll down to **Static files** section:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOUR_USERNAME/Songs_2.0/static/` |

## Step 7: Set Virtualenv Path
In the **Web** tab, under **Virtualenv** section:
```
/home/YOUR_USERNAME/Songs_2.0/venv
```

## Step 8: Reload and Test
1. Click the big green **Reload** button at the top of the Web tab
2. Visit your site: `https://YOUR_USERNAME.pythonanywhere.com`
3. Test the super admin login: `/superadmin/login`
   - Username: `superadmin`
   - Password: `admin123` (change this immediately!)

## Step 9: Upload Static Files (Images, Logos, Banners)
```bash
# In PythonAnywhere Files tab or via Bash:
cd ~/Songs_2.0/static
# Upload your directories:
# - author_images/
# - img/
# - tenants/
```

Or use rsync/scp from your local machine:
```bash
# From your local machine:
scp -r static/author_images YOUR_USERNAME@ssh.pythonanywhere.com:~/Songs_2.0/static/
scp -r static/tenants YOUR_USERNAME@ssh.pythonanywhere.com:~/Songs_2.0/static/
```

## Step 10: Database Upload
If you have an existing database:
```bash
# From local machine:
scp songs.db YOUR_USERNAME@ssh.pythonanywhere.com:~/Songs_2.0/
```

Or upload via Files tab in PythonAnywhere.

## Common Issues & Solutions

### Issue: Import errors
**Solution**: Make sure virtualenv is activated and all requirements are installed:
```bash
cd ~/Songs_2.0
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Static files not loading
**Solution**: Check Static files mapping in Web tab and verify paths are correct.

### Issue: Database locked errors
**Solution**: SQLite can have issues with concurrent writes. Consider:
- Using connection pooling
- Setting `timeout` in database connections
- For high traffic, migrate to MySQL (available in paid plans)

### Issue: "Module not found" errors
**Solution**: Check WSGI file has correct paths and `sys.path.insert` is before imports.

### Issue: 500 Internal Server Error
**Solution**: 
1. Check error logs in Web tab → Log files
2. Check WSGI file syntax
3. Verify environment variables are set

## Security Checklist
- [ ] Change default super admin password
- [ ] Set strong SECRET_KEY
- [ ] Don't commit .env files to git
- [ ] Set proper file permissions for sensitive files
- [ ] Enable HTTPS (automatic on PythonAnywhere)
- [ ] Regularly backup your database

## Maintenance

### Updating Code
```bash
cd ~/Songs_2.0
source venv/bin/activate
git pull  # if using git
# or upload new files via Files tab
# Then reload your web app from Web tab
```

### Database Backup
```bash
# Schedule in PythonAnywhere Tasks tab:
cp ~/Songs_2.0/songs.db ~/Songs_2.0/backups/songs_$(date +%Y%m%d).db
```

### View Logs
- Error log: `/var/log/YOUR_USERNAME.pythonanywhere.com.error.log`
- Server log: `/var/log/YOUR_USERNAME.pythonanywhere.com.server.log`

## Custom Domain (Optional)
1. Go to Web tab
2. Add your custom domain in CNAME section
3. Set DNS CNAME record to point to `YOUR_USERNAME.pythonanywhere.com`
4. Wait for DNS propagation (can take up to 48 hours)

## Upgrading to Paid Plan Benefits
- MySQL/PostgreSQL databases
- More CPU time
- Longer-running tasks
- SSH access
- No PythonAnywhere branding
- Custom domains

## Support
- PythonAnywhere forums: https://www.pythonanywhere.com/forums/
- PythonAnywhere help: https://help.pythonanywhere.com/

## Quick Reference Commands
```bash
# Activate virtualenv
cd ~/Songs_2.0 && source venv/bin/activate

# View error logs
tail -f /var/log/YOUR_USERNAME.pythonanywhere.com.error.log

# Database console
cd ~/Songs_2.0 && sqlite3 songs.db

# Update packages
pip install --upgrade -r requirements.txt

# Compile translations
pybabel compile -d translations
```

---

**Remember**: Replace `YOUR_USERNAME` with your actual PythonAnywhere username throughout all commands and configurations!

