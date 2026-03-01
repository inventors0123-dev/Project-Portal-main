# Deploy Guide (Render + Vercel)

## Required Environment Variables

- `DATABASE_URL` (PostgreSQL connection string)
- `ADMIN_PASSWORD` (strong password)
- `GOOGLE_CREDENTIALS_JSON` (full service-account JSON as one line)
- `DRIVE_PARENT_FOLDER_ID` (Google Drive folder ID where new project folders are created)

Optional:
- `SERVICE_ACCOUNT_FILE` (defaults to `credentials.json`)
- `SEND_PERMISSION_EMAIL` (`true` or `false`)
- `FLASK_DEBUG` (`false` in production)

## Render

1. Create Web Service from this repository.
2. Set Root Directory to `Project-Portal-main` (if your repo has the extra outer folder).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python init_db.py && gunicorn app:app`
5. Add environment variables listed above.
6. DB initialization is automatic on each deploy (no Render Shell required).

## Vercel

1. Import this repository in Vercel.
2. Set Root Directory to `Project-Portal-main` (if needed).
3. Keep `vercel.json` in place.
4. Add environment variables listed above.
5. Deploy.

## Security Notes

- Do not commit real `credentials.json` to git.
- Rotate Google service account key if it was already exposed.
- Keep `.gitignore` tracked so local secrets are excluded.
