from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date
from math import isfinite
from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import Vehicle, TransportRoute, TransportAssignment, Student, HostelRoom, HostelAllocation, InventoryItem, InventoryTransaction, Book, LibraryIssue, MessMenu, AuditLog
from .access import roles_required
ops_bp=Blueprint('operations',__name__)

@ops_bp.route('/operations/dashboard')
@login_required
@roles_required("admin", "operations_admin")
def dashboard():
    return render_template('operations/dashboard.html', vehicles=Vehicle.query.count(), routes=TransportRoute.query.count(), hostel_rooms=HostelRoom.query.count(), inventory=InventoryItem.query.count())


@ops_bp.route('/transport', methods=['GET','POST'])
@login_required
@roles_required("admin", "operations_admin")
def transport():
    if request.method=='POST':
        v=Vehicle(registration_no=request.form['registration_no'],vehicle_type=request.form.get('vehicle_type'),capacity=int(request.form.get('capacity') or 30),driver_name=request.form.get('driver_name'),driver_phone=request.form.get('driver_phone'))
        db.session.add(v); db.session.commit(); flash('Vehicle added.','success'); return redirect(url_for('operations.transport'))
    return render_template('operations/transport.html',vehicles=Vehicle.query.order_by(Vehicle.id.desc()).all(),routes=TransportRoute.query.all())

@ops_bp.route('/transport/route', methods=['POST'])
@login_required
@roles_required("admin", "operations_admin")
def route_add():
    r=TransportRoute(name=request.form['name'],pickup_points=request.form.get('pickup_points'),map_points=request.form.get('map_points'),monthly_fee=float(request.form.get('monthly_fee') or 0),vehicle_id=int(request.form['vehicle_id']) if request.form.get('vehicle_id') else None)
    db.session.add(r); db.session.commit(); flash('Transport route added.','success'); return redirect(url_for('operations.transport'))

@ops_bp.route('/transport/assign', methods=['GET','POST'])
@login_required
@roles_required("admin", "operations_admin")
def transport_assign():
    if request.method=='POST':
        db.session.add(TransportAssignment(student_id=int(request.form['student_id']),route_id=int(request.form['route_id']),pickup_point=request.form.get('pickup_point'))); db.session.commit(); flash('Student assigned to route.','success')
    return render_template('operations/transport_assign.html',students=Student.query.filter_by(status='Active').all(),routes=TransportRoute.query.all(),assignments=TransportAssignment.query.order_by(TransportAssignment.id.desc()).all())

@ops_bp.route('/hostel', methods=['GET','POST'])
@login_required
@roles_required("admin", "operations_admin")
def hostel():
    if request.method=='POST':
        db.session.add(HostelRoom(block=request.form['block'],room_no=request.form['room_no'],capacity=int(request.form.get('capacity') or 4),gender=request.form.get('gender'))); db.session.commit(); flash('Hostel room added.','success'); return redirect(url_for('operations.hostel'))
    return render_template('operations/hostel.html',rooms=HostelRoom.query.all(),students=Student.query.filter_by(status='Active').all(),allocations=HostelAllocation.query.order_by(HostelAllocation.id.desc()).all())

@ops_bp.route('/hostel/assign', methods=['POST'])
@login_required
@roles_required("admin", "operations_admin")
def hostel_assign():
    room_id = request.form.get("room_id", type=int)
    HostelRoom.query.filter_by(id=room_id).update({HostelRoom.capacity: HostelRoom.capacity}, synchronize_session=False)
    room=db.session.get(HostelRoom,room_id) if room_id else None; active=HostelAllocation.query.filter_by(room_id=room.id,status='Active').count() if room else 999
    if not room or active>=room.capacity: flash('Room is full or invalid.','danger')
    else:
        db.session.add(HostelAllocation(student_id=int(request.form['student_id']),room_id=room.id,bed_no=request.form.get('bed_no'))); db.session.commit(); flash('Student allocated.','success')
    return redirect(url_for('operations.hostel'))

@ops_bp.route('/inventory', methods=['GET','POST'])
@login_required
@roles_required("admin", "operations_admin")
def inventory():
    if request.method=='POST':
        db.session.add(InventoryItem(item_code=request.form['item_code'],name=request.form['name'],category=request.form.get('category'),unit=request.form.get('unit') or 'pcs',quantity=int(request.form.get('quantity') or 0),reorder_level=int(request.form.get('reorder_level') or 5),location=request.form.get('location'))); db.session.commit(); flash('Inventory item added.','success'); return redirect(url_for('operations.inventory'))
    return render_template('operations/inventory.html',items=InventoryItem.query.order_by(InventoryItem.id.desc()).all())

