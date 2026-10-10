# Edunexia Learning Platform — Flask Starter

## Included
- Admin login and dashboard
- Admin-only creation of student and instructor accounts; admin can deactivate accounts
- Admin course creation, instructor assignment, lesson upload, and exam question management
- Lessons can include protected PDF or video uploads plus text notes
- Student course enrolment, lesson completion tracking, multiple-choice exams
- Pass mark is 70%; certificate becomes available as a downloadable PDF after passing
- Instructor sees courses assigned by admin
- SQLite database and password hashing
- Bootstrap responsive interface

## Setup
Requires Python 3.10+.

### Windows
1. Extract the ZIP.
2. Open Command Prompt in the extracted folder.
3. Run:
   `py -m venv .venv`
   `.venv\Scripts\activate`
   `pip install -r requirements.txt`
   `python app.py`
4. Open `http://127.0.0.1:5000`.

### macOS / Linux
`python3 -m venv .venv`
`source .venv/bin/activate`
`pip install -r requirements.txt`
`python app.py`
Then open `http://127.0.0.1:5000`.

## First login
- Username: `admin`
- Password: `ChangeMe123!`

Change this password immediately. The initial admin is created only if the database does not already contain one. Delete `edunexia.db` to reset the demo database (this deletes all data).

## Content restrictions: important reality
The app does not show a normal download button for course PDFs or videos. Files are served through authenticated routes, and access is checked against the user's role/course enrolment. PDF/video controls and context menus are discouraged in the lesson page. However, **no web app can guarantee that content cannot be copied**: authorised viewers can use screenshots, screen recording, browser developer tools, or other capture methods. For stronger protection use a managed video streaming provider with signed URLs/DRM, watermarking, short-lived access tokens, and private object storage. A PDF shown in a browser may still be saved by the viewer.

## Production checklist
This is a runnable starter, not a fully hardened commercial LMS. Before public launch:
- Set a long random `SECRET_KEY` environment variable.
- Add CSRF protection, rate limiting, password reset, audit logs, email verification, backups, and security tests.
- Use HTTPS and a production WSGI server; turn off debug mode.
- Store uploads outside the public static directory, enforce upload limits, scan files, and configure cloud/private storage.
- For large videos, use streaming/CDN infrastructure instead of serving from Flask.
- The admin account is initially seeded with a known password. Change it before using real data.
