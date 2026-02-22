#!/bin/bash
# Post-Deployment Smoke Test Script
# Run this after Railway deployment to verify everything works
#
# Usage:
#   ./smoke_test.sh                    # Run all tests
#   ./smoke_test.sh --quick            # Run quick tests only
#   ./smoke_test.sh --admin-only       # Test admin pages only

echo "🔥 AyendeCX Post-Deployment Smoke Tests 🔥"
echo "=========================================="
echo ""

# Run Django smoke tests
python manage.py smoke_test "$@"

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Deployment verification successful!"
    echo "🚀 System is ready for production use"
else
    echo ""
    echo "❌ Deployment verification failed!"
    echo "⚠️  Do not use in production - fix errors first"
fi

exit $EXIT_CODE
