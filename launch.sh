#!/bin/bash
# CleanEstimate - Production Launch Script
#
# Usage:
#   ./launch.sh              # Start on port 5051
#   ./launch.sh --port 8080  # Custom port
#   ./launch.sh --setup      # Run Stripe setup first

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PORT=5051
SETUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --port) PORT="$2"; shift 2 ;;
        --setup) SETUP=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Load .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Load .env.stripe if it exists
if [ -f .env.stripe ]; then
    export $(grep -v '^#' .env.stripe | xargs)
fi

# Required env vars with defaults
export SESSION_SECRET="${SESSION_SECRET:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///cleanestimate.db}"

if [ "$SETUP" = true ]; then
    echo ""
    echo "  Stripe Setup"
    echo "  Paste your Stripe Secret Key (sk_test_... or sk_live_...):"
    read -r STRIPE_KEY
    python3 stripe_setup.py "$STRIPE_KEY"
    echo ""
    echo "  Setup complete. Run ./launch.sh to start the app."
    exit 0
fi

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║      CleanEstimate - Drake's Precision    ║"
echo "  ║      Professional Cleaning Management     ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  Port:     $PORT"
echo "  Database: ${DATABASE_URL:0:50}"
echo "  Stripe:   $([ -n "$STRIPE_SECRET_KEY" ] && echo 'Configured' || echo 'Not configured (run --setup)')"
echo "  URL:      http://localhost:$PORT"
echo ""

# Initialize database
python3 -c "from app import app, db; app.app_context().__enter__(); db.create_all(); print('  Database ready.')"

# Populate task templates if empty
python3 -c "
from app import app, db
from models import Task
with app.app_context():
    if Task.query.count() == 0:
        print('  Populating task templates...')
        # Trigger the populate route logic inline
        from app import task_library
        for cleaning_type, tasks in task_library.items():
            for td in tasks:
                t = Task(
                    name=td['task'],
                    instructions=td['instructions'],
                    method=td['method'],
                    materials=td['materials'],
                    approved_products=td['approved_products'],
                    precautions=td['precautions'],
                    time_per_100_sqft=td['time_per_100'],
                    cleaning_type=cleaning_type,
                )
                db.session.add(t)
        db.session.commit()
        print(f'  Loaded {Task.query.count()} tasks.')
    else:
        print(f'  Tasks loaded ({Task.query.count()} templates).')
"

echo "  Starting server..."
echo ""

# Use gunicorn if available, else flask dev server
if command -v gunicorn &> /dev/null; then
    exec gunicorn --bind "0.0.0.0:$PORT" --workers 2 --timeout 120 "app:app"
else
    exec python3 -c "
from app import app
app.run(host='0.0.0.0', port=$PORT, debug=False)
"
fi
