import os
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, date
from functools import wraps

from flask import (
    Flask, request, render_template, redirect, url_for, session, flash, jsonify
)

import db as dblayer

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.teardown_appcontext(dblayer.close_db)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def send_email_notification(name, email, message):
    """Best-effort email notification for a new contact message.
    No-ops silently if SMTP isn't configured — the message is always saved
    to the database regardless, so nothing is lost either way."""
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    pw = os.environ.get("SMTP_PASS")
    to_addr = os.environ.get("CONTACT_TO_EMAIL")
    if not all([host, user, pw, to_addr]):
        return False, "SMTP not configured — message saved to database only."

    port = int(os.environ.get("SMTP_PORT", 587))
    try:
        msg = MIMEText(f"From: {name} <{email}>\n\n{message}")
        msg["Subject"] = f"Portfolio contact form: {name}"
        msg["From"] = user
        msg["To"] = to_addr
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, pw)
            server.sendmail(user, [to_addr], msg.as_string())
        return True, "Email sent."
    except Exception as e:
        return False, f"Email send failed: {e}"


def fetch_portfolio_data():
    db = dblayer.get_db()

    projects = [dict(row) for row in db.execute(
        "SELECT * FROM projects ORDER BY sort_order, id"
    )]
    for p in projects:
        p["tags"] = [t.strip() for t in p["tags"].split(",") if t.strip()]

    categories = [dict(row) for row in db.execute(
        "SELECT * FROM skill_categories ORDER BY sort_order, id"
    )]
    skills_by_cat = {}
    for cat in categories:
        rows = db.execute(
            "SELECT * FROM skills WHERE category_id=? ORDER BY sort_order, id", (cat["id"],)
        )
        skills_by_cat[cat["name"]] = [dict(r) for r in rows]

    experience = [dict(row) for row in db.execute(
        "SELECT * FROM experience ORDER BY sort_order, id"
    )]
    for e in experience:
        e["bullets"] = [b.strip() for b in e["bullets"].split("\n") if b.strip()]

    achievements = [dict(row) for row in db.execute(
        "SELECT * FROM achievements ORDER BY sort_order, id"
    )]

    return {
        "projects": projects,
        "skills": skills_by_cat,
        "experience": experience,
        "achievements": achievements,
    }


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    total_visits = dblayer.record_visit()
    data = fetch_portfolio_data()
    return render_template("index.html", data_json=json.dumps(data), total_visits=total_visits)


@app.route("/contact", methods=["POST"])
def contact():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    message = (request.form.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"ok": False, "error": "All fields are required."}), 400

    db = dblayer.get_db()
    db.execute(
        "INSERT INTO messages (name, email, message, created_at) VALUES (?,?,?,?)",
        (name, email, message, datetime.utcnow().isoformat()),
    )
    db.commit()

    sent, note = send_email_notification(name, email, message)
    return jsonify({"ok": True, "email_sent": sent, "note": note})


# ---------------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Incorrect password.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    db = dblayer.get_db()
    unread = db.execute("SELECT COUNT(*) FROM messages WHERE is_read=0").fetchone()[0]
    total_messages = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_visits = db.execute("SELECT COALESCE(SUM(count),0) FROM daily_visits").fetchone()[0]
    today_visits = db.execute(
        "SELECT count FROM daily_visits WHERE day=?", (date.today().isoformat(),)
    ).fetchone()
    today_visits = today_visits[0] if today_visits else 0
    project_count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    return render_template(
        "admin.html",
        unread=unread, total_messages=total_messages,
        total_visits=total_visits, today_visits=today_visits,
        project_count=project_count,
    )


@app.route("/admin/projects", methods=["GET", "POST"])
@admin_required
def admin_projects():
    db = dblayer.get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO projects (title, category, metric, description, tags, github_url, demo_url, sort_order) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                request.form["title"], request.form["category"], request.form.get("metric", ""),
                request.form.get("description", ""), request.form.get("tags", ""),
                request.form.get("github_url", "#"), request.form.get("demo_url", "#"),
                int(request.form.get("sort_order") or 0),
            ),
        )
        db.commit()
        flash("Project added.")
        return redirect(url_for("admin_projects"))

    projects = db.execute("SELECT * FROM projects ORDER BY sort_order, id").fetchall()
    return render_template("admin_projects.html", projects=projects)


@app.route("/admin/projects/<int:project_id>/delete", methods=["POST"])
@admin_required
def admin_delete_project(project_id):
    db = dblayer.get_db()
    db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    db.commit()
    flash("Project deleted.")
    return redirect(url_for("admin_projects"))


