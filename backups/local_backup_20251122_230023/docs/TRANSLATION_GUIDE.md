# Translation Management Guide

This application uses Flask-Babel for internationalization (i18n). Translations are managed manually via `.po` files.

## Supported Languages
- English (en) - Base language
- Italian (it)
- Spanish (es)
- German (de)
- French (fr)

## Adding New Translatable Text

### 1. In Python/Flask Templates
Wrap text with the `_()` function:

**Python:**
```python
from flask_babel import gettext as _
message = _('Welcome to the application')
```

**Jinja2 Templates:**
```html
<h1>{{ _('Welcome to the application') }}</h1>
<button>{{ _('Save') }}</button>
```

### 2. Update Translation Files
Edit the `.po` files for each language:

**File locations:**
- `translations/en/LC_MESSAGES/messages.po` (English)
- `translations/it/LC_MESSAGES/messages.po` (Italian)
- `translations/es/LC_MESSAGES/messages.po` (Spanish)
- `translations/de/LC_MESSAGES/messages.po` (German)
- `translations/fr/LC_MESSAGES/messages.po` (French)

**Format:**
```po
msgid "Save"
msgstr "Salva"  # Italian translation

msgid "Welcome to the application"
msgstr "Benvenuto nell'applicazione"
```

### 3. Compile Translations
After editing `.po` files, compile them to `.mo` files:

```bash
cd /path/to/Songs_2.0
pybabel compile -d translations
```

This generates the binary `.mo` files that Flask uses.

### 4. Reload Application
Restart your Flask application or reload the page to see the changes.

## Common Translation Examples

### Recently Added Translations
```po
# Genre
msgid "Genre"
msgstr "Genere"  # Italian

# Add Song
msgid "Add Song"
msgstr "Aggiungi Canzone"  # Italian

# Delete
msgid "Delete"
msgstr "Elimina"  # Italian

# Logout
msgid "Logout"
msgstr "Esci"  # Italian
```

## Translation Tips

1. **Keep strings short and clear** - Easier to translate accurately
2. **Use context** - Similar words may need different translations
3. **Test in UI** - Verify translations fit in the interface
4. **Be consistent** - Use the same translation for the same term
5. **Use placeholders** - For dynamic content: `_('Hello {name}').format(name=user_name)`

## Full Translation Workflow

### For New UI Elements:

1. **Identify text** - Find all user-visible text
2. **Wrap with `_()`** - Make it translatable
3. **Add to English** - Update `translations/en/LC_MESSAGES/messages.po`
4. **Translate to other languages** - Update it, es, de, fr `.po` files
5. **Compile** - Run `pybabel compile -d translations`
6. **Test** - Verify in each language

### Using Translation Tools (Optional):

**Online Tools:**
- DeepL (https://www.deepl.com/) - High quality translations
- Google Translate - Quick translations
- Context.reverso.net - See translations in context

**Remember:** Always review automated translations for accuracy!

## Troubleshooting

### Translations not showing:
1. Check `.po` file syntax
2. Ensure you compiled to `.mo` files
3. Verify language code matches (en, it, es, de, fr)
4. Restart Flask application

### Special characters not displaying:
Ensure charset is set in `.po` file metadata:
```po
"Content-Type: text/plain; charset=UTF-8\n"
```

### Missing translations showing msgid:
Add the translation to the appropriate `.po` file and recompile.

## File Structure
```
translations/
├── en/
│   └── LC_MESSAGES/
│       ├── messages.po  (Edit this)
│       └── messages.mo  (Generated)
├── it/
│   └── LC_MESSAGES/
│       ├── messages.po  (Edit this)
│       └── messages.mo  (Generated)
├── es/
│   └── LC_MESSAGES/
│       ├── messages.po  (Edit this)
│       └── messages.mo  (Generated)
├── de/
│   └── LC_MESSAGES/
│       ├── messages.po  (Edit this)
│       └── messages.mo  (Generated)
└── fr/
    └── LC_MESSAGES/
        ├── messages.po  (Edit this)
        └── messages.mo  (Generated)
```

## Quick Reference Commands

```bash
# Compile all translations
pybabel compile -d translations

# Extract new strings from code (if needed)
pybabel extract -F babel.cfg -o translations/messages.pot .

# Update existing .po files with new strings (if needed)
pybabel update -i translations/messages.pot -d translations
```

## Best Practices

- ✅ Always translate complete sentences, not fragments
- ✅ Maintain consistent terminology across the app
- ✅ Keep translations up-to-date with UI changes
- ✅ Test translations in actual interface
- ✅ Have native speakers review translations when possible
- ❌ Don't use machine translation without review
- ❌ Don't translate technical terms (OK, CSS, SQL, etc.)
- ❌ Don't forget to compile after editing `.po` files

