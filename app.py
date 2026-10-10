import os, sqlite3, secrets
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "edunexia.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "mp4", "webm", "mov", "m4v"}
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB; adjust for your hosting
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','instructor','student')),
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS courses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          instructor_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(instructor_id) REFERENCES users(id) ON DELETE SET NULL);
        CREATE TABLE IF NOT EXISTS lessons(
          id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, title TEXT NOT NULL,
          content TEXT NOT NULL DEFAULT '', file_name TEXT, file_type TEXT, position INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS enrollments(
          student_id INTEGER NOT NULL, course_id INTEGER NOT NULL, PRIMARY KEY(student_id,course_id),
          FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS exam_questions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, question TEXT NOT NULL,
          option_a TEXT NOT NULL, option_b TEXT NOT NULL, option_c TEXT NOT NULL, option_d TEXT NOT NULL,
          correct_option TEXT NOT NULL CHECK(correct_option IN ('a','b','c','d')),
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS exam_results(
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, course_id INTEGER NOT NULL,
          score INTEGER NOT NULL, total INTEGER NOT NULL, passed INTEGER NOT NULL, attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(student_id, course_id),
          FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS lesson_progress(
          student_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(student_id, lesson_id),
          FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
          FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE);
        """)
        admin = con.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if not admin:
            con.execute("INSERT INTO users(name,username,password_hash,role) VALUES(?,?,?,?)",
                        ("Platform Admin", "admin", generate_password_hash(os.environ.get("INITIAL_ADMIN_PASSWORD", "ChangeMe123!")), "admin"))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def current_user():
    if not session.get("user_id"): return None
    with db() as con:
        return con.execute("SELECT id,name,username,role,active FROM users WHERE id=?", (session["user_id"],)).fetchone()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def user_can_access_course(con, course_id):
    role = session.get("role")
    if role in ("admin", "instructor"):
        if role == "admin": return True
        row = con.execute("SELECT instructor_id FROM courses WHERE id=?", (course_id,)).fetchone()
        return bool(row and row["instructor_id"] == session["user_id"])
    return bool(con.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",
                            (session["user_id"], course_id)).fetchone())

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Content-Security-Policy"] = "default-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'self'"
    return response

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password, or the account is inactive.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        if session["role"] == "admin":
            stats = {
                "students": con.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()["n"],
                "instructors": con.execute("SELECT COUNT(*) n FROM users WHERE role='instructor'").fetchone()["n"],
                "courses": con.execute("SELECT COUNT(*) n FROM courses").fetchone()["n"],
                "enrollments": con.execute("SELECT COUNT(*) n FROM enrollments").fetchone()["n"]}
            courses = con.execute("""SELECT c.*,u.name instructor_name,
              (SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) lesson_count
              FROM courses c LEFT JOIN users u ON u.id=c.instructor_id ORDER BY c.id DESC""").fetchall()
            return render_template("admin_dashboard.html", stats=stats, courses=courses)
        if session["role"] == "instructor":
            courses = con.execute("""SELECT c.*, (SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) lesson_count
              FROM courses c WHERE c.instructor_id=? ORDER BY c.id DESC""", (session["user_id"],)).fetchall()
            return render_template("instructor_dashboard.html", courses=courses)
        courses = con.execute("""SELECT c.*,u.name instructor_name,
          (SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) lesson_count,
          (SELECT COUNT(*) FROM lessons l JOIN lesson_progress p ON p.lesson_id=l.id
             WHERE l.course_id=c.id AND p.student_id=? AND p.completed=1) completed_count,
          (SELECT passed FROM exam_results e WHERE e.course_id=c.id AND e.student_id=?) exam_passed
          FROM courses c JOIN enrollments en ON en.course_id=c.id
          LEFT JOIN users u ON u.id=c.instructor_id
          WHERE en.student_id=? ORDER BY c.id DESC""",
          (session["user_id"],session["user_id"],session["user_id"])).fetchall()
        return render_template("student_dashboard.html", courses=courses)

@app.route("/admin/users", methods=["GET","POST"])
@roles_required("admin")
def manage_users():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        username=request.form.get("username","").strip().lower()
        password=request.form.get("password","")
        role=request.form.get("role","")
        if not name or not username or len(password)<8 or role not in ("student","instructor"):
            flash("Enter all fields. Password must be at least 8 characters; role must be student or instructor.", "danger")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(name,username,password_hash,role) VALUES(?,?,?,?)",
                                (name,username,generate_password_hash(password),role))
                flash(f"{role.title()} account created. Share login details privately.", "success")
            except sqlite3.IntegrityError:
                flash("That username is already in use.", "danger")
        return redirect(url_for("manage_users"))
    with db() as con:
        users=con.execute("SELECT id,name,username,role,active,created_at FROM users ORDER BY role,name").fetchall()
    return render_template("users.html", users=users)

@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_user(user_id):
    with db() as con:
        user=con.execute("SELECT id,role,active FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or user["role"]=="admin": abort(404)
        con.execute("UPDATE users SET active=? WHERE id=?", (0 if user["active"] else 1,user_id))
    flash("Account status updated.", "success")
    return redirect(url_for("manage_users"))

@app.route("/admin/courses/new", methods=["GET","POST"])
@roles_required("admin")
def new_course():
    with db() as con:
        instructors=con.execute("SELECT id,name,username FROM users WHERE role='instructor' AND active=1 ORDER BY name").fetchall()
    if request.method=="POST":
        title=request.form.get("title","").strip()
        description=request.form.get("description","").strip()
        instructor_id=request.form.get("instructor_id") or None
        if not title:
            flash("Course title is required.", "danger")
            return redirect(url_for("new_course"))
        with db() as con:
            con.execute("INSERT INTO courses(title,description,instructor_id) VALUES(?,?,?)",(title,description,instructor_id))
            course_id=con.execute("SELECT last_insert_rowid()").fetchone()[0]
        flash("Course created. Add lessons and exam questions next.", "success")
        return redirect(url_for("edit_course", course_id=course_id))
    return render_template("course_new.html", instructors=instructors)

@app.route("/admin/courses/<int:course_id>/edit", methods=["GET","POST"])
@roles_required("admin")
def edit_course(course_id):
    with db() as con:
        course=con.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if not course: abort(404)
        instructors=con.execute("SELECT id,name FROM users WHERE role='instructor' AND active=1 ORDER BY name").fetchall()
        lessons=con.execute("SELECT * FROM lessons WHERE course_id=? ORDER BY position,id", (course_id,)).fetchall()
        questions=con.execute("SELECT * FROM exam_questions WHERE course_id=? ORDER BY id", (course_id,)).fetchall()
    if request.method=="POST":
        title=request.form.get("title","").strip()
        description=request.form.get("description","").strip()
        instructor_id=request.form.get("instructor_id") or None
        with db() as con:
            con.execute("UPDATE courses SET title=?,description=?,instructor_id=? WHERE id=?",
                        (title,description,instructor_id,course_id))
        flash("Course details updated.", "success")
        return redirect(url_for("edit_course", course_id=course_id))
    return render_template("course_edit.html", course=course, instructors=instructors, lessons=lessons, questions=questions)

@app.route("/admin/courses/<int:course_id>/lessons", methods=["POST"])
@roles_required("admin")
def add_lesson(course_id):
    title=request.form.get("title","").strip()
    body=request.form.get("content","").strip()
    upload=request.files.get("material")
    if not title:
        flash("Lesson title is required.", "danger")
        return redirect(url_for("edit_course",course_id=course_id))
    filename=None; file_type=None
    if upload and upload.filename:
        if not allowed_file(upload.filename):
            flash("Allowed lesson files: PDF, MP4, WEBM, MOV, M4V.", "danger")
            return redirect(url_for("edit_course",course_id=course_id))
        ext=upload.filename.rsplit(".",1)[1].lower()
        filename=f"{secrets.token_hex(16)}.{ext}"
        upload.save(os.path.join(UPLOAD_DIR,filename))
        file_type="video" if ext in {"mp4","webm","mov","m4v"} else "pdf"
    with db() as con:
        exists=con.execute("SELECT id FROM courses WHERE id=?",(course_id,)).fetchone()
        if not exists: abort(404)
        pos=con.execute("SELECT COALESCE(MAX(position),0)+1 n FROM lessons WHERE course_id=?",(course_id,)).fetchone()["n"]
        con.execute("INSERT INTO lessons(course_id,title,content,file_name,file_type,position) VALUES(?,?,?,?,?,?)",
                    (course_id,title,body,filename,file_type,pos))
    flash("Lesson added.", "success")
    return redirect(url_for("edit_course",course_id=course_id))

@app.route("/admin/lessons/<int:lesson_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_lesson(lesson_id):
    with db() as con:
        lesson=con.execute("SELECT * FROM lessons WHERE id=?",(lesson_id,)).fetchone()
        if lesson:
            if lesson["file_name"]:
                try: os.remove(os.path.join(UPLOAD_DIR,lesson["file_name"]))
                except OSError: pass
            con.execute("DELETE FROM lessons WHERE id=?",(lesson_id,))
    flash("Lesson deleted.", "success")
    return redirect(url_for("edit_course",course_id=request.form.get("course_id",1)))

@app.route("/admin/courses/<int:course_id>/questions", methods=["POST"])
@roles_required("admin")
def add_question(course_id):
    fields=[request.form.get(k,"").strip() for k in ("question","option_a","option_b","option_c","option_d")]
    correct=request.form.get("correct_option","")
    if not all(fields) or correct not in ("a","b","c","d"):
        flash("Complete the question, all four options, and the correct answer.", "danger")
    else:
        with db() as con:
            con.execute("""INSERT INTO exam_questions(course_id,question,option_a,option_b,option_c,option_d,correct_option)
              VALUES(?,?,?,?,?,?,?)""",(course_id,*fields,correct))
        flash("Exam question added.", "success")
    return redirect(url_for("edit_course",course_id=course_id))

@app.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_question(question_id):
    with db() as con:
        q=con.execute("SELECT course_id FROM exam_questions WHERE id=?",(question_id,)).fetchone()
        if not q: abort(404)
        course_id=q["course_id"]
        con.execute("DELETE FROM exam_questions WHERE id=?",(question_id,))
    flash("Question deleted.", "success")
    return redirect(url_for("edit_course",course_id=course_id))

@app.route("/admin/courses/<int:course_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_course(course_id):
    with db() as con:
        lessons=con.execute("SELECT file_name FROM lessons WHERE course_id=?",(course_id,)).fetchall()
        for l in lessons:
            if l["file_name"]:
                try: os.remove(os.path.join(UPLOAD_DIR,l["file_name"]))
                except OSError: pass
        con.execute("DELETE FROM courses WHERE id=?",(course_id,))
    flash("Course deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/assignments", methods=["GET", "POST"])
@roles_required("admin")
def manage_assignments():
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        course_id = request.form.get("course_id", type=int)
        action = request.form.get("action", "assign")
        with db() as con:
            student = con.execute("SELECT id FROM users WHERE id=? AND role='student' AND active=1", (student_id,)).fetchone()
            course = con.execute("SELECT id FROM courses WHERE id=?", (course_id,)).fetchone()
            if not student or not course:
                flash("Choose a valid active student and course.", "danger")
            elif action == "remove":
                con.execute("DELETE FROM enrollments WHERE student_id=? AND course_id=?", (student_id, course_id))
                flash("Course assignment removed.", "success")
            else:
                con.execute("INSERT OR IGNORE INTO enrollments(student_id,course_id) VALUES(?,?)", (student_id, course_id))
                flash("Course assigned to student.", "success")
        return redirect(url_for("manage_assignments"))
    with db() as con:
        students = con.execute("SELECT id,name,username FROM users WHERE role='student' AND active=1 ORDER BY name").fetchall()
        courses = con.execute("SELECT id,title FROM courses ORDER BY title").fetchall()
        assignments = con.execute("""SELECT en.student_id,en.course_id,u.name student_name,u.username,
          c.title course_title FROM enrollments en JOIN users u ON u.id=en.student_id
          JOIN courses c ON c.id=en.course_id ORDER BY u.name,c.title""").fetchall()
    return render_template("assignments.html", students=students, courses=courses, assignments=assignments)

@app.route("/course/<int:course_id>")
@login_required
def course_view(course_id):
    with db() as con:
        course=con.execute("SELECT c.*,u.name instructor_name FROM courses c LEFT JOIN users u ON u.id=c.instructor_id WHERE c.id=?",(course_id,)).fetchone()
        if not course: abort(404)
        if not user_can_access_course(con,course_id): abort(403)
        lessons=con.execute("""SELECT l.*,COALESCE(p.completed,0) completed FROM lessons l
          LEFT JOIN lesson_progress p ON p.lesson_id=l.id AND p.student_id=?
          WHERE l.course_id=? ORDER BY l.position,l.id""",(session["user_id"],course_id)).fetchall()
        questions=con.execute("SELECT id,question,option_a,option_b,option_c,option_d FROM exam_questions WHERE course_id=? ORDER BY id",(course_id,)).fetchall()
        result=con.execute("SELECT * FROM exam_results WHERE student_id=? AND course_id=?",(session["user_id"],course_id)).fetchone() if session["role"]=="student" else None
    return render_template("course_view.html",course=course,lessons=lessons,questions=questions,result=result)

@app.route("/lesson/<int:lesson_id>/file")
@login_required
def lesson_file(lesson_id):
    with db() as con:
        lesson=con.execute("SELECT * FROM lessons WHERE id=?",(lesson_id,)).fetchone()
        if not lesson or not lesson["file_name"]: abort(404)
        if not user_can_access_course(con,lesson["course_id"]): abort(403)
        path=os.path.join(UPLOAD_DIR,lesson["file_name"])
        if not os.path.isfile(path): abort(404)
        # Serve inline; this discourages downloading but cannot prevent all copying.
        mimetype="application/pdf" if lesson["file_type"]=="pdf" else "video/"+("mp4" if path.endswith(".mp4") else "webm")
        response=make_response(send_file(path, mimetype=mimetype, as_attachment=False, conditional=True))
        response.headers["Content-Disposition"]="inline"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Accept-Ranges"]="bytes"
        response.headers["Cache-Control"]="private, no-store"
        return response

@app.route("/lesson/<int:lesson_id>/complete", methods=["POST"])
@roles_required("student")
def complete_lesson(lesson_id):
    with db() as con:
        lesson=con.execute("SELECT * FROM lessons WHERE id=?",(lesson_id,)).fetchone()
        if not lesson or not user_can_access_course(con,lesson["course_id"]): abort(403)
        con.execute("INSERT INTO lesson_progress(student_id,lesson_id,completed) VALUES(?,?,1) ON CONFLICT(student_id,lesson_id) DO UPDATE SET completed=1",
                    (session["user_id"],lesson_id))
    flash("Lesson marked complete.", "success")
    return redirect(url_for("course_view",course_id=lesson["course_id"]))

@app.route("/course/<int:course_id>/exam", methods=["POST"])
@roles_required("student")
def submit_exam(course_id):
    with db() as con:
        if not user_can_access_course(con,course_id): abort(403)
        questions=con.execute("SELECT * FROM exam_questions WHERE course_id=? ORDER BY id",(course_id,)).fetchall()
        if not questions:
            flash("This course does not have exam questions yet.", "warning")
            return redirect(url_for("course_view",course_id=course_id))
        score=0
        for q in questions:
            if request.form.get(f"q_{q['id']}","")==q["correct_option"]: score+=1
        passed=1 if score/len(questions)>=0.7 else 0
        with db() as con2:
            con2.execute("""INSERT INTO exam_results(student_id,course_id,score,total,passed) VALUES(?,?,?,?,?)
              ON CONFLICT(student_id,course_id) DO UPDATE SET score=excluded.score,total=excluded.total,passed=excluded.passed,attempted_at=CURRENT_TIMESTAMP""",
              (session["user_id"],course_id,score,len(questions),passed))
    flash(f"Exam result: {score}/{len(questions)}. "+("You passed! Your certificate is ready." if passed else "You need 70% to pass. Review the lessons and try again."), "success" if passed else "warning")
    return redirect(url_for("course_view",course_id=course_id))

@app.route("/course/<int:course_id>/certificate")
@roles_required("student")
def certificate(course_id):
    with db() as con:
        course=con.execute("SELECT * FROM courses WHERE id=?",(course_id,)).fetchone()
        result=con.execute("SELECT * FROM exam_results WHERE student_id=? AND course_id=? AND passed=1",(session["user_id"],course_id)).fetchone()
        if not course or not result: abort(403)
    output=BytesIO()
    pdf=canvas.Canvas(output,pagesize=landscape(A4))
    w,h=landscape(A4)
    pdf.setFillColorRGB(0.96,0.97,1);pdf.rect(0,0,w,h,fill=1,stroke=0)
    pdf.setStrokeColorRGB(0.31,0.27,0.9);pdf.setLineWidth(4);pdf.rect(24,24,w-48,h-48,stroke=1,fill=0)
    pdf.setFillColorRGB(0.09,0.14,0.25);pdf.setFont("Helvetica-Bold",28);pdf.drawCentredString(w/2,h-115,"CERTIFICATE OF COMPLETION")
    pdf.setFillColorRGB(0.35,0.38,0.48);pdf.setFont("Helvetica",14);pdf.drawCentredString(w/2,h-158,"This certificate is proudly presented to")
    pdf.setFillColorRGB(0.31,0.27,0.9);pdf.setFont("Helvetica-Bold",26);pdf.drawCentredString(w/2,h-205,session.get("name","Student"))
    pdf.setFillColorRGB(0.35,0.38,0.48);pdf.setFont("Helvetica",14);pdf.drawCentredString(w/2,h-245,"for successfully completing the course")
    pdf.setFillColorRGB(0.09,0.14,0.25);pdf.setFont("Helvetica-Bold",20);pdf.drawCentredString(w/2,h-278,course["title"][:90])
    pdf.setFont("Helvetica",11);pdf.setFillColorRGB(0.35,0.38,0.48)
    pdf.drawCentredString(w/2,85,f"Issued on {datetime.now().strftime('%d %B %Y')}  |  Result: {result['score']}/{result['total']} ({round(result['score']/result['total']*100)}%)")
    pdf.setFont("Helvetica-Oblique",10);pdf.drawCentredString(w/2,62,"Edunexia Learning Platform")
    pdf.showPage();pdf.save();output.seek(0)
    return send_file(output,mimetype="application/pdf",as_attachment=True,download_name=f"certificate_course_{course_id}.pdf")

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="You do not have permission to access this content."),403
@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="The requested page or content was not found."),404

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
