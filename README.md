# SIWES Management & Logbook System

A Flask web app for managing SIWES (Students Industrial Work Experience
Scheme) logbooks. Students submit weekly activity logs, supervisors review
and comment on them, and an admin manages accounts and monitors progress.

## Features

**Student**
- Register / login
- Add placement (company) details
- Submit weekly log entries (activities, skills learned, attendance)
- Edit / delete their own entries
- View entry status (pending / reviewed) and supervisor comments
- Printable view of a single log entry

**Supervisor**
- Login (account created by admin)
- View list of assigned students
- View each student's full logbook
- Add comments and mark entries as reviewed

**Admin**
- Login (default account created automatically — see below)
- View overall stats (students, total entries, reviewed count)
- Create supervisor accounts
- Assign a supervisor to each student
- Delete student records

## Setup

1. Install Python 3.9+ if you don't already have it.
2. Open a terminal in this folder and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   python app.py
   ```

4. Open your browser to `http://127.0.0.1:5000`

A SQLite database file (`siwes.db`) is created automatically the first time
you run the app, along with a default admin account:

```
email:    admin@siwes.com
password: admin123
```

**Change this password (or edit `create_default_admin()` in `app.py`)
before using this anywhere beyond your own machine.**

## Typical workflow

1. Log in as admin (`admin@siwes.com` / `admin123`).
2. Create a supervisor account under "Add Supervisor".
3. Have students register themselves at `/register`.
4. As admin, assign each student to a supervisor.
5. Students log in and start submitting weekly entries.
6. Supervisors log in, open a student, and review/comment on entries.

## Project structure

```
siwes_system/
├── app.py                  # all routes, models, and app setup
├── requirements.txt
├── siwes.db                 # created automatically on first run
├── static/
│   └── css/style.css
└── templates/
    ├── base.html            # shared layout + navbar
    ├── index.html            # landing page
    ├── login.html / register.html
    ├── student_dashboard.html
    ├── edit_placement.html
    ├── log_entry_form.html   # add/edit a log entry
    ├── log_view.html         # printable single entry
    ├── supervisor_dashboard.html
    ├── student_logs_for_supervisor.html
    ├── review_log.html
    ├── admin_dashboard.html
    ├── new_supervisor.html
    ├── assign_supervisor.html
    └── error.html
```

## Notes for extending it

- All accounts live in a single `User` table distinguished by a `role`
  column (`student` / `supervisor` / `admin`) — simpler than separate
  tables, since students, supervisors, and admins share a login system.
- Log entries are re-set to `pending` whenever a student edits them, so a
  supervisor's earlier approval doesn't silently apply to changed content.
- To add file uploads (e.g. a final SIWES report), you'd add a `filepath`
  column to `LogEntry` and use Flask's `request.files` with `app.config["UPLOAD_FOLDER"]`.
- To export reports, `pandas` + `LogEntry.query.all()` can generate a CSV,
  or `reportlab`/`weasyprint` can generate PDFs from the `log_view.html` template.
