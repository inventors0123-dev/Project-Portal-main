import importlib.util
from pathlib import Path


INNER_APP_PATH = Path(__file__).parent / "Project-Portal-main" / "app.py"
spec = importlib.util.spec_from_file_location("project_portal_inner_app", INNER_APP_PATH)

if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load app module from {INNER_APP_PATH}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Expose Flask app for gunicorn: `gunicorn app:app`
app = module.app
init_db = getattr(module, "init_db", None)
Project = getattr(module, "Project", None)
ProjectAccess = getattr(module, "ProjectAccess", None)