@app.route("/admin/skills", methods=["GET", "POST"])
@admin_required
def admin_skills():
    db = dblayer.get_db()
    if request.method == "POST":
        cat_name = request.form["category_name"].strip()
        cat = db.execute("SELECT id FROM skill_categories WHERE name=?", (cat_name,)).fetchone()
        if cat:
            cat_id = cat["id"]
        else:
            cur = db.execute(
                "INSERT INTO skill_categories (name, sort_order) VALUES (?, 99)", (cat_name,)
            )
            cat_id = cur.lastrowid
        db.execute(
            "INSERT INTO skills (category_id, name, level, sort_order) VALUES (?,?,?,0)",
            (cat_id, request.form["skill_name"], int(request.form.get("level") or 50)),
        )
        db.commit()
        flash("Skill added.")
        return redirect(url_for("admin_skills"))

    categories = db.execute("SELECT * FROM skill_categories ORDER BY sort_order, id").fetchall()
    skills_by_cat = {}
    for cat in categories:
        skills_by_cat[cat["name"]] = db.execute(
            "SELECT * FROM skills WHERE category_id=? ORDER BY sort_order, id", (cat["id"],)
        ).fetchall()
    return render_template("admin_skills.html", skills_by_cat=skills_by_cat)


@app.route("/admin/skills/<int:skill_id>/delete", methods=["POST"])
@admin_required
def admin_delete_skill(skill_id):
    db = dblayer.get_db()
    db.execute("DELETE FROM skills WHERE id=?", (skill_id,))
    db.commit()
    flash("Skill deleted.")
    return redirect(url_for("admin_skills"))


@app.route("/admin/experience", methods=["GET", "POST"])
@admin_required
def admin_experience():
    db = dblayer.get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO experience (role, org, date_range, bullets, sort_order) VALUES (?,?,?,?,?)",
            (
                request.form["role"], request.form.get("org", ""), request.form.get("date_range", ""),
                request.form.get("bullets", ""), int(request.form.get("sort_order") or 0),
            ),
        )
        db.commit()
        flash("Experience entry added.")
        return redirect(url_for("admin_experience"))

    entries = db.execute("SELECT * FROM experience ORDER BY sort_order, id").fetchall()
    return render_template("admin_experience.html", entries=entries)


@app.route("/admin/experience/<int:entry_id>/delete", methods=["POST"])
@admin_required
def admin_delete_experience(entry_id):
    db = dblayer.get_db()
    db.execute("DELETE FROM experience WHERE id=?", (entry_id,))
    db.commit()
    flash("Experience entry deleted.")
    return redirect(url_for("admin_experience"))


@app.route("/admin/achievements", methods=["GET", "POST"])
@admin_required
def admin_achievements():
    db = dblayer.get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO achievements (icon, title, description, date_label, sort_order) VALUES (?,?,?,?,?)",
            (
                request.form.get("icon", "🏆"), request.form["title"],
                request.form.get("description", ""), request.form.get("date_label", ""),
                int(request.form.get("sort_order") or 0),
            ),
        )
        db.commit()
        flash("Achievement added.")
        return redirect(url_for("admin_achievements"))

    entries = db.execute("SELECT * FROM achievements ORDER BY sort_order, id").fetchall()
    return render_template("admin_achievements.html", entries=entries)


@app.route("/admin/achievements/<int:entry_id>/delete", methods=["POST"])
@admin_required
def admin_delete_achievement(entry_id):
    db = dblayer.get_db()
    db.execute("DELETE FROM achievements WHERE id=?", (entry_id,))
    db.commit()
    flash("Achievement deleted.")
    return redirect(url_for("admin_achievements"))


@app.route("/admin/messages")
@admin_required
def admin_messages():
    db = dblayer.get_db()
    db.execute("UPDATE messages SET is_read=1 WHERE is_read=0")
    db.commit()
    messages = db.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
    return render_template("admin_messages.html", messages=messages)


@app.route("/admin/messages/<int:msg_id>/delete", methods=["POST"])
@admin_required
def admin_delete_message(msg_id):
    db = dblayer.get_db()
    db.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    db.commit()
    flash("Message deleted.")
    return redirect(url_for("admin_messages"))


@app.route("/admin/analytics")
@admin_required
def admin_analytics():
    db = dblayer.get_db()
    since = (date.today() - timedelta(days=13)).isoformat()
    rows = db.execute(
        "SELECT day, count FROM daily_visits WHERE day >= ? ORDER BY day", (since,)
    ).fetchall()
    by_day = {r["day"]: r["count"] for r in rows}
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    series = [{"day": d, "count": by_day.get(d, 0)} for d in days]
    total = db.execute("SELECT COALESCE(SUM(count),0) FROM daily_visits").fetchone()[0]
    return render_template("admin_analytics.html", series=series, total=total)


# ---------------------------------------------------------------------------
dblayer.init_db(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
