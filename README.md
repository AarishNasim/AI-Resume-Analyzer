# AI Resume Analyzer & Job Recommendation System

Ready-to-run B.Tech CSE minor project using Python Flask + JavaScript + HTML/CSS + SQLite + NLP/ML.

## Features
- Registration/login/logout with hashed passwords and sessions
- PDF/DOCX resume upload
- Resume text extraction
- Skill extraction
- TF-IDF + cosine similarity
- Skill-based + NLP job matching
- Job recommendation dashboard
- Save job functionality
- SQLite database (no MySQL setup required)

## Run
1. Install Python 3.10+.
2. Open this folder in VS Code.
3. Create environment: `python -m venv .venv`
4. Activate it (Windows): `.venv\\Scripts\\activate`
5. Install packages: `pip install -r requirements.txt`
6. Run: `python app.py`
7. Open: `http://127.0.0.1:5000`

The SQLite database is created automatically on first run and sample jobs are inserted automatically.

## Railway deployment

This repository is a Flask application deployed from the repository root. Railway uses the root-level `Procfile` and starts `app:app` with Gunicorn. Set `APP_ENV=production`, a strong `SECRET_KEY`, and `FRONTEND_URL` to the exact browser origin that is allowed to call the backend. Railway provides `PORT` automatically.

SQLite and uploaded files use the local filesystem by default. For production persistence, attach a Railway Volume and set `DATABASE_PATH` and `UPLOADS_DIR` to paths on that volume, or migrate the existing database layer to a managed database/object store.

There is currently no React/Vite frontend in this repository. The UI is Flask/Jinja with static JavaScript and CSS, so there is no Vercel project, `VITE_API_URL`, `package.json`, or frontend root directory to configure from this repository.

## Project flow
Register -> Login -> Dashboard -> Upload PDF/DOCX -> Extract text -> Extract skills -> TF-IDF/cosine similarity + skill matching -> Match percentage -> Job recommendations -> Save job.

## Important
This is a complete working academic/demo version. For production deployment, replace the development secret key, add CSRF protection, stronger validation, persistent production database, logging, and secure file storage.
