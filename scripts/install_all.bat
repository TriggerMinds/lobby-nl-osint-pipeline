@echo off
echo === Lobby NL OSINT Pipeline - Windows installatie ===
python --version
pip install -r requirements.txt
playwright install chromium
python -m spacy download nl_core_news_sm
python scripts/install_check.py
echo === Installatie klaar ===
pause
