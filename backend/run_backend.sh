#/bin/sh sh

uv run --env-file .env uvicorn app.main:app --reload
