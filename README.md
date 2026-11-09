# Library Desk – Library Management System

A basic web application for running a small library: catalogue books, register members,
and track issuing and returning with automatic fines.

**Stack:** HTML/CSS (client side) · Python Flask (backend) · MySQL (database, XAMPP for offline use)

## Modules
| # | Module | What it does |
|---|--------|--------------|
| 1 | **Books** | Add, edit, delete, search books; tracks total and available copies |
| 2 | **Members** | Add, edit, delete, search members (Student / Faculty / Staff) |
| 3 | **Issue & Return** | Issue a book to a member, mark returned, filter by status, auto-calculate fine |
| + | Dashboard | Totals, overdue list, recent activity |

Rules built in: a book can't be issued when no copies are available; copies can't be lowered
below what is on loan; books/members with borrowing history can't be deleted; fine is
**Tk 5 per late day** (change `FINE_PER_DAY` in `app.py`); default loan is 14 days.

## Database design
```
books (book_id PK, title, author, isbn UNIQUE, category, total_copies, available_copies, added_on)
members (member_id PK, name, email UNIQUE, phone, member_type, joined_on)
issues (issue_id PK, book_id FK, member_id FK, issue_date, due_date, return_date, fine)

books 1 ──< issues >── 1 members        (one book / member, many issue records)
```

## Run it (XAMPP, Windows/Mac)
1. Start **Apache** and **MySQL** in the XAMPP control panel.
2. Open **http://localhost/phpmyadmin** → *Import* → choose `schema.sql` → *Go*.
   (This creates `library_db` with sample data.)
3. In a terminal inside this folder:
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
4. Open **http://127.0.0.1:5000**

If your MySQL root user has a password, set it first:
`set DB_PASSWORD=yourpassword` (Windows) or `export DB_PASSWORD=yourpassword` (Mac/Linux).
Other options: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`.

## Project structure
```
app.py            Flask routes + database logic
schema.sql        tables, constraints, sample data
templates/        HTML pages (Jinja)
static/style.css  styling
```

## GitHub workflow (required: commit regularly)
```bash
git init
git add .
git commit -m "Initial Flask project with schema"
git branch -M main
git remote add origin https://github.com/<username>/library-management-system.git
git push -u origin main
```
Suggested split for two members: one owns **Books + Members**, the other owns **Issue & Return +
Dashboard + report**. Commit small and often, e.g. `git commit -m "Add member search"`.
