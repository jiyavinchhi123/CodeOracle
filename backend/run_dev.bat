@echo off
REM Dev server — only watches app/ to avoid reloads when uploads are extracted
uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
