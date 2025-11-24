# 📧 Email Setup Guide for Musium

## Quick Setup (5 minutes)

### Step 1: Generate Gmail App Password

1. **Go to Google Account Security**
   - Visit: https://myaccount.google.com/security
   - Or: Google Account → Security (left menu)

2. **Enable 2-Factor Authentication** (if not already enabled)
   - Scroll to "How you sign in to Google"
   - Click "2-Step Verification"
   - Follow the setup wizard

3. **Generate App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Or search "App passwords" in your Google Account settings
   - Select:
     - **App**: Mail
     - **Device**: Other (Custom name)
     - Name it: "Musium" or "Songs App"
   - Click "Generate"
   
4. **Copy the 16-character password**
   - Google shows something like: `abcd efgh ijkl mnop`
   - Copy it (remove spaces): `abcdefghijklmnop`

### Step 2: Configure Your App

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** and update these lines:
   ```bash
   MAIL_USERNAME=your-actual-email@gmail.com
   MAIL_PASSWORD=abcdefghijklmnop  # paste the 16-char password from Step 1
   ```

3. **That's it!** The app will automatically load these variables.

### Step 3: Test It

1. **Run the app:**
   ```bash
   python3 app.py
   ```

2. **Create a new tenant** from the superadmin panel
3. **Check "Send Invitation"**
4. You should see: "Invitation email sent successfully!" instead of "Email not configured"
5. Check your email inbox for the invitation!

---

## Troubleshooting

### "Email not configured" still appearing
- Make sure you copied `.env.example` to `.env` (without the `.example`)
- Check that `MAIL_USERNAME` and `MAIL_PASSWORD` are filled in
- Restart the app after editing `.env`

### "Authentication failed" error
- You're using your regular Gmail password instead of an App Password
- Generate a new App Password following Step 1 above
- Make sure there are no spaces in the password

### Can't find "App Passwords" in Google
- You need to enable 2-Factor Authentication first
- App Passwords only appear after 2FA is enabled
- Try the direct link: https://myaccount.google.com/apppasswords

### Want to use a different email service?
Edit these in `.env`:

**Outlook/Hotmail:**
```bash
MAIL_SERVER=smtp-mail.outlook.com
MAIL_PORT=587
MAIL_USERNAME=your-email@outlook.com
MAIL_PASSWORD=your-outlook-password
```

**Yahoo:**
```bash
MAIL_SERVER=smtp.mail.yahoo.com
MAIL_PORT=587
MAIL_USERNAME=your-email@yahoo.com
MAIL_PASSWORD=your-yahoo-app-password
```

---

## Security Notes

- ✅ **`.env` is already in `.gitignore`** - your credentials won't be committed to git
- ✅ Use App Passwords, not your main Gmail password
- ✅ Never share your `.env` file
- ✅ For production, use environment variables or a secrets manager

---

## Production Deployment

For production (not localhost), consider:

1. **SendGrid** (https://sendgrid.com) - Free tier: 100 emails/day
2. **Mailgun** (https://www.mailgun.com) - Free tier: 5,000 emails/month
3. **Amazon SES** (https://aws.amazon.com/ses) - $0.10 per 1,000 emails

These are more reliable than Gmail for production apps.









