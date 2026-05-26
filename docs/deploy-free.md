# Free Hosting Deploy

Recommended split:

- Frontend: Vercel Hobby, project root `web/`.
- API: Render Free web service, Docker runtime using `Dockerfile.api`.
- Database: Neon Free Postgres.
- Auth: Firebase Auth only.

This keeps the Vite app on a static CDN and the FastAPI app on a normal
container host. On Render Free, Alembic runs at container startup because
Render pre-deploy commands are paid-only.

## 1. Create Neon Postgres

Create a Neon project and copy the pooled connection string. The API expects
SQLAlchemy's async driver, so convert the scheme:

```text
postgresql://user:password@host/db?sslmode=require
```

to:

```text
postgresql+asyncpg://user:password@host/db?ssl=require
```

Use this as `DATABASE_URL` on Render.

## 2. Deploy API on Render

1. Push this repo to GitHub.
2. In Render, create a new Blueprint from the repo. It will read `render.yaml`.
3. Set the secret env vars Render asks for:
   - `DATABASE_URL`
   - `GEMINI_API_KEY`
   - `FIREBASE_CREDENTIALS_JSON` (base64-encoded service account JSON)
   - `CORS_ORIGINS`
   - `WEB_BASE_URL`
   - `BOT_USERNAME`
4. For the first deploy, set placeholder frontend values:
   - `CORS_ORIGINS=https://your-vercel-app.vercel.app`
   - `WEB_BASE_URL=https://your-vercel-app.vercel.app`
5. After deploy, confirm:

```bash
curl https://your-render-api.onrender.com/api/v1/health
```

Expected response:

```json
{"status":"ok","version":"0.1.0"}
```

## 3. Deploy Frontend on Vercel

Create a Vercel project from the same GitHub repo:

- Root Directory: `web`
- Framework Preset: Vite
- Build Command: `npm run build`
- Output Directory: `dist`

Set env vars:

```text
VITE_API_URL=https://your-render-api.onrender.com
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
```

The `web/vercel.json` rewrite sends deep links like `/practice/writing` back
to `index.html`, so React Router can handle them.

## 4. Finalize API Origins

After Vercel gives you the final URL, update Render:

```text
CORS_ORIGINS=https://your-vercel-app.vercel.app
WEB_BASE_URL=https://your-vercel-app.vercel.app
```

Redeploy the Render service.

## Notes

- Render Free services can sleep when idle, so the first API request after a
  quiet period may be slow.
- Render Free does not support pre-deploy commands. `Dockerfile.api` runs
  `alembic upgrade head`, seeds `vocabulary_master` if it is empty, then starts
  Uvicorn.
- The Telegram bot is not deployed by this setup. Keep it on the existing VPS
  or add a separate paid/background worker later.
- Do not commit real Firebase service account JSON. Encode it locally and paste
  the result into `FIREBASE_CREDENTIALS_JSON` in Render's environment settings:

```bash
base64 -i firebase_credentials.json | tr -d '\n'
```
