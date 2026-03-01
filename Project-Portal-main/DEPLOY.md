# Deploy Guide (Render + Vercel)

## Required Environment Variables

- `DATABASE_URL` (PostgreSQL connection string)
- `ADMIN_PASSWORD` (strong password)
- `GOOGLE_CREDENTIALS_JSON` (full service-account JSON as one line)

Optional:
- `SERVICE_ACCOUNT_FILE` (defaults to `credentials.json`)
- `FLASK_DEBUG` (`false` in production)

## Render

1. Create Web Service from this repository.
2. Set Root Directory to `Project-Portal-main` (if your repo has the extra outer folder).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Add environment variables listed above.
6. After first deploy, run one-time DB init command:
   - `python init_db.py`

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
