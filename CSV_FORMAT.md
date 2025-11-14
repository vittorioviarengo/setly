# 📄 CSV File Format for Song Upload

## Overview
The Musium app allows tenant admins to bulk upload songs using CSV files. This is the fastest way to populate your song database.

---

## CSV Format

### Required Columns (Minimum 4)
1. **title** - Song title
2. **author** - Artist/band name
3. **language** - Language code (en, it, es, de, fr)
4. **image** - Image filename (can be empty)

### Optional Columns
5. **requests** - Number of requests (defaults to 0)
6. **popularity** - Popularity score (defaults to 0)
7. **genre** - Music genre (defaults to empty)
8. **playlist** - Playlist name for organization (defaults to empty)

---

## Format Details

### Column Order

**Full Format (8 columns):**
```
title,author,language,image,requests,popularity,genre,playlist
```

**Minimal Format (4 columns):**
```
title,author,language,image
```

### Example CSV Content

**Full Format with Genre & Playlist:**
```csv
1973,JAMES BLUNT,en,JAMESBLUNT.jpg,0,0,Pop,Romantic Ballads
A GROOVY KIND OF LOVE,PHIL COLLINS,en,PHILCOLLINS.jpg,0,0,Pop,Love Songs
Hotel California,EAGLES,en,EAGLES.jpg,0,50,Rock,Classic Rock
Perfect,ED SHEERAN,en,EDSHEERAN.jpg,0,75,Pop,Wedding Songs
```

**Minimal Format (4 columns only):**
```csv
Hotel California,EAGLES,en,EAGLES.jpg
Bohemian Rhapsody,QUEEN,en,QUEEN.jpg
```

**Mixed Format (some with genre/playlist, some without):**
```csv
1973,JAMES BLUNT,en,JAMESBLUNT.jpg,0,0,Pop,Romantic
Hotel California,EAGLES,en,EAGLES.jpg,0,0
Perfect,ED SHEERAN,en,EDSHEERAN.jpg,0,0,,Wedding Songs
```

---

## Field Requirements

### Title
- **Required**: Yes
- **Format**: Any text
- **Example**: `Hotel California`, `1973`, `A MODO TUO`

### Author
- **Required**: Yes
- **Format**: Artist or band name
- **Example**: `EAGLES`, `JAMES BLUNT`, `ELISA / LIGABUE`

### Language
- **Required**: Yes
- **Format**: Two-letter language code
- **Supported**: `en` (English), `it` (Italian), `es` (Spanish), `de` (German), `fr` (French)
- **Example**: `en`, `it`

### Image
- **Required**: No (can be empty string)
- **Format**: Filename with extension (just the filename, not full path)
- **Example**: `EAGLES.jpg`, `PHILCOLLINS.jpg`
- **Location**: Images are stored in `/static/tenants/<your-slug>/author_images/`
- **Note**: You can upload images manually or use "Bulk Fetch from Spotify" in admin panel

### Requests
- **Required**: No
- **Format**: Integer number
- **Default**: 0
- **Example**: `0`, `5`, `10`

### Popularity
- **Required**: No
- **Format**: Integer number
- **Default**: 0
- **Example**: `0`, `50`, `100`

### Genre
- **Required**: No
- **Format**: Text string
- **Default**: Empty string
- **Example**: `Pop`, `Rock`, `Jazz`, `Classical`, `Hip Hop`
- **Note**: Used for filtering songs by music genre

### Playlist
- **Required**: No
- **Format**: Text string  
- **Default**: Empty string
- **Example**: `Wedding Songs`, `Romantic Ballads`, `Party Hits`, `Slow Dance`
- **Note**: Used for organizing songs into custom playlists
- **Tip**: You can use the same playlist name across multiple songs to group them

---

## Upload Process

### How to Upload

1. **Prepare Your CSV File**
   - Follow the format above
   - Save as `.csv` file
   - Ensure proper encoding (UTF-8)

2. **Access Tenant Admin Panel**
   - Log in to your tenant admin: `/<your-slug>/admin`
   - Scroll to "Upload Song Library" card

3. **Upload File**
   - Click "Choose CSV File"
   - Select your CSV file
   - Click "Upload CSV" button

4. **Review Results**
   - Success message shows number of songs added
   - Error messages show any problematic rows
   - Songs are immediately available in your database

---

## Important Notes

### ✅ Best Practices
- **No Header Row**: CSV should NOT have a header row with column names
- **Encoding**: Use UTF-8 encoding for special characters
- **Commas**: If song titles contain commas, wrap in quotes: `"Hello, Goodbye",BEATLES,en,BEATLES.jpg`
- **Quotes**: If song titles contain quotes, escape them: `"He said ""Hello""",ARTIST,en,ARTIST.jpg`

### ⚠️ Common Issues

**Empty Rows**: Automatically skipped

**Missing Columns**: Rows with less than 4 columns are skipped with error message

**Special Characters**: Ensure your CSV is UTF-8 encoded

**Duplicate Songs**: The upload does NOT check for duplicates - each row is added

### 🔒 Security
- Only logged-in tenant admins can upload CSV files
- Uploads are tenant-specific (songs are isolated per tenant)
- File must have `.csv` extension

---

## Multi-Tenant Behavior

Each tenant has their own isolated song database:
- **Sergio's CSV** → Only visible to Sergio's customers
- **Laura's CSV** → Only visible to Laura's customers
- No cross-tenant data sharing

---

## Error Handling

The upload process provides detailed feedback:

### Success Example
```
✅ CSV upload complete! Added 150 song(s).
```

### Partial Success Example
```
✅ CSV upload complete! Added 145 song(s). Skipped 5 row(s). 
Errors: Row 12: Missing required fields; Row 34: Not enough columns...
```

### Complete Failure Example
```
❌ Error processing CSV file: [specific error message]
```

---

## Sample CSV File

A sample CSV file (`songs.csv`) is included in the project root with 1000+ songs for reference.

To use it:
1. Download `songs.csv`
2. Optionally edit to customize for your needs
3. Upload via the admin panel

---

## Converting from Excel

If you have your song list in Excel:

1. **In Excel**: File → Save As
2. **Format**: Choose "CSV UTF-8 (Comma delimited) (.csv)"
3. **Save** and upload to Musium

---

## Genre and Playlist Support ✅

**NEW**: The CSV format now supports `genre` and `playlist` columns (columns 7 and 8)!

- **Genre**: Automatically populated if you use the Spotify API fetch, or you can include it in your CSV
- **Playlist**: Custom organization field for grouping songs (e.g., "Wedding Songs", "Party Hits")
- **Both Optional**: You can leave these columns empty or omit them entirely

---

## Questions?

For issues or questions about CSV uploads, check the app logs or contact support.

