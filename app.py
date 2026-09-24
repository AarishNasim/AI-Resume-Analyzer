import os, sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from services.resume_parser import extract_text
from services.skill_extractor import extract_skills
from services.matcher import match_jobs

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'resume_analyzer.db')
UPLOADS = os.path.join(BASE, 'uploads')
os.makedirs(UPLOADS, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-this-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED = {'pdf', 'docx'}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS resumes(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, resume_text TEXT, skills TEXT, score REAL, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, company TEXT NOT NULL, description TEXT NOT NULL, required_skills TEXT NOT NULL, location TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, job_id INTEGER, match_percentage REAL, status TEXT DEFAULT 'Saved', applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    if con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0:
        jobs = [
        ('Python Developer','TechNova','Build Flask APIs and backend services.','Python, Flask, SQL, REST API, Git','Noida / Remote'),
        ('Data Analyst','DataBridge','Analyze business data and create reports.','Python, SQL, Pandas, Excel, Statistics','Delhi'),
        ('ML Intern','AI Labs','Work on machine learning and NLP experiments.','Python, Machine Learning, Pandas, Scikit-learn, NLP','Jaipur / Remote'),
        ('Frontend Developer','WebCraft','Create responsive web interfaces.','HTML, CSS, JavaScript, React, Git','Hyderabad'),
        ('Full Stack Developer','CodeWorks','Develop frontend and backend features.','Python, JavaScript, Flask, HTML, CSS, SQL','Noida')]
        con.executemany('INSERT INTO jobs(title,company,description,required_skills,location) VALUES(?,?,?,?,?)', jobs)
    con.commit(); con.close()

@app.route('/')
def home(): return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not name or not email or len(password)<6: flash('Name, email and password (6+ characters) are required.','error'); return render_template('register.html')
        try:
            con=db(); con.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(name,email,generate_password_hash(password))); con.commit(); con.close()
            flash('Registration successful. Please login.','success'); return redirect(url_for('login'))
        except sqlite3.IntegrityError: flash('Email already registered.','error')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        con=db(); user=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); con.close()
        if user and check_password_hash(user['password'],password):
            session['user_id']=user['id']; session['name']=user['name']; return redirect(url_for('dashboard'))
        flash('Invalid email or password.','error')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    con=db(); resume=con.execute('SELECT * FROM resumes WHERE user_id=? ORDER BY id DESC LIMIT 1',(session['user_id'],)).fetchone(); jobs=con.execute('SELECT * FROM jobs').fetchall(); con.close()
    results=match_jobs(resume['resume_text'], jobs) if resume else []
    return render_template('dashboard.html', name=session['name'], resume=resume, results=results)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session: return redirect(url_for('login'))
    file=request.files.get('resume')
    if not file or not file.filename: flash('Please choose a PDF or DOCX resume.','error'); return redirect(url_for('dashboard'))
    ext=file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED: flash('Only PDF and DOCX files are allowed.','error'); return redirect(url_for('dashboard'))
    filename=secure_filename(file.filename); path=os.path.join(UPLOADS, filename); file.save(path)
    try: text=extract_text(path)
    except Exception as e: flash(f'Could not read resume: {e}','error'); return redirect(url_for('dashboard'))
    if not text.strip(): flash('No readable text found in the resume.','error'); return redirect(url_for('dashboard'))
    skills=extract_skills(text)
    con=db(); con.execute('DELETE FROM resumes WHERE user_id=?',(session['user_id'],)); con.execute('INSERT INTO resumes(user_id,filename,resume_text,skills) VALUES(?,?,?,?)',(session['user_id'],filename,text,', '.join(skills))); con.commit(); con.close()
    flash(f'Resume analyzed. Found {len(skills)} skills.','success'); return redirect(url_for('dashboard'))

@app.route('/save-job/<int:job_id>', methods=['POST'])
def save_job(job_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    con=db(); resume=con.execute('SELECT * FROM resumes WHERE user_id=? ORDER BY id DESC LIMIT 1',(session['user_id'],)).fetchone(); job=con.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if resume and job:
        score=next((x['score'] for x in match_jobs(resume['resume_text'],[job]) if x['id']==job_id),0)
        con.execute('INSERT INTO applications(user_id,job_id,match_percentage) VALUES(?,?,?)',(session['user_id'],job_id,score)); con.commit()
    con.close(); flash('Job saved.','success'); return redirect(url_for('dashboard'))

if __name__=='__main__':
    init_db(); app.run(debug=True)
else: init_db()
