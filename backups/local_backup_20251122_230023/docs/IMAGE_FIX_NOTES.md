# Image Filename Standardization Fix

## Problem

Images were not displaying in the Song Database UI due to filename mismatches between the database and filesystem.

### Root Causes:

1. **Case Sensitivity Differences:**
   - **macOS**: Case-insensitive file system (default) - `MADONNA.jpg` and `madonna.jpg` are the same file
   - **Linux**: Case-sensitive file system - `MADONNA.jpg` and `madonna.jpg` are DIFFERENT files
   - **Windows**: Case-insensitive (like macOS)

2. **Inconsistent Filenames:**
   - Database had entries like: `JAMES_BLUNT.jpg`, `madonna.jpg`, `DeBARGE.jpg`
   - Actual files were: `JAMESBLUNT.jpg`, `madonna.jpg`, `DeBARGE.jpg`
   - On macOS, some worked by chance; on Linux deployment, they would fail

## Solution

Standardized ALL image filenames to use:
- **UPPERCASE** filename (before extension)
- **lowercase** extension (`.jpg`, `.jpeg`, `.png`, etc.)

**Example**: `JAMESBLUNT.jpg`, `MARIAHCAREY.jpg`, `JOHNMILES.jpg`

## What Was Fixed

### Files Renamed: 28 images
- `madonna.jpg` → `MADONNA.jpg`
- `MICHAELJACKSONPAULMcCARTNEY.jpg` → `MICHAELJACKSONPAULMCCARTNEY.jpg`
- `DeBARGE.jpg` → `DEBARGE.jpg`
- And 25 more...

### Database Records Updated: 30 songs
- Updated references to match the new standardized filenames
- Now database and filesystem are perfectly aligned

## Benefits

1. ✅ **Works on all operating systems** (macOS, Linux, Windows)
2. ✅ **No broken images** when deploying to Linux servers
3. ✅ **Consistent naming convention** across entire project
4. ✅ **Easier to maintain and debug**

## Maintenance Script

Use `standardize_image_case.py` for future image additions:

```bash
# Check what would change (dry run)
python3 standardize_image_case.py

# Apply changes
python3 standardize_image_case.py --apply
```

## Deployment Checklist

When deploying to a new server (especially Linux):

1. ✅ Ensure all image filenames follow the standard: `ARTISTNAME.jpg`
2. ✅ Run `standardize_image_case.py` to verify consistency
3. ✅ Test image loading in the UI before going live
4. ✅ Check browser console for 404 errors on image files

## Notes

- Always use UPPERCASE for artist names in filenames
- Keep file extensions lowercase (`.jpg`, not `.JPG`)
- Avoid spaces in filenames (use underscores if needed)
- Test on a Linux system before production deployment

---

**Date Fixed**: October 18, 2025
**Scripts Used**: `standardize_image_case.py`

