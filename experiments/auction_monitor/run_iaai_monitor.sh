#!/bin/bash

# IAAI AuctionNow Monitor Runner Script

echo "🚀 Starting IAAI AuctionNow Monitor..."

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Install playwright browsers if needed
echo "🎭 Installing Playwright browsers..."
playwright install chromium

# Run the IAAI monitor app
echo "🌐 Starting IAAI AuctionNow Monitor on http://localhost:5001"
python iaai_app.py