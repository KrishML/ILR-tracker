#!/bin/bash
# Start the ILR Tracker hybrid app
# Usage: ./start.sh [dev|prod]

MODE=${1:-prod}
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$MODE" = "dev" ]; then
    echo "🚀 Starting in DEVELOPMENT mode..."
    echo "   Backend: http://localhost:5001"
    echo "   Frontend: http://localhost:3000 (with hot reload)"
    echo ""

    # Start Flask backend in background
    cd "$DIR/backend" && python app.py &
    FLASK_PID=$!

    # Start Vite dev server
    cd "$DIR/frontend" && npm run dev

    # Cleanup on exit
    kill $FLASK_PID 2>/dev/null
else
    echo "🚀 Starting in PRODUCTION mode..."
    echo "   Building frontend..."
    cd "$DIR/frontend" && npm run build

    echo "   Starting server at http://localhost:5001"
    cd "$DIR/backend" && python app.py
fi
