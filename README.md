# AI Resume Analyzer 📄🤖

An end-to-end AI-powered web application that evaluates resumes, highlights key strengths, identifies missing skills, and provides actionable recommendations to improve ATS compatibility and recruiter readability.

🔗 **Live Demo:** [ai-resume-analyzer-production-533f.up.railway.app](https://ai-resume-analyzer-production-533f.up.railway.app)[cite: 2]

---

## 🚀 Features

* **Resume Parsing & Evaluation:** Extracts and structures data from uploaded resumes (PDF/DOCX).
* **ATS Compatibility & Score:** Analyzes formatting, keyword placement, and structure to generate an ATS score.
* **Skill Gap Analysis:** Highlights missing industry-relevant technical and soft skills.
* **Actionable Feedback:** Provides specific recommendations on phrasing, impact metrics, and readability.
* **Production-Ready Deployment:** Containerized and served with Gunicorn for stable cloud hosting.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, Gunicorn
* **Frontend:** HTML5, CSS3, JavaScript
* **NLP & Processing:** PyPDF2 / pdfplumber, NLTK, Scikit-learn
* **Deployment & Hosting:** Railway, Git

---

## 📂 Project Structure

AI-Resume-Analyzer/
├── static/
├── templates/
├── app.py
├── requirements.txt
├── Procfile
└── README.md

---

## ⚙️ Local Setup & Installation

1. Clone the repository:
git clone https://github.com/syedaarish/AI-Resume-Analyzer.git
cd AI-Resume-Analyzer

2. Create and activate a virtual environment:
python -m venv .venv
.venv\Scripts\activate

3. Install dependencies:
pip install -r requirements.txt

4. Run the application:
python app.py

---

## ☁️ Deployment

The project is configured for deployment on Railway using Gunicorn:

gunicorn app:app --bind 0.0.0.0:$PORT

---

## 👨‍💻 Author

**Aarish Nasim**
* Email: syedaarish00786@gmail.com
* GitHub: https://github.com/syedaarish

---

## 📜 License

This project is licensed under the MIT License.
