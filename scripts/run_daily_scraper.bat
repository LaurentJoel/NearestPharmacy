@echo off
REM ============================================
REM Daily Pharmacy Scraper - Runs at 8:00 AM
REM ============================================

REM Log start time
echo [%date% %time%] Starting daily pharmacy scraper... >> "%~dp0logs\scraper.log"

REM Change to project directory
cd /d "c:\Users\laure\Desktop\NearestPharmacy"

REM Run the scraper
python scripts\quick_scraper.py >> "%~dp0logs\scraper.log" 2>&1

REM Log completion
echo [%date% %time%] Scraper completed. >> "%~dp0logs\scraper.log"
echo. >> "%~dp0logs\scraper.log"
