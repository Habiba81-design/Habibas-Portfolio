# Portfolio — Flask backend

A real backend for the portfolio site: SQLite-backed content (projects, skills,
experience, achievements), a working contact form, a password-protected admin
dashboard to edit everything without touching code, and a simple visit counter.

Tested end-to-end locally with Flask's test client before shipping — every
route (homepage render, contact submission, admin login/CRUD, analytics) was
exercised and confirmed working.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Visit `http://127.0.0.1:5000`. Admin dashboard: `http://127.0.0.1:5000/admin`
— default password is `changeme`. **Set your own before deploying anywhere
public:**

```bash
export ADMIN_PASSWORD=your-real-password
export SECRET_KEY=some-random-string
python app.py
```

## What's real here

- **Content (projects/skills/experience/achievements)** lives in a SQLite
  database (`portfolio.db`), seeded with the same placeholder content as
  before on first run. Edit it live from `/admin` — no redeploy needed.
- **Contact form** (`POST /contact`) saves every message to the database.
  View them at `/admin/messages`.
- **Email notifications** on new messages are optional — set these env vars
  to enable sending via SMTP (e.g. Gmail app password, SendGrid, etc.):
  ```bash
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=you@gmail.com
  SMTP_PASS=your-app-password
  CONTACT_TO_EMAIL=you@gmail.com
  ```
  Without these set, messages are still saved — you just check them in
  `/admin/messages` instead of getting an email ping.
- **Visit counter** increments once per homepage load, shown in the hero
  facts panel, the footer, and broken down by day under `/admin/analytics`.

## Deploy on Render (Web Service)

1. Push this folder to a GitHub repo.
2. Render → **New → Web Service** → connect the repo.
3. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
4. Environment variables (Render → Environment tab):
   - `ADMIN_PASSWORD` — required, don't leave it as `changeme`
   - `SECRET_KEY` — any random string
   - `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `CONTACT_TO_EMAIL` — optional, for email notifications
5. Deploy.

### Important limitation: SQLite + Render's free tier

Render's free Web Service filesystem is **ephemeral** — it resets on every
redeploy and can reset on restarts too. That means `portfolio.db` (and
everything in it: your edited content, contact messages, visit history) can
disappear when Render redeploys the service.

This is fine for a demo, but for anything you actually rely on:
- Attach a persistent disk (available on Render's paid instance tiers), or
- Swap SQLite for a managed database (e.g. Render's Postgres offering) —
  would need `db.py` rewritten to use `psycopg2`/`sqlalchemy` instead of
  the stdlib `sqlite3` calls it uses now. Ask if you want that version built.

## Project structure

```
app.py                     Flask routes (public + admin)
db.py                       sqlite3 data layer, schema, seed data
templates/
  index.html                 public portfolio page
  admin_login.html            admin password gate
  admin_base.html              shared admin layout
  admin.html                    admin dashboard overview
  admin_projects.html            projects CRUD
  admin_skills.html               skills CRUD
  admin_experience.html            experience CRUD
  admin_achievements.html           achievements CRUD
  admin_messages.html                contact message inbox
  admin_analytics.html                visit stats
```
