#!/bin/bash
# Quick setup script for PythonAnywhere deployment

echo "🚀 Setly - PythonAnywhere Setup Script"
echo "======================================="
echo ""

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Are you in the project directory?"
    exit 1
fi

echo "✅ Found app.py"
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated!"
    echo "Run: workon setly-env"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

echo "🌍 Compiling translations..."
pybabel compile -d translations

if [ $? -ne 0 ]; then
    echo "❌ Failed to compile translations"
    exit 1
fi

echo "✅ Translations compiled"
echo ""

echo "🗄️  Initializing database..."
python3 << 'EOF'
try:
    from app import init_db
    init_db()
    print("✅ Database initialized")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")
    exit(1)
EOF

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Go to PythonAnywhere Web tab"
echo "2. Click 'Reload' button"
echo "3. Visit your app at: https://vittorioviarengo.pythonanywhere.com"
echo ""
echo "To create a super admin:"
echo "python3 create_superadmin.py"
echo ""