@ops_bp.route('/inventory/transaction', methods=['POST'])
@login_required
@roles_required("admin", "operations_admin")
def inventory_tx():
    item_id = request.form.get("item_id", type=int)
    quantity = request.form.get("quantity", type=int)
    direction = request.form.get("transaction_type")
    if not item_id or not quantity or quantity < 1 or direction not in ("IN", "OUT"):
        flash("Invalid transaction.", "danger")
        return redirect(url_for("operations.inventory"))
    stock = InventoryItem.query.filter_by(id=item_id)
    change = quantity
    if direction == "OUT":
        stock = stock.filter(InventoryItem.quantity >= quantity)
        change = -quantity
    if stock.update({InventoryItem.quantity: InventoryItem.quantity + change}, synchronize_session=False):
        db.session.add(InventoryTransaction(item_id=item_id, transaction_type=direction,
                                           quantity=quantity, reference=request.form.get("reference"),
                                           created_by=current_user.id))
        db.session.commit()
        flash("Stock updated.", "success")
    else:
        flash("Item not found or insufficient stock.", "danger")
    return redirect(url_for("operations.inventory"))


@ops_bp.route('/library/return/<int:issue_id>', methods=['POST'])
@login_required
@roles_required("admin", "librarian")
def library_return(issue_id):
    issue = LibraryIssue.query.filter_by(id=issue_id)
    if issue.filter_by(status="Issued").update(
        {LibraryIssue.status: "Returned", LibraryIssue.return_date: date.today()},
        synchronize_session=False,
    ):
        book_id = issue.with_entities(LibraryIssue.book_id).scalar()
        Book.query.filter_by(id=book_id).filter(Book.available < Book.quantity).update(
            {Book.available: Book.available + 1}, synchronize_session=False
        )
        db.session.commit()
        flash("Book returned.", "success")
    return redirect(url_for("library.issue"))


RECORDS = {
    "mess": (MessMenu, "Meal Plan", "mess.index", (
        ("menu_date", "Date", "date"), ("meal_type", "Meal", ("Breakfast", "Lunch", "Tea", "Dinner")),
        ("menu", "Menu", "textarea"), ("estimated_cost", "Estimated cost", "decimal"),
    )),
    "hostel": (HostelRoom, "Hostel Room", "operations.hostel", (
        ("block", "Block", "required"), ("room_no", "Room number", "required"),
        ("capacity", "Capacity", "positive"), ("gender", "Gender", "text"),
    )),
    "inventory": (InventoryItem, "Inventory Item", "operations.inventory", (
        ("item_code", "Item code", "required"), ("name", "Name", "required"),
        ("category", "Category", "text"), ("unit", "Unit", "required"),
        ("reorder_level", "Reorder level", "integer"), ("location", "Location", "text"),
    )),
}


def parse_record_fields(model, fields):
    values = {}
    for key, label, kind in fields:
        raw = request.form.get(key, "").strip()
        if kind == "date":
            value = date.fromisoformat(raw)
        elif kind in ("integer", "positive"):
            value = int(raw)
            if not (int(kind == "positive") <= value <= 2_147_483_647):
                raise ValueError(f"Enter a valid {label.lower()}.")
        elif kind == "decimal":
            value = float(raw or "0")
            if not isfinite(value) or value < 0:
                raise ValueError(f"Enter a valid {label.lower()}.")
        else:
            limit = getattr(model.__table__.columns[key].type, "length", None) or 10000
            if (kind in ("required", "textarea") and not raw) or len(raw) > limit:
                raise ValueError(f"Enter a valid {label.lower()}.")
            if isinstance(kind, tuple) and raw not in kind:
                raise ValueError(f"Select a valid {label.lower()}.")
            value = raw
        values[key] = value
    return values


@ops_bp.route("/<any(mess,hostel,inventory):module>/records/<int:record_id>", methods=["GET", "POST"])
@login_required
@roles_required("operations_admin")
def operation_record(module, record_id):
    model, title, back, fields = RECORDS[module]
    if request.method == "POST" and model is HostelRoom:
        HostelRoom.query.filter_by(id=record_id).update(
            {HostelRoom.capacity: HostelRoom.capacity}, synchronize_session=False)
    record = db.get_or_404(model, record_id)
    if request.method == "POST":
        try:
            values = parse_record_fields(model, fields)
            if model is HostelRoom and values["capacity"] < HostelAllocation.query.filter_by(
                room_id=record.id, status="Active"
            ).count():
                raise ValueError("Capacity cannot be lower than the occupied beds.")
            for key, value in values.items():
                setattr(record, key, value)
            db.session.add(AuditLog(user_id=current_user.id, action="RECORD_UPDATE",
                                  module=title, details=f"Updated record #{record_id}"))
            db.session.commit()
            flash(f"{title} updated.", "success")
            return redirect(url_for("operations.operation_record", module=module, record_id=record_id), code=303)
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error, ValueError) else "A record already uses this code.", "warning")
            return redirect(url_for("operations.operation_record", module=module, record_id=record_id, edit=1), code=303)
    return render_template("operations/record.html", record=record, title=title, back=back, module=module,
                           fields=fields, editing=request.args.get("edit") == "1")
