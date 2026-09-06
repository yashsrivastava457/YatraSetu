# YatraSetu - Vercel Deployment

## 1. Environment Variables
Add these in Vercel Project Settings -> Environment Variables:

- DATABASE_URL
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

Do NOT upload backend/.env or expose the service-role key in frontend files.

## 2. Build
No frontend build command is required. Vercel serves the HTML/CSS/JS files and runs FastAPI from api/index.py.

## 3. Routes
- `/` -> home.html
- `/login.html`
- `/super-admin.html`
- `/temple-setup.html`
- `/zone-setup.html`
- `/index.html?temple_id=...`
- `/api/*` -> FastAPI

## 4. Database
DATABASE_URL must point to the production PostgreSQL database (Supabase Postgres is suitable).

## 5. Deploy
Push this folder to GitHub, import the repository in Vercel, add the environment variables, and Deploy.
