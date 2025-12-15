from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import os
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "crimespot"

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store"
    return response

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    path = os.path.join(os.path.dirname(__file__), "database.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  
    return conn

@app.route("/")
def dashboard():
    conn = get_db_connection()
    cities = [row["city"] for row in conn.execute(
        "SELECT DISTINCT city FROM reports WHERE status='verified' ORDER BY city ASC"
    ).fetchall()]
    conn.close()
    cities.insert(0, "India")  
    return render_template("dashboard.html", cities=cities)

@app.route("/city_stats/<city>")
def city_stats(city):
    conn = get_db_connection()

    if city.lower() == "india":
        total_crimes = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE status='verified'"
        ).fetchone()[0]
        last24_time = datetime.now() - timedelta(hours=24)
        last24_crimes = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE status='verified' AND date >= ?",
            (last24_time.strftime("%Y-%m-%d %H:%M:%S"),)
        ).fetchone()[0]
        breakdown_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM reports WHERE status='verified' GROUP BY type"
        ).fetchall()
        max_crimes = 500
    else:
        total_crimes = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE LOWER(city) = LOWER(?) AND status='verified'",
            (city,)
        ).fetchone()[0]
        last24_time = datetime.now() - timedelta(hours=24)
        last24_crimes = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE LOWER(city) = LOWER(?) AND status='verified' AND date >= ?",
            (city, last24_time.strftime("%Y-%m-%d %H:%M:%S"))
        ).fetchone()[0]
        breakdown_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM reports WHERE LOWER(city) = LOWER(?) AND status='verified' GROUP BY type",
            (city,)
        ).fetchall()
        max_crimes = 50

    breakdown = {row["type"]: row["cnt"] for row in breakdown_rows}
    conn.close()

    safety_score = max(0, 10 - (total_crimes / max_crimes * 10))
    safety_score = round(safety_score, 1)

    return jsonify({
        "total": total_crimes,
        "last24": last24_crimes,
        "safety": safety_score,
        "breakdown": breakdown
    })

@app.route('/recent_crimes/<city>')
def recent_crimes(city):
    conn = get_db_connection()
    if city.lower() == "india":
        rows = conn.execute(
            "SELECT type, description, date FROM reports WHERE status='verified' ORDER BY date DESC LIMIT 3"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT type, description, date FROM reports WHERE LOWER(city)=LOWER(?) AND status='verified' ORDER BY date DESC LIMIT 3",
            (city,)
        ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route("/report", methods=["GET", "POST"])
def report_page():
    if request.method == "POST":
        category = request.form.get("category")
        description = request.form.get("description")
        lat = request.form.get("latitude")
        lng = request.form.get("longitude")
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        city = request.form.get("city")

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO reports (type, description, lat, lng, city, date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (category, description, lat, lng, city, date, "pending")
            )
            conn.commit()
            flash("Report submitted successfully!", "success_report")
        except Exception as e:
            print("DB Error:", e)
            flash("Error saving report!", "error_report")
        conn.close()
        return redirect(url_for("report_page"))

    return render_template("report.html")

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if admin:
            session["admin_logged_in"] = True
            session["admin_username"] = admin["username"]
            session["admin_city"] = admin["city"]
            session["admin_role"] = admin["role"]
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid username or password", "login_error")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route("/admin_dashboard")
@admin_required
def admin_dashboard():
    conn = get_db_connection()

    if session.get("admin_role") == "super_admin":
        reports = conn.execute("SELECT * FROM reports ORDER BY date DESC").fetchall()
        total_reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        verified_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='verified'").fetchone()[0]
        pending_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='pending'").fetchone()[0]
        rejected_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='rejected'").fetchone()[0]
    else:
        reports = conn.execute(
            "SELECT * FROM reports WHERE LOWER(city) = LOWER(?) ORDER BY date DESC",
            (session["admin_city"],)
        ).fetchall()
        total_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE LOWER(city) = LOWER(?)", (session["admin_city"],)).fetchone()[0]
        verified_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='verified' AND LOWER(city) = LOWER(?)", (session["admin_city"],)).fetchone()[0]
        pending_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='pending' AND LOWER(city) = LOWER(?)", (session["admin_city"],)).fetchone()[0]
        rejected_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='rejected' AND LOWER(city) = LOWER(?)", (session["admin_city"],)).fetchone()[0]
    
    conn.close()

    return render_template(
        "admin_dashboard.html",
        reports=reports,
        total_reports=total_reports,
        verified_reports=verified_reports,
        pending_reports=pending_reports,
        rejected_reports=rejected_reports
    )

@app.route("/admin_logout")
def admin_logout():
    session.clear()
    # flash("Logged out successfully", "info")
    return redirect(url_for("dashboard"))

@app.route("/verify/<int:report_id>", methods=["POST"])
def verify_report(report_id):
    conn = get_db_connection()

    if session.get("admin_role") == "super_admin":
        report = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    else:
        report = conn.execute(
            "SELECT * FROM reports WHERE id=? AND LOWER(city) = LOWER(?)",
            (report_id, session["admin_city"])
        ).fetchone()

    if report:
        conn.execute("UPDATE reports SET status = 'verified' WHERE id = ?", (report_id,))
        conn.commit()

    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/reject/<int:report_id>", methods=["POST"])
def reject_report(report_id):
    conn = get_db_connection()

    if session.get("admin_role") == "super_admin":
        report = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    else:
        report = conn.execute(
            "SELECT * FROM reports WHERE id=? AND LOWER(city) = LOWER(?)",
            (report_id, session["admin_city"])
        ).fetchone()

    if report:
        conn.execute("UPDATE reports SET status = 'rejected' WHERE id = ?", (report_id,))
        conn.commit()

    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/get_verified_reports")
def get_verified_reports():
    conn = get_db_connection()
    reports = conn.execute("SELECT * FROM reports WHERE status='verified'").fetchall()
    conn.close()
    return [
        {
            "lat": r["lat"],
            "lng": r["lng"],
            "type": r["type"],
            "description": r["description"],
            "date": r["date"]
        }
        for r in reports
    ]

@app.route("/map")
def map_page():
    return render_template("map.html")

@app.route("/awareness")
def awareness():
    return render_template("awareness.html")

if __name__ == "__main__":
    conn = sqlite3.connect("database.db")
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.close()
    app.run(debug=True)

