"""Library Management System - Flask + MySQL
Modules: Books, Members, Issue & Return (plus a dashboard).
"""
import os
from datetime import date, timedelta

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Defaults match a fresh XAMPP install (user root, empty password).
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "library_db"),
}

LOAN_DAYS = 14       # default loan period
FINE_PER_DAY = 5     # Tk per late day
MEMBER_TYPES = ["Student", "Faculty", "Staff"]


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().cursor(dictionary=True)
    cur.execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(sql, args)
        db.commit()
        return cur.lastrowid
    except mysql.connector.Error:
        db.rollback()
        raise
    finally:
        cur.close()


@app.template_filter("hue")
def hue_filter(text):
    """Stable colour per category, used for the book 'spine' marker."""
    return sum(ord(c) for c in (text or "")) * 7 % 360


@app.errorhandler(mysql.connector.Error)
def db_error(err):
    return render_template("error.html", message=str(err)), 500


# --------------------------------------------------------------- dashboard
@app.route("/")
def index():
    stats = query(
        """SELECT
             (SELECT COUNT(*) FROM books)                                   AS titles,
             (SELECT COALESCE(SUM(total_copies),0) FROM books)              AS copies,
             (SELECT COUNT(*) FROM members)                                 AS members,
             (SELECT COUNT(*) FROM issues WHERE return_date IS NULL)        AS on_loan,
             (SELECT COUNT(*) FROM issues
                WHERE return_date IS NULL AND due_date < CURDATE())         AS overdue,
             (SELECT COALESCE(SUM(fine),0) FROM issues)                     AS fines""",
        one=True,
    )
    overdue = query(
        """SELECT i.issue_id, b.title, m.name, i.due_date,
                  DATEDIFF(CURDATE(), i.due_date) AS days_late,
                  DATEDIFF(CURDATE(), i.due_date) * %s AS fine_amt
           FROM issues i
           JOIN books b ON b.book_id = i.book_id
           JOIN members m ON m.member_id = i.member_id
           WHERE i.return_date IS NULL AND i.due_date < CURDATE()
           ORDER BY i.due_date LIMIT 6""",
        (FINE_PER_DAY,),
    )
    recent = query(
        """SELECT i.issue_id, b.title, m.name, i.issue_date, i.return_date
           FROM issues i
           JOIN books b ON b.book_id = i.book_id
           JOIN members m ON m.member_id = i.member_id
           ORDER BY i.issue_id DESC LIMIT 6"""
    )
    return render_template("index.html", stats=stats, overdue=overdue, recent=recent)


# ------------------------------------------------------------------- books
def read_book_form():
    f = request.form
    data = {
        "title": f.get("title", "").strip(),
        "author": f.get("author", "").strip(),
        "isbn": f.get("isbn", "").strip(),
        "category": f.get("category", "").strip(),
        "total_copies": f.get("total_copies", "").strip(),
    }
    error = None
    if not all([data["title"], data["author"], data["isbn"], data["category"]]):
        error = "Title, author, ISBN and category are required."
    elif not data["total_copies"].isdigit() or int(data["total_copies"]) < 1:
        error = "Copies must be a whole number of 1 or more."
    return data, error


def book_categories():
    return [r["category"] for r in query("SELECT DISTINCT category FROM books ORDER BY category")]


@app.route("/books")
def books():
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM books"
    args = ()
    if q:
        sql += " WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s OR category LIKE %s"
        args = (f"%{q}%",) * 4
    rows = query(sql + " ORDER BY title", args)
    return render_template("books.html", books=rows, q=q)


