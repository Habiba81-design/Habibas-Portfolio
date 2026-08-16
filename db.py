"""
Thin SQLite data layer for the portfolio backend. No ORM — just sqlite3 from
the standard library, kept deliberately simple so it's easy to read and edit.
"""
import sqlite3
import os
from datetime import date

from flask import g

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "portfolio.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'ml',
    metric TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    github_url TEXT DEFAULT '#',
    demo_url TEXT DEFAULT '#',
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skill_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES skill_categories(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    level INTEGER DEFAULT 50,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    org TEXT DEFAULT '',
    date_range TEXT DEFAULT '',
    bullets TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    icon TEXT DEFAULT '🏆',
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    date_label TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_read INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_visits (
    day TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
);
"""

DEFAULT_PROJECTS = [
    ("Customer Churn Predictor", "ml", "0.91 AUC",
     "Gradient-boosted model predicting subscription churn 30 days out, deployed behind a Flask API with drift monitoring.",
     "XGBoost, MLflow, Docker", "#", "#", 0),
    ("Clinical Notes NLP Pipeline", "nlp", "F1 0.87",
     "Fine-tuned transformer for extracting structured entities from unstructured clinical notes, with an active-learning loop for labeling.",
     "Transformers, spaCy, Active Learning", "#", "#", 1),
    ("Satellite Flood Segmentation", "cv", "0.82 IoU",
     "U-Net segmentation model identifying flooded regions from Sentinel-2 imagery for disaster response teams.",
     "PyTorch, U-Net, Remote Sensing", "#", "#", 2),
    ("Demand Forecasting Engine", "ts", "-18% MAPE",
     "Hierarchical time-series forecasting system for retail demand planning, replacing a manual spreadsheet process.",
     "Prophet, LightGBM, Airflow", "#", "#", 3),
    ("Real-time Fraud Scoring", "ml", "<50ms p99",
     "Streaming feature pipeline + model serving layer for transaction fraud scoring at low latency.",
     "Kafka, FastAPI, Redis", "#", "#", 4),
    ("Research: Calibration in LLM Evals", "nlp", "workshop paper",
     "Studied confidence calibration failure modes in LLM-as-judge evaluation setups across five benchmark tasks.",
     "LLM Eval, Research, Python", "#", "#", 5),
]

DEFAULT_SKILLS = {
    "Languages & Core": [("Python", 92), ("SQL", 85), ("R", 55)],
    "ML / Deep Learning": [("PyTorch", 88), ("scikit-learn", 90), ("Transformers / HF", 78)],
    "Data Engineering": [("Pandas / Spark", 87), ("Airflow", 62), ("dbt", 50)],
    "MLOps & Tools": [("Docker", 70), ("MLflow / W&B", 75), ("Git / CI-CD", 80)],
}

DEFAULT_EXPERIENCE = [
    ("Data Scientist", "Company Name", "2024 — Present",
     "Led development of a churn-prediction model that reduced customer loss by 12%\n"
     "Built and maintained feature store serving 40+ production features\n"
     "Mentored 2 junior data scientists on experiment design", 0),
    ("ML Research Intern", "Lab / Company Name", "2023 — 2024",
     "Co-authored a workshop paper on evaluation calibration in language models\n"
     "Built reproducible benchmarking pipeline used by 3 research teams", 1),
    ("Data Analyst", "Earlier Company", "2021 — 2023",
     "Automated weekly reporting, saving ~6 analyst-hours per week\n"
     "Built the first version of the company's internal metrics dashboard", 2),
]

DEFAULT_ACHIEVEMENTS = [
    ("🏆", "Kaggle Competition — Top 3%", "Tabular playground series, 2400+ teams", "2025", 0),
    ("🥈", "University Hackathon — 2nd Place", "Built a flood early-warning prototype in 24h", "2024", 1),
    ("📄", "Workshop Paper Accepted", "LLM evaluation calibration, NeurIPS workshop", "2024", 2),
    ("🎖️", "Kaggle Expert", "Top 3% ranked, competitions category", "2023", 3),
    ("🚀", "Best ML Project Award", "Undergraduate capstone showcase", "2022", 4),
    ("📊", "Dean's List", "Top 5% of graduating cohort", "2021", 5),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = sqlite3.connect(DB_PATH)
        db.executescript(SCHEMA)
        db.commit()

        cur = db.execute("SELECT COUNT(*) FROM projects")
        if cur.fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO projects (title, category, metric, description, tags, github_url, demo_url, sort_order) "
                "VALUES (?,?,?,?,?,?,?,?)",
                DEFAULT_PROJECTS,
            )

        cur = db.execute("SELECT COUNT(*) FROM skill_categories")
        if cur.fetchone()[0] == 0:
            for i, (cat_name, skills) in enumerate(DEFAULT_SKILLS.items()):
                cur = db.execute(
                    "INSERT INTO skill_categories (name, sort_order) VALUES (?,?)", (cat_name, i)
                )
                cat_id = cur.lastrowid
                for j, (skill_name, level) in enumerate(skills):
                    db.execute(
                        "INSERT INTO skills (category_id, name, level, sort_order) VALUES (?,?,?,?)",
                        (cat_id, skill_name, level, j),
                    )

        cur = db.execute("SELECT COUNT(*) FROM experience")
        if cur.fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO experience (role, org, date_range, bullets, sort_order) VALUES (?,?,?,?,?)",
                DEFAULT_EXPERIENCE,
            )

        cur = db.execute("SELECT COUNT(*) FROM achievements")
        if cur.fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO achievements (icon, title, description, date_label, sort_order) VALUES (?,?,?,?,?)",
                DEFAULT_ACHIEVEMENTS,
            )

        db.commit()
        db.close()


def record_visit():
    db = get_db()
    today = date.today().isoformat()
    db.execute(
        "INSERT INTO daily_visits (day, count) VALUES (?, 1) "
        "ON CONFLICT(day) DO UPDATE SET count = count + 1",
        (today,),
    )
    db.commit()
    total = db.execute("SELECT COALESCE(SUM(count), 0) FROM daily_visits").fetchone()[0]
    return total
