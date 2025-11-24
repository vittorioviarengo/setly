# Multilingual Development Guide

## Overview
This application supports multiple languages (English, Italian, Spanish, French, German). All user-facing strings MUST be multilingual.

## Rules for Adding New Features

### 1. **Always Use Flask-Babel `_()` Function**
Never hardcode strings in templates or Python code. Always use the translation function:

**✅ CORRECT:**
```python
flash(_('User created successfully'), 'success')
```

**❌ WRONG:**
```python
flash('User created successfully', 'success')
```

### 2. **JavaScript Strings in Templates**
When you need translations in JavaScript, pass them from Flask using `tojson`:

**✅ CORRECT:**
```javascript
const translations = {
    confirmMessage: {{ _('Are you sure?') | tojson }},
    errorMessage: {{ _('An error occurred') | tojson }}
};

showConfirm(translations.confirmMessage);
```

**❌ WRONG:**
```javascript
showConfirm('Are you sure?');  // Hardcoded English!
```

### 3. **Adding New Translations**

When adding a new string that needs translation:

1. **Add the string with `_()` in your code:**
   ```python
   flash(_('New feature message'), 'info')
   ```

2. **Extract translations:**
   ```bash
   pybabel extract -F babel.cfg -k _l -o messages.pot .
   pybabel update -i messages.pot -d translations -l en -l it -l es -l fr -l de
   ```

3. **Translate in each `.po` file:**
   - `translations/en/LC_MESSAGES/messages.po`
   - `translations/it/LC_MESSAGES/messages.po`
   - `translations/es/LC_MESSAGES/messages.po`
   - `translations/fr/LC_MESSAGES/messages.po`
   - `translations/de/LC_MESSAGES/messages.po`

4. **Compile translations:**
   ```bash
   pybabel compile -d translations
   ```

### 4. **Common Patterns**

#### Dialog Boxes
```javascript
// In template
showConfirm(
    {{ _('Are you sure you want to delete this?') | tojson }},
    () => { /* confirm action */ }
);
```

#### Error Messages
```javascript
// In template
const translations = {
    errorMsg: {{ _('An error occurred') | tojson }}
};
showError(translations.errorMsg);
```

#### Success Messages
```python
# In Python
return jsonify({'message': _('Operation successful')})
```

### 5. **Checklist for New Features**

Before committing code with new strings:

- [ ] All user-facing strings use `_()` function
- [ ] JavaScript strings are passed via `tojson` from Flask
- [ ] Translations added to all 5 language files (en, it, es, fr, de)
- [ ] Translations compiled with `pybabel compile -d translations`
- [ ] Tested in at least 2 different languages

### 6. **Testing Multilingual Features**

1. Change language in the app
2. Test all new strings appear in the selected language
3. Verify no hardcoded English strings remain
4. Check browser console for any untranslated strings

### 7. **Common Mistakes to Avoid**

❌ **Don't:**
- Hardcode English strings
- Use `alert()` or `confirm()` with hardcoded strings
- Forget to add translations to all language files
- Use string concatenation with translations (use format strings instead)

✅ **Do:**
- Always use `_()` for user-facing strings
- Pass translations to JavaScript via `tojson`
- Add translations to all 5 language files
- Test in multiple languages before committing

## Examples from Codebase

### Good Example: `templates/queue.html`
```javascript
const translations = {
    failedToStartGig: {{ _('Failed to start gig') | tojson }},
    errorStartingGig: {{ _('Error starting gig') | tojson }}
};

showError(translations.failedToStartGig);
```

### Good Example: `app.py`
```python
flash(_('No active gig. Please wait for the musician to start the gig.'), 'info')
```

## Questions?

If you're unsure whether a string needs translation, ask yourself:
- Will the end user see this?
- Is this a button, label, message, or error text?
- If yes to any → **IT MUST BE TRANSLATED**

