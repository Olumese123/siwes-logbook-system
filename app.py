"""
SIWES Management & Logbook System
----------------------------------
A Flask web app for managing SIWES (Students Industrial Work Experience
Scheme) logbooks: students submit weekly activity logs, supervisors review
and comment on them, and admins manage students/supervisors and view
overall records.

Run with:
    pip install -r requirements.txt
    python app.py

Default admin login (created automatically on first run):
    email:    admin@siwes.com
    password: admin123
(Change this immediately after first login in a real deployment.)
"""

from datetime import date, datetime
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# App & extensions setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///siwes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    """A single table holds all account types, distinguished by `role`."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student / supervisor / admin

    # Student-only fields
    matric_no = db.Column(db.String(50))
    department = db.Column(db.String(120))
    level = db.Column(db.String(20))
    phone = db.Column(db.String(30))

    # Placement info (student-only)
    company_name = db.Column(db.String(150))
    company_address = db.Column(db.String(250))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)

    supervisor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    supervisor = db.relationship(
        "User", remote_side=[id], backref="assigned_students"
    )

    log_entries = db.relationship(
        "LogEntry", backref="student", cascade="all, delete-orphan",
        foreign_keys="LogEntry.student_id"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    week_number = db.Column(db.Integer, nullable=False)
    entry_date = db.Column(db.Date, nullable=False, default=date.today)
    activities = db.Column(db.Text, nullable=False)
    skills_learned = db.Column(db.Text)

    attended = db.Column(db.Boolean, default=True)  # attendance for that week

    status = db.Column(db.String(20), default="pending")  # pending / reviewed
    supervisor_comment = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Access-control decorators
# ---------------------------------------------------------------------------

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        matric_no = request.form.get("matric_no", "").strip()
        department = request.form.get("department", "").strip()
        level = request.form.get("level", "").strip()
        phone = request.form.get("phone", "").strip()

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))

        student = User(
            name=name, email=email, role="student",
            matric_no=matric_no, department=department,
            level=level, phone=phone,
        )
        student.set_password(password)
        db.session.add(student)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            if user.role == "student":
                return redirect(url_for("student_dashboard"))
            elif user.role == "supervisor":
                return redirect(url_for("supervisor_dashboard"))
            else:
                return redirect(url_for("admin_dashboard"))
        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------

@app.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    entries = (LogEntry.query
               .filter_by(student_id=current_user.id)
               .order_by(LogEntry.week_number.desc())
               .all())
    return render_template("student_dashboard.html", entries=entries)


