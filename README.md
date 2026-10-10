# EDUNEXIA Learning Platform — Flask + SQLite + Render

Responsive LMS starter for mobile, tablet and laptop, built with Flask, SQLite and Bootstrap 5.

## Included
- Admin creates, edits, activates/deactivates and deletes student, instructor and administrator accounts; students cannot self-register. Admin can change usernames and passwords. The currently logged-in admin and last active admin are protected from accidental lockout.
- Admin creates, edits and deletes courses, chooses one of five course themes, assigns instructors, adds video/PDF lessons and exam questions.
- **Admin assigns courses to individual students.** Students see only their assigned courses.
- Student lesson progress, multiple-choice exam marking, 70% pass mark, downloadable PDF certificate.
- Instructors see only courses assigned to them.
- Passwords hashed with Werkzeug; role checks enforced on server routes.
- Protected file routes check account role and course assignment.
- Responsive Bootstrap layout.
- Render deployment files: `render.yaml`, `Procfile`, `requirements.txt`, `.gitignore`.

## Run locally
Python 3.10+ recommended.

Windows:
```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`.

## Initial administrator
- Username: `admin`
- Initial password: `admin123` (unless `INITIAL_ADMIN_PASSWORD` is set when the database is first created).

**Important:** `admin123` is a requested starter password and is not suitable for long-term use. Log in and change it immediately. The Render configuration also seeds `INITIAL_ADMIN_PASSWORD=admin123` on first database creation. If the database already exists, changing this environment variable does not reset the existing admin password; update it from Admin → Users → Edit.

## GitHub and Render deployment
1. Create a new private GitHub repository.
2. Extract this ZIP, then upload/commit the project files to the repository. Do not commit `.env`, `edunexia.db`, or private user uploads.
3. In Render, create a **Web Service** and connect the GitHub repository. Render can detect `render.yaml`; otherwise use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
4. Add environment variables:
   - `SECRET_KEY`: long random secret
   - `INITIAL_ADMIN_PASSWORD`: strong initial admin password, set before first database creation
5. Deploy and log in as `admin`. Log in with username `admin` and password `admin123` on a fresh database, then change the password immediately. Create accounts, create courses and choose a theme, add lessons and exam questions, then use **Assign courses** to assign courses to students.

## IMPORTANT: database and uploaded-file persistence on Render
SQLite and local uploads are suitable for local testing or a single-instance demo. On Render, the filesystem of a normal web service is ephemeral; deployments/restarts can erase local SQLite data and uploaded files. For a real production deployment:
- Attach a persistent disk and store the SQLite database and uploads on that disk, or preferably
- Use a managed PostgreSQL database and private object storage for uploaded PDFs/videos.
- Do not scale multiple web instances while using a local SQLite database.
- Configure backups and restore testing.

## Content protection limitations
Students cannot create/edit/delete course content, cannot manage other students, and have no download/share links for lessons. Materials are served through authenticated routes and PDF/video browser download controls are hidden or discouraged. **No web application can completely prevent copying** by authorised viewers (screenshots, screen recording, browser tools, or external cameras). For stronger protection use private video hosting with DRM/signed URLs and watermarking. PDF rendering in a browser is not an absolute copy-prevention system.

## Before public launch
Add CSRF protection, rate limiting, password reset, audit logs, malware scanning for uploads, file size/content validation, monitoring, and a proper production data store. `app.py` is configured to avoid Flask debug mode when run under Gunicorn.
