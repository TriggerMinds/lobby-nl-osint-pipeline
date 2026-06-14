Write-Host "=== Lobby NL OSINT Pipeline - Windows installatie ===" -ForegroundColor Cyan
python --version
pip install -r requirements.txt
playwright install chromium
python -m spacy download nl_core_news_sm
python scripts/install_check.py
Write-Host "=== Installatie klaar ===" -ForegroundColor Green