@app.route("/student/placement", methods=["GET", "POST"])
@login_required
@role_required("student")
def edit_placement():
    if request.method == "POST":
        current_user.company_name = request.form.get("company_name", "").strip()
        current_user.company_address = request.form.get("company_address", "").strip()
        start = request.form.get("start_date")
        end = request.form.get("end_date")
        current_user.start_date = datetime.strptime(start, "%Y-%m-%d").date() if start else None
        current_user.end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else None
        db.session.commit()
        flash("Placement details updated.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("edit_placement.html")


@app.route("/student/log/new", methods=["GET", "POST"])
@login_required
@role_required("student")
def new_log_entry():
    if request.method == "POST":
        entry = LogEntry(
            student_id=current_user.id,
            week_number=int(request.form["week_number"]),
            entry_date=datetime.strptime(request.form["entry_date"], "%Y-%m-%d").date(),
            activities=request.form["activities"].strip(),
            skills_learned=request.form.get("skills_learned", "").strip(),
            attended=bool(request.form.get("attended")),
        )
        db.session.add(entry)
        db.session.commit()
        flash("Log entry submitted.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("log_entry_form.html", entry=None)


@app.route("/student/log/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("student")
def edit_log_entry(entry_id):
    entry = LogEntry.query.get_or_404(entry_id)
    if entry.student_id != current_user.id:
        abort(403)

    if request.method == "POST":
        entry.week_number = int(request.form["week_number"])
        entry.entry_date = datetime.strptime(request.form["entry_date"], "%Y-%m-%d").date()
        entry.activities = request.form["activities"].strip()
        entry.skills_learned = request.form.get("skills_learned", "").strip()
        entry.attended = bool(request.form.get("attended"))
        entry.status = "pending"  # re-open for review after edit
        db.session.commit()
        flash("Log entry updated.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("log_entry_form.html", entry=entry)


@app.route("/student/log/<int:entry_id>/delete", methods=["POST"])
@login_required
@role_required("student")
def delete_log_entry(entry_id):
    entry = LogEntry.query.get_or_404(entry_id)
    if entry.student_id != current_user.id:
        abort(403)
    db.session.delete(entry)
    db.session.commit()
    flash("Log entry deleted.", "info")
    return redirect(url_for("student_dashboard"))


@app.route("/log/<int:entry_id>/view")
@login_required
def view_log_entry(entry_id):
    """Printable single-entry view. Accessible to the owning student,
    their supervisor, or any admin."""
    entry = LogEntry.query.get_or_404(entry_id)
    student = entry.student
    if not (current_user.id == student.id
            or current_user.id == student.supervisor_id
            or current_user.role == "admin"):
        abort(403)
    return render_template("log_view.html", entry=entry, student=student)


# ---------------------------------------------------------------------------
# Supervisor routes
# ---------------------------------------------------------------------------

@app.route("/supervisor/dashboard")
@login_required
@role_required("supervisor")
def supervisor_dashboard():
    students = User.query.filter_by(role="student", supervisor_id=current_user.id).all()
    pending_count = (LogEntry.query
                      .join(User, LogEntry.student_id == User.id)
                      .filter(User.supervisor_id == current_user.id,
                              LogEntry.status == "pending")
                      .count())
    return render_template("supervisor_dashboard.html", students=students, pending_count=pending_count)


@app.route("/supervisor/student/<int:student_id>")
@login_required
@role_required("supervisor")
def view_student_logs(student_id):
    student = User.query.get_or_404(student_id)
    if student.supervisor_id != current_user.id:
        abort(403)
    entries = (LogEntry.query
               .filter_by(student_id=student.id)
               .order_by(LogEntry.week_number.desc())
               .all())
    return render_template("student_logs_for_supervisor.html", student=student, entries=entries)


@app.route("/supervisor/log/<int:entry_id>/review", methods=["GET", "POST"])
@login_required
@role_required("supervisor")
def review_log_entry(entry_id):
    entry = LogEntry.query.get_or_404(entry_id)
    if entry.student.supervisor_id != current_user.id:
        abort(403)

    if request.method == "POST":
        entry.supervisor_comment = request.form.get("comment", "").strip()
        entry.status = "reviewed"
        db.session.commit()
        flash("Comment saved and entry marked reviewed.", "success")
        return redirect(url_for("view_student_logs", student_id=entry.student_id))

    return render_template("review_log.html", entry=entry)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    students = User.query.filter_by(role="student").all()
    supervisors = User.query.filter_by(role="supervisor").all()

    total_students = len(students)
    total_entries = LogEntry.query.count()
    reviewed_entries = LogEntry.query.filter_by(status="reviewed").count()

    return render_template(
        "admin_dashboard.html",
        students=students, supervisors=supervisors,
        total_students=total_students, total_entries=total_entries,
        reviewed_entries=reviewed_entries,
    )


@app.route("/admin/supervisors/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def new_supervisor():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("new_supervisor"))

        supervisor = User(name=name, email=email, role="supervisor")
        supervisor.set_password(password)
        db.session.add(supervisor)
        db.session.commit()
        flash("Supervisor account created.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("new_supervisor.html")


@app.route("/admin/student/<int:student_id>/assign", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assign_supervisor(student_id):
    student = User.query.get_or_404(student_id)
    supervisors = User.query.filter_by(role="supervisor").all()

    if request.method == "POST":
        sup_id = request.form.get("supervisor_id")
        student.supervisor_id = int(sup_id) if sup_id else None
        db.session.commit()
        flash(f"Supervisor updated for {student.name}.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("assign_supervisor.html", student=student, supervisors=supervisors)


@app.route("/admin/student/<int:student_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_student(student_id):
    student = User.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Student record deleted.", "info")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You don't have permission to view this page."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


# ---------------------------------------------------------------------------
# Startup: create tables + a default admin account
# ---------------------------------------------------------------------------

def create_default_admin():
    if not User.query.filter_by(role="admin").first():
        admin = User(name="System Admin", email="admin@siwes.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Default admin created -> email: admin@siwes.com | password: admin123")


with app.app_context():
    db.create_all()
    create_default_admin()


if __name__ == "__main__":
    app.run(debug=True)
