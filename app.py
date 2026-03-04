from flask import Flask, render_template, request, redirect, session, send_file
from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper
import json, os
from datetime import date, datetime

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

app.secret_key = "super_secret_key_2025"

USERNAME = "Boss"
PASSWORD = "1234nadi"

DATA_FILE = "/var/data/data.json"

# ================= DATA =================
def load_data():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except:
            data = []
    return data


def save_data(data):
    # حفظ النسخة الرئيسية
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    # حفظ نسخة احتياطية
    with open("data_backup.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_room(data, room_number):
    for r in data:
        if r["room"] == room_number:
            return r
    return None


# ================= DAYS =================
def remaining_days(g):
    checkin = datetime.strptime(g["checkin"], "%Y-%m-%d").date()
    passed = (date.today() - checkin).days
    return max(g["stay_days"] - passed, 0)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == USERNAME and password == PASSWORD:
            session["user"] = username
            return redirect("/")
        else:
            return render_template("login.html", error="Wrong credentials")

    return render_template("login.html")


# ================= HOME =================
@app.route("/")
@login_required
def home():
    data = load_data()
    keyword = request.args.get("search", "").lower()

    total_rooms = len(data)
    total_guests = 0
    total_warning = 0
    total_expired = 0

    filtered_rooms = []

    for r in data:
        occ = len(r["guests"])
        free = r["beds"] - occ

        match_room = keyword in r["room"].lower()

        match_guest = False
        for g in r["guests"]:
            if (
                keyword in g.get("name", "").lower()
                or keyword in str(g.get("id", "")).lower()
            ):
                match_guest = True

        if keyword and not (match_room or match_guest):
            continue

        for g in r["guests"]:
            days_left = remaining_days(g)
            if days_left == 0:
                total_expired += 1
            elif days_left <= 3:
                total_warning += 1

        total_guests += occ

        filtered_rooms.append({
            "room": r["room"],
            "beds": r["beds"],
            "occupied": occ,
            "free": free
        })

    return render_template(
        "index.html",
        rooms=filtered_rooms,
        total_rooms=total_rooms,
        total_guests=total_guests,
        total_warning=total_warning,
        total_expired=total_expired,
        keyword=keyword
    )


# ================= ADD ROOM =================
@app.route("/add-room", methods=["GET", "POST"])
@login_required
def add_room():
    
    data = load_data()

    if request.method == "POST":
        room_number = request.form["room"].strip()
        beds = request.form["beds"].strip()

        if not room_number or not beds.isdigit():
            return redirect("/add-room")

        if get_room(data, room_number):
            return redirect("/add-room")

        data.append({
            "room": room_number,
            "beds": int(beds),
            "guests": []
        })

        save_data(data)
        return redirect("/")

    return render_template("add_room.html")

# ================= ROOM DETAILS =================
@app.route("/room/<room_number>")
@login_required
def room_details(room_number):
    data = load_data()
    room = get_room(data, room_number)

    if not room:
        return redirect("/")

    guests_with_days = []

    for g in room["guests"]:
        guests_with_days.append({
         "id": g.get("id"),
         "name": g.get("name"),
         "checkin": g.get("checkin"),
         "checkout": g.get("checkout"),
         "note": g.get("note")
    })

    return render_template(
        "room_details.html",
        room=room,
        guests=guests_with_days
    )
    
@app.route("/edit_days/<room_number>/<guest_id>", methods=["POST"])
@login_required
def edit_days(room_number, guest_id):
    data = load_data()
    room = get_room(data, room_number)

    if not room:
        return redirect("/")

    change = request.form["change"].strip()

    if not change.lstrip("-").isdigit():
        return redirect(f"/room/{room_number}")

    change = int(change)

    for g in room["guests"]:
        if str(g.get("id")) == guest_id:
            g["stay_days"] += change
            if g["stay_days"] < 1:
                g["stay_days"] = 1
            break

    save_data(data)
    return redirect(f"/room/{room_number}")

   
@app.route("/delete_guest/<room_number>/<guest_id>", methods=["POST"])
@login_required
def delete_guest(room_number, guest_id):
    data = load_data()
    room = get_room(data, room_number)

    if not room:
        return redirect("/")

    room["guests"] = [
        g for g in room["guests"]
        if str(g.get("id")) != guest_id
    ]

    save_data(data)
    return redirect(f"/room/{room_number}")


@app.route("/delete_room/<room_number>", methods=["POST"])
@login_required
def delete_room(room_number):
    data = load_data()

    data = [
        r for r in data
        if r["room"] != room_number
    ]

    save_data(data)
    return redirect("/")

@app.route("/export-pdf")
@login_required
def export_pdf():
    data = load_data()

    file_path = "static/Hostel_Report.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("Hostify Report", styles["Title"]))
    elements.append(Spacer(1, 20))

    table_data = [["Room", "Beds", "Guests"]]

    for r in data:
        table_data.append([
            r["room"],
            str(r["beds"]),
            str(len(r["guests"]))
        ])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_file("static/Hostel_Report.pdf", as_attachment=True)



@app.route("/backup")
@login_required
def backup():
    return send_file("data.json", as_attachment=True)



@app.route("/logout")
@login_required
def logout():
    session.pop("user", None)
    return redirect("/login")


@app.route("/edit_guest/<room_number>/<guest_id>", methods=["GET","POST"])
@login_required
def edit_guest(room_number, guest_id):

    data = load_data()
    room = get_room(data, room_number)

    guest = None
    for g in room["guests"]:
        if str(g["id"]) == guest_id:
            guest = g

    if request.method == "POST":
        guest["checkout"] = request.form["checkout"]
        guest["note"] = request.form["note"]

        save_data(data)

        return redirect(f"/room/{room_number}")

    return render_template("edit_guest.html", guest=guest, room=room)

@app.route("/add_guest/<room_number>", methods=["POST"])
@login_required
def add_guest(room_number):

    data = load_data()
    room = get_room(data, room_number)

    guest_id = request.form["id"].strip()
    name = request.form["name"].strip()
    checkin = request.form["checkin"]
    checkout = request.form["checkout"]
    note = request.form["note"]

    print(guest_id, name, checkin, checkout, note)

    if not guest_id or not name:
        return redirect(f"/room/{room_number}")

    new_guest = {
        "id": guest_id,
        "name": name,
        "checkin": checkin,
        "checkout": checkout,
        "note": note
    }

    room["guests"].append(new_guest)

    save_data(data)

    return redirect(f"/room/{room_number}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)