@app.route("/books/add", methods=["GET", "POST"])
def add_book():
    data = {"title": "", "author": "", "isbn": "", "category": "", "total_copies": "1"}
    if request.method == "POST":
        data, error = read_book_form()
        if error:
            flash(error, "error")
        else:
            try:
                n = int(data["total_copies"])
                execute(
                    """INSERT INTO books (title, author, isbn, category, total_copies, available_copies)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (data["title"], data["author"], data["isbn"], data["category"], n, n),
                )
                flash(f"Added “{data['title']}”.", "ok")
                return redirect(url_for("books"))
            except mysql.connector.IntegrityError:
                flash("A book with that ISBN already exists.", "error")
    return render_template("book_form.html", book=data, categories=book_categories(), editing=False)


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    book = query("SELECT * FROM books WHERE book_id=%s", (book_id,), one=True)
    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("books"))
    issued = book["total_copies"] - book["available_copies"]

    if request.method == "POST":
        data, error = read_book_form()
        if not error and int(data["total_copies"]) < issued:
            error = f"{issued} cop{'y is' if issued == 1 else 'ies are'} currently on loan, so copies can't go below {issued}."
        if error:
            flash(error, "error")
            book = {**book, **data}
        else:
            try:
                n = int(data["total_copies"])
                execute(
                    """UPDATE books SET title=%s, author=%s, isbn=%s, category=%s,
                              total_copies=%s, available_copies=%s WHERE book_id=%s""",
                    (data["title"], data["author"], data["isbn"], data["category"], n, n - issued, book_id),
                )
                flash("Book updated.", "ok")
                return redirect(url_for("books"))
            except mysql.connector.IntegrityError:
                flash("A book with that ISBN already exists.", "error")
                book = {**book, **data}
    return render_template("book_form.html", book=book, categories=book_categories(), editing=True)


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    used = query("SELECT COUNT(*) AS n FROM issues WHERE book_id=%s", (book_id,), one=True)["n"]
    if used:
        flash("This book has borrowing history and can't be deleted.", "error")
    else:
        execute("DELETE FROM books WHERE book_id=%s", (book_id,))
        flash("Book deleted.", "ok")
    return redirect(url_for("books"))


# ----------------------------------------------------------------- members
def read_member_form():
    f = request.form
    data = {
        "name": f.get("name", "").strip(),
        "email": f.get("email", "").strip(),
        "phone": f.get("phone", "").strip(),
        "member_type": f.get("member_type", "Student"),
    }
    error = None
    if not data["name"] or not data["email"]:
        error = "Name and email are required."
    elif "@" not in data["email"]:
        error = "Enter a valid email address."
    elif data["member_type"] not in MEMBER_TYPES:
        error = "Choose a member type from the list."
    return data, error


@app.route("/members")
def members():
    q = request.args.get("q", "").strip()
    sql = """SELECT m.*,
                    (SELECT COUNT(*) FROM issues i
                     WHERE i.member_id = m.member_id AND i.return_date IS NULL) AS on_loan
             FROM members m"""
    args = ()
    if q:
        sql += " WHERE m.name LIKE %s OR m.email LIKE %s OR m.phone LIKE %s"
        args = (f"%{q}%",) * 3
    rows = query(sql + " ORDER BY m.name", args)
    return render_template("members.html", members=rows, q=q)


@app.route("/members/add", methods=["GET", "POST"])
def add_member():
    data = {"name": "", "email": "", "phone": "", "member_type": "Student"}
    if request.method == "POST":
        data, error = read_member_form()
        if error:
            flash(error, "error")
        else:
            try:
                execute(
                    "INSERT INTO members (name, email, phone, member_type) VALUES (%s,%s,%s,%s)",
                    (data["name"], data["email"], data["phone"] or None, data["member_type"]),
                )
                flash(f"Added member {data['name']}.", "ok")
                return redirect(url_for("members"))
            except mysql.connector.IntegrityError:
                flash("A member with that email already exists.", "error")
    return render_template("member_form.html", member=data, types=MEMBER_TYPES, editing=False)


@app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
def edit_member(member_id):
    member = query("SELECT * FROM members WHERE member_id=%s", (member_id,), one=True)
    if not member:
        flash("Member not found.", "error")
        return redirect(url_for("members"))
    if request.method == "POST":
        data, error = read_member_form()
        if error:
            flash(error, "error")
            member = {**member, **data}
        else:
            try:
                execute(
                    "UPDATE members SET name=%s, email=%s, phone=%s, member_type=%s WHERE member_id=%s",
                    (data["name"], data["email"], data["phone"] or None, data["member_type"], member_id),
                )
                flash("Member updated.", "ok")
                return redirect(url_for("members"))
            except mysql.connector.IntegrityError:
                flash("A member with that email already exists.", "error")
                member = {**member, **data}
    return render_template("member_form.html", member=member, types=MEMBER_TYPES, editing=True)


@app.route("/members/<int:member_id>/delete", methods=["POST"])
def delete_member(member_id):
    used = query("SELECT COUNT(*) AS n FROM issues WHERE member_id=%s", (member_id,), one=True)["n"]
    if used:
        flash("This member has borrowing history and can't be deleted.", "error")
    else:
        execute("DELETE FROM members WHERE member_id=%s", (member_id,))
        flash("Member deleted.", "ok")
    return redirect(url_for("members"))


# ---------------------------------------------------------- issue & return
@app.route("/issues")
def issues():
    status = request.args.get("status", "all")
    where = {
        "all": "",
        "active": "WHERE i.return_date IS NULL",
        "overdue": "WHERE i.return_date IS NULL AND i.due_date < CURDATE()",
        "returned": "WHERE i.return_date IS NOT NULL",
    }.get(status, "")
    rows = query(
        f"""SELECT i.*, b.title, m.name,
                   CASE WHEN i.return_date IS NOT NULL THEN 'returned'
                        WHEN i.due_date < CURDATE() THEN 'overdue'
                        ELSE 'active' END AS status,
                   CASE WHEN i.return_date IS NULL
                        THEN GREATEST(DATEDIFF(CURDATE(), i.due_date), 0) * %s
                        ELSE i.fine END AS fine_amt
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN members m ON m.member_id = i.member_id
            {where}
            ORDER BY i.issue_id DESC""",
        (FINE_PER_DAY,),
    )
    return render_template("issues.html", issues=rows, status=status, fine_per_day=FINE_PER_DAY)


@app.route("/issues/new", methods=["GET", "POST"])
def issue_book():
    today = date.today()
    default_due = today + timedelta(days=LOAN_DAYS)

    if request.method == "POST":
        book_id = request.form.get("book_id", type=int)
        member_id = request.form.get("member_id", type=int)
        try:
            due = date.fromisoformat(request.form.get("due_date", ""))
        except ValueError:
            due = None

        if not book_id or not member_id:
            flash("Choose both a book and a member.", "error")
        elif due is None or due < today:
            flash("Due date must be today or later.", "error")
        else:
            db = get_db()
            cur = db.cursor(dictionary=True)
            try:
                # lock the row so two librarians can't issue the last copy at once
                cur.execute("SELECT title, available_copies FROM books WHERE book_id=%s FOR UPDATE", (book_id,))
                book = cur.fetchone()
                if not book or book["available_copies"] < 1:
                    db.rollback()
                    flash("No copies of that book are available right now.", "error")
                else:
                    cur.execute(
                        "INSERT INTO issues (book_id, member_id, issue_date, due_date) VALUES (%s,%s,%s,%s)",
                        (book_id, member_id, today, due),
                    )
                    cur.execute(
                        "UPDATE books SET available_copies = available_copies - 1 WHERE book_id=%s",
                        (book_id,),
                    )
                    db.commit()
                    flash(f"Issued “{book['title']}”, due {due:%d %b %Y}.", "ok")
                    return redirect(url_for("issues", status="active"))
            except mysql.connector.Error:
                db.rollback()
                raise
            finally:
                cur.close()

    available = query("SELECT book_id, title, author, available_copies FROM books WHERE available_copies > 0 ORDER BY title")
    people = query("SELECT member_id, name, member_type FROM members ORDER BY name")
    return render_template("issue_form.html", books=available, members=people,
                           today=today, default_due=default_due, loan_days=LOAN_DAYS)


@app.route("/issues/<int:issue_id>/return", methods=["POST"])
def return_book(issue_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM issues WHERE issue_id=%s FOR UPDATE", (issue_id,))
        rec = cur.fetchone()
        if not rec or rec["return_date"] is not None:
            db.rollback()
            flash("That loan was already returned or doesn't exist.", "error")
        else:
            today = date.today()
            late_days = max((today - rec["due_date"]).days, 0)
            fine = late_days * FINE_PER_DAY
            cur.execute("UPDATE issues SET return_date=%s, fine=%s WHERE issue_id=%s", (today, fine, issue_id))
            cur.execute("UPDATE books SET available_copies = available_copies + 1 WHERE book_id=%s", (rec["book_id"],))
            db.commit()
            if fine:
                flash(f"Returned {late_days} day{'s' if late_days != 1 else ''} late. Fine to collect: Tk {fine}.", "warn")
            else:
                flash("Returned on time. No fine.", "ok")
    except mysql.connector.Error:
        db.rollback()
        raise
    finally:
        cur.close()
    return redirect(request.referrer or url_for("issues"))


if __name__ == "__main__":
    app.run(debug=True)
