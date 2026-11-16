from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from datetime import date, timedelta
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from .extensions import db
from .access import roles_required
from .models import Book, LibraryIssue, Student

library_bp=Blueprint("library",__name__)

@library_bp.route("/books", methods=["GET","POST"])
@login_required
@roles_required("admin", "librarian")
def books():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        isbn = request.form.get("isbn", "").strip() or None
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        qty = request.form.get("quantity", "1")
        if (not title or len(title) > 200 or len(isbn or "") > 50 or len(author) > 150
                or len(category) > 100 or not qty.isdecimal() or len(qty) > 5 or int(qty) < 1):
            flash("Enter a valid title, book details and positive copy count.", "danger")
        else:
            db.session.add(Book(isbn=isbn, title=title, author=author, category=category,
                                quantity=int(qty), available=int(qty)))
            try:
                db.session.commit()
                flash("Book added to the catalogue.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("A book with this ISBN already exists.", "warning")
        return redirect(url_for("library.books"))

    term = request.args.get("q", "").strip()[:100]
    stock = request.args.get("stock", "")
    query = Book.query
    if term:
        query = query.filter(or_(*(field.icontains(term, autoescape=True)
                                   for field in (Book.title, Book.author, Book.isbn, Book.category))))
    if stock == "available":
        query = query.filter(Book.available > 0)
    elif stock == "unavailable":
        query = query.filter(Book.available <= 0)
    totals = db.session.query(func.count(Book.id), func.coalesce(func.sum(Book.quantity), 0),
                              func.coalesce(func.sum(Book.available), 0)).one()
    page = query.order_by(Book.title, Book.id).paginate(per_page=25, error_out=False)
    return render_template("library/books.html", page=page, totals=totals, filters=dict(q=term, stock=stock))

@library_bp.route("/issue", methods=["GET","POST"])
@login_required
@roles_required("admin", "librarian")
def issue():
    today = date.today()
    if request.method == "POST":
        book_id = request.form.get("book_id", type=int)
        student_id = request.form.get("student_id", type=int)
        student = Student.query.filter_by(id=student_id, status="Active").first()
        try:
            due = date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else today + timedelta(days=14)
        except ValueError:
            due = None
        if due is None or due < today:
            flash("Select a due date on or after today.", "danger")
        elif student is None:
            flash("Select an active student.", "danger")
        elif Book.query.filter_by(id=book_id).filter(Book.available > 0).update(
            {Book.available: Book.available - 1}, synchronize_session=False
        ):
            db.session.add(LibraryIssue(book_id=book_id, student_id=student.id, issue_date=today, due_date=due))
            db.session.commit()
            flash("Book issued.", "success")
        else:
            flash("This book is unavailable.", "warning")
        return redirect(url_for("library.issue"))
    books = Book.query.filter(Book.available > 0).order_by(Book.title).all()
    students = Student.query.filter_by(status="Active").order_by(Student.first_name).all()
    status = request.args.get("status", "")
    term = request.args.get("q", "").strip()[:100]
    active = LibraryIssue.query.filter_by(status="Issued")
    overdue = active.filter(LibraryIssue.due_date < today)
    query = LibraryIssue.query
    if status == "overdue":
        query = overdue
    elif status in ("Issued", "Returned"):
        query = query.filter_by(status=status)
    if term:
        query = query.join(Book).join(Student).filter(or_(*(field.icontains(term, autoescape=True)
            for field in (Book.title, Student.admission_no, Student.first_name, Student.last_name))))
    page = query.options(joinedload(LibraryIssue.book), joinedload(LibraryIssue.student)).order_by(
        LibraryIssue.id.desc()).paginate(per_page=25, error_out=False)
    return render_template("library/issue.html", books=books, students=students, page=page,
                           today=today, default_due=today + timedelta(days=14),
                           totals=(active.count(), overdue.count(), LibraryIssue.query.filter_by(status="Returned").count()),
                           filters=dict(q=term, status=status))
