# 🎉 What's New in Musium v2.0

## 📦 Latest Updates

### ✅ **Per-Tenant Image Storage**
- Each artist now has their own dedicated image directory
- Path: `/static/tenants/<your-slug>/author_images/`
- No more naming conflicts between artists
- Easier to manage and backup individual artists' data

### ⚡ **Bulk Spotify Fetch**
- NEW button in admin panel: "Bulk Fetch from Spotify"
- Automatically fetches for ALL songs:
  - Missing artist images
  - Music genres
  - Song languages
- Saves hours of manual work!

### 📊 **CSV Upload Improvements**
- File preview before upload (size + estimated song count)
- Confirmation dialog for large uploads (>100 songs)
- Progress bar during upload
- Status messages ("Reading CSV...", "Processing songs...", etc.)
- Now supports 8 columns: title, author, language, image, requests, popularity, **genre**, **playlist**

### 🔐 **Complete Password Management**
- First-time password setup via email token
- Forgot password flow with reset email
- Change password in tenant admin panel
- Secure token-based authentication

### 🌍 **Multi-Language Support**
- Per-tenant language preference
- Invitation emails in tenant's language
- Admin panel defaults to tenant's preferred language
- Support for: English, Italian, Spanish, German, French

### 🎵 **Enhanced Song Database**
- Added **genre** field (Rock, Pop, Jazz, etc.)
- Added **playlist** field for custom organization
- Client-side filtering by genre and playlist
- Spotify API integration for automatic genre detection

---

## 🚀 **How to Use New Features**

### Bulk Spotify Fetch
1. Log in to your tenant admin
2. Scroll to the green "Bulk Fetch from Spotify" card
3. Click "Fetch Missing Data"
4. Wait for processing (progress shown)
5. Review results and check your Songs Database

### CSV with Genres & Playlists
```csv
Hotel California,EAGLES,en,EAGLES.jpg,0,50,Rock,Classic Rock
Perfect,ED SHEERAN,en,EDSHEERAN.jpg,0,75,Pop,Wedding Songs
```

### Large CSV Uploads
1. Select your CSV file
2. Review file info (size + song count)
3. Click "Upload"
4. If >100 songs, confirm the upload
5. Watch progress bar
6. View results when complete

---

## 🔧 **Migration Tools**

### Migrate Existing Images
If you have images in `/static/author_images/`:

```bash
python3 migrate_images_to_tenant.py
```

This safely copies images to tenant-specific directories.

---

## 📝 **Breaking Changes**

### Image Paths
- **Old**: `/static/author_images/ARTIST.jpg`
- **New**: `/static/tenants/<slug>/author_images/ARTIST.jpg`

The app handles both paths for backwards compatibility.

---

## 🐛 **Bug Fixes**

- ✅ Fixed SQLite Row `.get()` AttributeError on login
- ✅ Fixed Jinja2 template syntax error in admin panel
- ✅ Fixed language change routing for tenant-specific URLs
- ✅ Fixed duplicate song display in end-user interface
- ✅ Fixed tenant data isolation across all routes

---

## 📚 **Documentation**

- `CSV_FORMAT.md` - Complete CSV format guide
- `IMAGE_ORGANIZATION.md` - Image storage architecture
- `LANGUAGE_FEATURE.md` - Multi-language system details
- `SETUP_GUIDE.md` - Fresh installation guide

---

## 🎯 **Ready for Beta!**

All critical features are implemented:
- ✅ Multi-tenant architecture
- ✅ Password management
- ✅ CSV upload with validation
- ✅ Bulk Spotify integration
- ✅ Per-tenant data isolation
- ✅ Multi-language support

**Next Steps**: Deploy to production and start testing with real artists!









