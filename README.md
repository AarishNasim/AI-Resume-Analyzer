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

## Project flow
Register -> Login -> Dashboard -> Upload PDF/DOCX -> Extract text -> Extract skills -> TF-IDF/cosine similarity + skill matching -> Match percentage -> Job recommendations -> Save job.

## Important
This is a complete working academic/demo version. For production deployment, replace the development secret key, add CSRF protection, stronger validation, persistent production database, logging, and secure file storage.
