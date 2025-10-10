@echo off
REM IAAI AuctionNow Monitor Runner Script for Windows

echo 🚀 Starting IAAI AuctionNow Monitor...

REM Change to script directory
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update requirements
echo 📥 Installing requirements...
pip install -r requirements.txt

REM Install playwright browsers if needed
echo 🎭 Installing Playwright browsers...
playwright install chromium

REM Run the IAAI monitor app
echo 🌐 Starting IAAI AuctionNow Monitor on http://localhost:5001
python iaai_app.py