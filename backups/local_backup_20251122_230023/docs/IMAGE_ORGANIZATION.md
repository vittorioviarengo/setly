# 🖼️ Image Organization in Musium

## Current Image Structure

### Song/Artist Images
**Current Location**: `/static/author_images/`
- All tenants share the same directory
- Images referenced in CSV as filenames (e.g., `EAGLES.jpg`)
- Images displayed from: `/static/author_images/EAGLES.jpg`

### Tenant-Specific Images
**Current Location**: `/static/tenants/<tenant-slug>/`
- ✅ `logos/` - Tenant logos (16x16 icon)
- ✅ `images/` - Welcome banner images

---

## 🎯 Recommended: Per-Tenant Author Images

### Proposed Structure
```
/static/
  ├── author_images/          # Shared/legacy images (optional)
  └── tenants/
      ├── sergio/
      │   ├── logos/          # ✅ Already exists
      │   ├── images/         # ✅ Already exists  
      │   └── author_images/  # 🆕 Per-tenant song images
      ├── laura/
      │   ├── logos/
      │   ├── images/
      │   └── author_images/  # 🆕 Per-tenant song images
      └── vittorio/
          ├── logos/
          ├── images/
          └── author_images/  # 🆕 Per-tenant song images
```

---

## ✅ Benefits of Per-Tenant Author Images

### 1. **Data Isolation**
- Each artist has their own image library
- No risk of overwriting another tenant's images
- Easier to manage permissions

### 2. **Naming Flexibility**
- Two artists can both have `EAGLES.jpg` without conflict
- No need for unique naming schemes across all tenants
- Simpler image management

### 3. **Backup & Migration**
- Easy to backup one artist's entire data set
- Simple to export/import a complete tenant
- All tenant data in one directory tree

### 4. **Scalability**
- Works for 10 tenants or 10,000 tenants
- No single directory with thousands of images
- Better filesystem performance

### 5. **Consistency**
- Matches existing tenant data structure
- Logos and banners are already per-tenant
- Logical organization

---

## 📋 Implementation Options

### Option 1: Keep Current (Shared Directory)
**Pros:**
- ✅ No code changes needed
- ✅ Works now
- ✅ Simple for single-tenant use

**Cons:**
- ❌ Naming conflicts between tenants
- ❌ Harder to manage multiple artists
- ❌ Less organized at scale

### Option 2: Per-Tenant Directories (Recommended)
**Pros:**
- ✅ Better multi-tenancy
- ✅ No naming conflicts
- ✅ Easier data management
- ✅ More professional architecture

**Cons:**
- ⚠️ Requires code changes
- ⚠️ Need migration for existing images
- ⚠️ CSV must reference correct path

### Option 3: Hybrid Approach
- Keep `/static/author_images/` for shared/common images
- Add `/static/tenants/<slug>/author_images/` for tenant-specific
- Check tenant directory first, fallback to shared

---

## 🔧 Implementation Plan (If Needed)

### Phase 1: Add Per-Tenant Support
1. Create `author_images/` directory for each tenant
2. Update image upload route to save to tenant directory
3. Update image display logic to use tenant path
4. Test with new uploads

### Phase 2: Migration (Optional)
1. Create migration script for existing images
2. Copy images to appropriate tenant directories
3. Update database references if needed
4. Keep originals as backup

### Phase 3: CSV Updates
Update CSV documentation to specify:
- Images should exist in tenant's `author_images/` directory
- OR provide full path in CSV
- OR keep using shared directory for backwards compatibility

---

## 💡 Current Recommendation

**For Now**: Keep the current structure (`/static/author_images/`) since:
- The app is nearly ready for beta
- Changing this affects multiple components
- Can be migrated later without data loss
- Works fine for initial tenants

**For Future**: Plan migration to per-tenant directories:
- Better for long-term scalability
- Cleaner architecture
- Easier multi-tenant management

---

## 🎨 Image Upload Workflow (Current)

### Via CSV:
1. Artist prepares CSV with image filenames
2. Artist uploads images to `/static/author_images/`
3. Artist uploads CSV via admin panel
4. Songs reference images by filename

### Via Spotify:
1. Artist clicks "Fetch from Spotify" for a song
2. App downloads image from Spotify API
3. Image saved to `/static/author_images/`
4. Database updated with filename

### Via Manual Upload:
1. Artist can manually upload image files
2. Images saved to `/static/author_images/`
3. Can be referenced in CSV or directly in UI

---

## 📝 CSV Image Reference

### Current Format:
```csv
Song Title,Artist,en,ARTIST.jpg,0,0,Pop,Playlist
```

The image column (`ARTIST.jpg`) is just a filename, not a path.

### If Moving to Per-Tenant:
```csv
Song Title,Artist,en,ARTIST.jpg,0,0,Pop,Playlist
```

Same format! The code would automatically look in the right tenant directory.

---

## 🚀 Next Steps

1. **For Beta Launch**: Use current structure
2. **Post-Beta**: Evaluate based on usage
3. **If Scaling**: Migrate to per-tenant structure
4. **Tool Needed**: Create migration script

---

## 🔍 Technical Details

### Current Image Path Construction:
```javascript
const authorImage = `/static/author_images/${song.image}`;
```

### Per-Tenant Would Be:
```javascript
const authorImage = `/static/tenants/${tenantSlug}/author_images/${song.image}`;
```

### Upload Location (Current):
```python
app.config['UPLOAD_FOLDER'] = 'static/author_images'
```

### Upload Location (Per-Tenant):
```python
upload_folder = f'static/tenants/{tenant_slug}/author_images'
```

---

## ⚠️ Important Notes

- **CSV doesn't include paths** - only filenames
- **Images must be uploaded separately** from CSV
- **Spotify fetch** auto-downloads and saves images
- **Shared directory works** for initial beta testing
- **Migration is possible** without breaking existing data

---

## Questions?

Contact the development team for:
- Migration assistance
- Bulk image uploads
- Custom image organization
- Technical support









