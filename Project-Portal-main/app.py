import json
import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from googleapiclient.discovery import build
from google.oauth2 import service_account

app = Flask(__name__)
os.makedirs(app.instance_path, exist_ok=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- SECURE CONFIGURATION ---
# This pulls the database link from platform Environment Variables.
# Local fallback uses SQLite so the app can still boot without DATABASE_URL.
database_url = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(app.instance_path, 'database.db')}",
)

# Fix for Render/Neon PostgreSQL protocol naming compatibility
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Always set this in production environments.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")

db = SQLAlchemy(app)

# --- DATABASE MODEL ---
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    drive_id = db.Column(db.String(100), nullable=False)
    assigned_user = db.Column(db.String(500))

# --- GOOGLE DRIVE CONNECTION ---
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

def get_drive_service():
    # Prefer secret manager env var in production. File path remains as local fallback.
    if GOOGLE_CREDENTIALS_JSON:
        creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE if os.path.isabs(SERVICE_ACCOUNT_FILE) else os.path.join(BASE_DIR, SERVICE_ACCOUNT_FILE),
            scopes=SCOPES
        )
    return build('drive', 'v3', credentials=creds)

def init_db():
    with app.app_context():
        db.create_all()

# --- ROUTES ---
@app.route('/')
def index():
    # Shows the list of all active projects (Jalgaon tenders, etc.)
    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@app.route('/create_page')
def create_page():
    return render_template('create.html')

@app.route('/healthz')
def healthz():
    return {"status": "ok"}, 200

@app.route('/create', methods=['POST'])
def create_project():
    project_name = request.form.get('name')
    raw_emails = request.form.get('email')
    form_pass = request.form.get('admin_pass')

    # Security check: User must enter SECURE_2026 to proceed
    if form_pass != ADMIN_PASSWORD:
        return "Unauthorized: Incorrect Admin Password", 403

    user_emails = [email.strip() for email in raw_emails.split(',') if email.strip()]
    
    try:
        service = get_drive_service()
        
        # 1. Create Folder in Google Drive (Inside PORTAL_ROOT)
        file_metadata = {
            'name': project_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': ['1-jjxSjs8W1IaUfXjenmDeK9qHEySMb9O'] 
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        
        # 2. Grant Access Permissions to Team Emails
        for email in user_emails:
            service.permissions().create(
                fileId=folder_id, 
                sendNotificationEmail=True, 
                body={'type': 'user', 'role': 'writer', 'emailAddress': email}
            ).execute()
        
        # 3. Save Project Details to Neon Database permanently
        new_project = Project(name=project_name, drive_id=folder_id, assigned_user=", ".join(user_emails))
        db.session.add(new_project)
        db.session.commit()
        
        return redirect(url_for('index'))
    except Exception as e:
        return f"Error: {e}"

@app.route('/delete/<int:id>')
def delete_project(id):
    # Removes the project from the dashboard list
    project_to_delete = Project.query.get_or_404(id)
    db.session.delete(project_to_delete)
    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    # Creates tables on first local run.
    init_db()
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
