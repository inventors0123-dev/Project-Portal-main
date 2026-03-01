import json
import os
import re

from flask import Flask, redirect, render_template, request, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy.orm import joinedload

app = Flask(__name__)
os.makedirs(app.instance_path, exist_ok=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CONFIGURATION ---
database_url = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(app.instance_path, 'database.db')}",
)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
DRIVE_PARENT_FOLDER_ID = os.getenv("DRIVE_PARENT_FOLDER_ID", "").strip()
SEND_PERMISSION_EMAIL = (
    os.getenv("SEND_PERMISSION_EMAIL", "true").strip().lower() == "true"
)

SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

db = SQLAlchemy(app)


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    drive_id = db.Column(db.String(100), nullable=False)
    assigned_user = db.Column(db.String(500))
    access_list = db.relationship(
        "ProjectAccess",
        backref="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def user_emails(self):
        if self.access_list:
            return [row.user_email for row in self.access_list]
        if self.assigned_user:
            return [email.strip() for email in self.assigned_user.split(",") if email.strip()]
        return []


class ProjectAccess(db.Model):
    __tablename__ = "project_access"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    user_email = db.Column(db.String(320), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="writer")

    __table_args__ = (db.UniqueConstraint("project_id", "user_email", name="uq_project_user"),)


def sync_legacy_access_rows():
    projects = Project.query.options(joinedload(Project.access_list)).all()
    changed = False

    for project in projects:
        if project.access_list:
            continue
        seen = set()
        legacy_emails = [
            email.strip().lower()
            for email in (project.assigned_user or "").split(",")
            if email.strip()
        ]
        for email in legacy_emails:
            if email in seen:
                continue
            seen.add(email)
            if not EMAIL_RE.match(email):
                continue
            db.session.add(
                ProjectAccess(project_id=project.id, user_email=email, role="writer")
            )
            changed = True

    if changed:
        db.session.commit()


def init_db():
    with app.app_context():
        db.create_all()
        sync_legacy_access_rows()


def get_drive_service():
    if GOOGLE_CREDENTIALS_JSON:
        creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
    else:
        credentials_path = (
            SERVICE_ACCOUNT_FILE
            if os.path.isabs(SERVICE_ACCOUNT_FILE)
            else os.path.join(BASE_DIR, SERVICE_ACCOUNT_FILE)
        )
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    return build("drive", "v3", credentials=creds)


def parse_emails(raw_emails):
    tokens = raw_emails.replace("\n", ",").split(",") if raw_emails else []
    seen = set()
    valid = []
    invalid = []

    for token in tokens:
        email = token.strip().lower()
        if not email:
            continue
        if email in seen:
            continue
        seen.add(email)
        if EMAIL_RE.match(email):
            valid.append(email)
        else:
            invalid.append(email)

    return valid, invalid


@app.route("/")
def index():
    projects = (
        Project.query.options(joinedload(Project.access_list))
        .order_by(Project.id.desc())
        .all()
    )
    return render_template("index.html", projects=projects)


@app.route("/create_page")
def create_page():
    return redirect(url_for("index") + "#new-project")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.svg",
        mimetype="image/svg+xml",
    )


@app.route("/create", methods=["POST"])
def create_project():
    project_name = (request.form.get("name") or "").strip()
    raw_emails = request.form.get("email") or ""
    form_pass = request.form.get("admin_pass") or ""

    if form_pass != ADMIN_PASSWORD:
        return "Unauthorized: Incorrect Admin Password", 403
    if not project_name:
        return "Project name is required.", 400
    if len(project_name) > 100:
        return "Project name must be 100 characters or less.", 400
    if not DRIVE_PARENT_FOLDER_ID:
        return "Server configuration error: set DRIVE_PARENT_FOLDER_ID.", 500

    user_emails, invalid_emails = parse_emails(raw_emails)
    if invalid_emails:
        return f"Invalid emails: {', '.join(invalid_emails)}", 400
    if not user_emails:
        return "At least one valid email is required.", 400

    existing = Project.query.filter(db.func.lower(Project.name) == project_name.lower()).first()
    if existing:
        return "Project with this name already exists.", 409

    service = None
    folder_id = None
    try:
        service = get_drive_service()

        folder = service.files().create(
            body={
                "name": project_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [DRIVE_PARENT_FOLDER_ID],
            },
            fields="id",
        ).execute()
        folder_id = folder.get("id")

        for email in user_emails:
            service.permissions().create(
                fileId=folder_id,
                sendNotificationEmail=SEND_PERMISSION_EMAIL,
                body={"type": "user", "role": "writer", "emailAddress": email},
            ).execute()

        new_project = Project(
            name=project_name,
            drive_id=folder_id,
            assigned_user=", ".join(user_emails),
        )
        db.session.add(new_project)
        db.session.flush()

        for email in user_emails:
            db.session.add(
                ProjectAccess(project_id=new_project.id, user_email=email, role="writer")
            )

        db.session.commit()
        return redirect(url_for("index"))
    except Exception:
        db.session.rollback()
        app.logger.exception("Project creation failed")

        # Best effort rollback for partially created folder
        if service and folder_id:
            try:
                service.files().delete(fileId=folder_id).execute()
            except Exception:
                app.logger.exception("Folder cleanup failed for folder_id=%s", folder_id)

        return "Could not create project. Check email IDs, Drive permissions, and credentials.", 500


@app.route("/delete/<int:id>", methods=["POST"])
def delete_project(id):
    form_pass = request.form.get("admin_pass") or ""
    if form_pass != ADMIN_PASSWORD:
        return "Unauthorized: Incorrect Admin Password", 403

    project_to_delete = Project.query.get_or_404(id)
    db.session.delete(project_to_delete)
    db.session.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
