# app.py
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import pandas as pd
import os
import random
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret_in_production"

CREDENTIALS_CSV = "credentials.csv"
APPLICATIONS_XLSX = "applications.xlsx"

# Leave types including On Duty
LEAVE_TYPES = ["On Duty", "LHAP", "LAP", "RH", "CL", "CCL"]


# ----------------------------------------------------
# Utilities
# ----------------------------------------------------
def load_credentials():
    if not os.path.exists(CREDENTIALS_CSV):
        return {}
    df = pd.read_csv(CREDENTIALS_CSV, dtype=str)
    return dict(zip(df["username"].astype(str), df["password"].astype(str)))


def save_application_to_excel(data: dict):
    df_row = pd.DataFrame([data])
    if not os.path.exists(APPLICATIONS_XLSX):
        df_row.to_excel(APPLICATIONS_XLSX, index=False)
    else:
        existing = pd.read_excel(APPLICATIONS_XLSX, dtype=str)
        combined = pd.concat([existing, df_row], ignore_index=True)
        combined.to_excel(APPLICATIONS_XLSX, index=False)


def read_all_applications():
    if not os.path.exists(APPLICATIONS_XLSX):
        return pd.DataFrame([], columns=[
            "application_no", "submitted_on", "name", "emp_id", "gender",
            "designation", "department", "nature", "period_from", "period_to",
            "grounds", "address", "phone", "submitted_by_username", "status",
            "leave_days"
        ])
    return pd.read_excel(APPLICATIONS_XLSX, dtype=str)


def update_application_record(application_no: str, updates: dict):
    df = read_all_applications()
    if df.empty:
        return False
    idx = df.index[df["application_no"] == application_no]
    if len(idx) == 0:
        return False
    for k, v in updates.items():
        df.loc[idx, k] = v
    df.to_excel(APPLICATIONS_XLSX, index=False)
    return True


def generate_application_number():
    year_prefix = datetime.now().year
    random_digits = random.randint(100000, 999999)
    return f"{year_prefix}{random_digits}"


# ----------------------------------------------------
# PDF GENERATOR
# ----------------------------------------------------
def generate_leave_pdf(form_data: dict):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from io import BytesIO
    import qrcode, os

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Font + Logo Paths
    base_dir = os.getcwd()
    font_path = os.path.join(base_dir, "NotoSansDevanagari-VariableFont_wdth,wght.ttf")
    logo_path = os.path.join(base_dir, "static", "images", "indian_railways_logo.jpg")

    pdfmetrics.registerFont(TTFont("HindiFont", font_path))
    font = "HindiFont"

    # --------------------------------------------
    # HEADER OUTSIDE BORDER
    # --------------------------------------------
    c.setFont(font, 18)
    c.drawCentredString(
        width / 2,
        height - 35,
        "OFFICE LEAVE APPLICATION FORM / कार्यालय अवकाश आवेदन पत्र"
    )

    # --------------------------------------------
    # BORDER (moved slightly down so header is outside)
    # --------------------------------------------
    top_border_y = height - 60
    margin = 25

    c.setLineWidth(2)
    c.rect(margin, margin, width - 2 * margin, top_border_y - margin)

    y = top_border_y - 30
    margin_x = margin + 20

    # --------------------------------------------
    # LOGO (Placed INSIDE border, aligned right)
    # --------------------------------------------
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        c.drawImage(logo, width - 120, top_border_y - 70, 55, 55, mask='auto')

    # --------------------------------------------
    # DEPARTMENT TITLE
    # --------------------------------------------
    c.setFont(font, 15)
    c.drawCentredString(
        width / 2.1,
        top_border_y - 20,
        "RAIL WHEEL FACTORY, YELAHANKA, BENGALURU"
    )

    c.setFont(font, 13)
    c.drawCentredString(
        width / 2.1,
        top_border_y - 38,
        "रेल पहिया कारखाना, येलहंका, बेंगलुरु"
    )

    y -= 45

    # --------------------------------------------
    # GENERAL DETAILS
    # --------------------------------------------
    c.setFont(font, 12)
    c.drawString(margin_x, y, f"Submitted On / जमा करने की तिथि: {form_data['submitted_on']}")
    y -= 20
    c.drawString(margin_x, y, f"Application No / आवेदन संख्या: {form_data['application_no']}")
    y -= 30

    # --------------------------------------------
    # APPLICANT DETAILS
    # --------------------------------------------
    c.setFont(font, 14)
    c.drawString(margin_x, y, "Applicant Details / आवेदक का विवरण:")
    y -= 22

    c.setFont(font, 12)
    fields = [
        ("Name / नाम", "name"),
        ("Employee ID / कर्मचारी आईडी", "emp_id"),
        ("Gender / लिंग", "gender"),
        ("Designation / पदनाम", "designation"),
        ("Department / विभाग", "department")
    ]

    for label, key in fields:
        c.drawString(margin_x, y, f"{label}: {form_data[key]}")
        y -= 18

    y -= 15

    # --------------------------------------------
    # LEAVE INFO
    # --------------------------------------------
    c.setFont(font, 14)
    c.drawString(margin_x, y, "Leave Information / अवकाश की जानकारी:")
    y -= 22

    c.setFont(font, 12)
    c.drawString(margin_x, y, f"Nature of Leave / अवकाश का प्रकार: {form_data['nature']}")
    y -= 18
    c.drawString(
        margin_x,
        y,
        f"Period / अवधि: {form_data['period_from']} to {form_data['period_to']}"
    )
    y -= 18
    c.drawString(margin_x, y, f"Grounds / कारण: {form_data['grounds']}")
    y -= 22

    # Leave days
    leave_days = form_data.get("leave_days", 0)
    used_days = form_data.get("used_days", 0)
    remaining_days = form_data.get("remaining_days", 0)

    if form_data["nature"] == "On Duty":
        c.drawString(margin_x, y, f"On Duty Leave Days: {leave_days}")
        y -= 18
        c.drawString(
            margin_x,
            y,
            "Note: On Duty leave does NOT reduce monthly quota."
        )
        y -= 25
    else:
        c.drawString(margin_x, y, f"Leave Days Applied: {leave_days}")
        y -= 18
        c.drawString(margin_x, y, f"Used This Month: {used_days}")
        y -= 18
        c.drawString(margin_x, y, f"Remaining Leaves: {remaining_days}")
        y -= 25

    # --------------------------------------------
    # CONTACT
    # --------------------------------------------
    c.setFont(font, 14)
    c.drawString(margin_x, y, "Contact During Leave / अवकाश के दौरान संपर्क:")
    y -= 22

    c.setFont(font, 12)
    c.drawString(margin_x, y, f"Address / पता: {form_data['address']}")
    y -= 18
    c.drawString(margin_x, y, f"Phone / फोन: {form_data['phone']}")
    y -= 60

    # --------------------------------------------
    # SIGNATURES (More gap added)
    # --------------------------------------------
    c.setFont(font, 14)
    c.drawString(margin_x, y, "Signatures / हस्ताक्षर:")
    y -= 28

    c.setFont(font, 12)

    for title in [
        "Applicant / आवेदक",
        "Verifying Officer / सत्यापन अधिकारी",
        "Sanctioning Authority / स्वीकृत प्राधिकारी"
    ]:
        c.line(margin_x, y, margin_x + 260, y)
        c.drawString(margin_x, y - 16, title)
        y -= 55  # gap for handwritten signature

    # --------------------------------------------
    # LINK (BOTTOM-LEFT INSIDE BORDER)
    # --------------------------------------------
    link_y = margin + 25
    c.setFont(font, 11)
    c.setFillColorRGB(0, 0, 1)

    url = f"http://localhost:5000/public/{form_data['application_no']}"
    c.drawString(margin_x, link_y, f"View Application Online: {url}")
    c.linkURL(url, (margin_x, link_y - 5, margin_x + 330, link_y + 10))

    # --------------------------------------------
    # QR CODE (BOTTOM RIGHT INSIDE BORDER)
    # --------------------------------------------
    import qrcode
    qr_data = f"Application No:{form_data['application_no']}\nName:{form_data['name']}"
    qr_img = qrcode.make(qr_data)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    c.drawImage(ImageReader(qr_buf), width - 150, margin + 10, 100, 100)

    # --------------------------------------------
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ----------------------------------------------------
# ROUTES
# ----------------------------------------------------
@app.route("/")
def home():
    return render_template("login_select.html")


@app.route("/public/<app_no>")
def public_view(app_no):
    df = read_all_applications()
    row = df[df["application_no"] == str(app_no)]
    if row.empty:
        return "<h2>Application not found</h2>"

    app_rec = row.iloc[0].to_dict()

    html = f"""
    <h2>Application Details</h2>
    <p><b>Application No:</b> {app_rec.get('application_no')}</p>
    <p><b>Submitted On:</b> {app_rec.get('submitted_on')}</p>
    <p><b>Name:</b> {app_rec.get('name')}</p>
    <p><b>Employee ID:</b> {app_rec.get('emp_id')}</p>
    <p><b>Gender:</b> {app_rec.get('gender')}</p>
    <p><b>Designation:</b> {app_rec.get('designation')}</p>
    <p><b>Department:</b> {app_rec.get('department')}</p>
    <p><b>Nature of Leave:</b> {app_rec.get('nature')}</p>
    <p><b>Period:</b> {app_rec.get('period_from')} to {app_rec.get('period_to')}</p>
    <p><b>Grounds:</b> {app_rec.get('grounds')}</p>
    <p><b>Address:</b> {app_rec.get('address')}</p>
    <p><b>Phone:</b> {app_rec.get('phone')}</p>
    <p><b>Status:</b> {app_rec.get('status')}</p>
    """
    return html


# ----------------------------------------------------
# ADMIN LOGIN
# ----------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username", "")
        pw = request.form.get("password", "")
        if user == "admin" and pw == "admin@123":
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid Admin Credentials", "danger")
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    df = read_all_applications()
    apps = df.fillna("").to_dict(orient="records")
    return render_template("admin_dashboard.html", applications=apps)


@app.route("/admin/view/<app_no>")
def admin_view(app_no):
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    df = read_all_applications()
    row = df[df["application_no"] == app_no]
    if row.empty:
        flash("Application not found", "danger")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_view.html", app=row.iloc[0].to_dict())


@app.route("/admin/action/<app_no>/<action>")
def admin_action(app_no, action):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    df = read_all_applications()
    df["application_no"] = df["application_no"].astype(str)
    app_no = str(app_no)

    if app_no not in df["application_no"].values:
        flash("Application not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    idx = df.index[df["application_no"] == app_no][0]
    status = df.at[idx, "status"]

    if action == "accept" and status == "onprocess":
        df.at[idx, "status"] = "accepted"
    elif action == "reject" and status == "onprocess":
        df.at[idx, "status"] = "rejected"
    elif action == "delete" and status in ["accepted", "rejected"]:
        df = df[df["application_no"] != app_no]
    else:
        flash("Invalid action", "danger")

    df.to_excel(APPLICATIONS_XLSX, index=False)
    return redirect(url_for("admin_dashboard"))


# ----------------------------------------------------
# USER LOGIN
# ----------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    creds = load_credentials()
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u in creds and creds[u] == p:
            session.clear()
            session["username"] = u
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=session["username"])


# ----------------------------------------------------
# LEAVE FORM
# ----------------------------------------------------
@app.route("/leave")
def leave_form():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("leave_form.html", leave_types=LEAVE_TYPES, form_data=None)


@app.route("/submit_leave", methods=["POST"])
def submit_leave():
    if "username" not in session:
        return redirect(url_for("login"))

    # Fetch fields
    name = request.form.get("name", "")
    emp_id = request.form.get("emp_id", "")
    gender = request.form.get("gender", "")
    designation = request.form.get("designation", "")
    department = request.form.get("department", "")
    nature = request.form.get("nature", "")
    period_from = request.form.get("period_from", "")
    period_to = request.form.get("period_to", "")
    grounds = request.form.get("grounds", "")
    address = request.form.get("address", "")
    phone = request.form.get("phone", "")
    edit_app_no = request.form.get("edit_app_no", "")

    # Validation
    if not all([name, emp_id, gender, designation, department, nature,
                period_from, period_to, grounds, address, phone]):
        flash("All fields required", "danger")
        return redirect(url_for("leave_form"))

    if not (phone.isdigit() and len(phone) == 10):
        flash("Phone must be 10 digits", "danger")
        return redirect(url_for("leave_form"))

    # Calculate leave days
    start = datetime.strptime(period_from, "%Y-%m-%d")
    end = datetime.strptime(period_to, "%Y-%m-%d")
    leave_days = (end - start).days + 1

    username = session["username"]

    # Count monthly used days (excluding On Duty)
    df = read_all_applications()
    month_key = start.strftime("%Y-%m")
    used_days = 0

    for _, row in df.iterrows():
        if (
            row.get("submitted_by_username") == username
            and row.get("status") != "rejected"
            and row.get("period_from", "").startswith(month_key)
            and row.get("nature") != "On Duty"
        ):
            try:
                used_days += int(row.get("leave_days", 0))
            except:
                pass

    remaining = 7 - used_days

    if nature != "On Duty" and leave_days > remaining:
        flash(f"You have only {remaining} leave days left.", "danger")
        return redirect(url_for("leave_form"))

    submitted_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save or update
    if edit_app_no:
        updates = {
            "name": name, "emp_id": emp_id, "gender": gender,
            "designation": designation, "department": department,
            "nature": nature, "period_from": period_from,
            "period_to": period_to, "grounds": grounds,
            "address": address, "phone": phone,
            "submitted_on": submitted_on, "leave_days": leave_days,
            "status": "onprocess"
        }
        update_application_record(edit_app_no, updates)
        application_no = edit_app_no
    else:
        application_no = generate_application_number()
        save_application_to_excel({
            "application_no": application_no,
            "submitted_on": submitted_on,
            "name": name,
            "emp_id": emp_id,
            "gender": gender,
            "designation": designation,
            "department": department,
            "nature": nature,
            "period_from": period_from,
            "period_to": period_to,
            "grounds": grounds,
            "address": address,
            "phone": phone,
            "submitted_by_username": username,
            "status": "onprocess",
            "leave_days": leave_days
        })

    # Data for PDF
    pdf_form = {
        "application_no": application_no,
        "submitted_on": submitted_on,
        "name": name,
        "emp_id": emp_id,
        "gender": gender,
        "designation": designation,
        "department": department,
        "nature": nature,
        "period_from": period_from,
        "period_to": period_to,
        "grounds": grounds,
        "address": address,
        "phone": phone,
        "submitted_by_username": username,
        "leave_days": leave_days,
        "used_days": used_days,
        "remaining_days": remaining - leave_days if nature != "On Duty" else remaining
    }

    pdf = generate_leave_pdf(pdf_form)
    pdf.seek(0)

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"leave_{application_no}.pdf",
        mimetype="application/pdf"
    )


@app.route("/my_applications")
def my_applications():
    if "username" not in session:
        return redirect(url_for("login"))
    df = read_all_applications()
    user_apps = df[df["submitted_by_username"] == session["username"]].fillna("").to_dict(orient="records")
    return render_template("view_applications.html", user_apps=user_apps)


# 🔹 NEW: EDIT ROUTE so url_for('edit_application', app_no=...) works
@app.route("/edit/<app_no>", methods=["GET"])
def edit_application(app_no):
    if "username" not in session:
        return redirect(url_for("login"))

    df = read_all_applications()
    row = df[df["application_no"] == str(app_no)]
    if row.empty:
        flash("Application not found", "danger")
        return redirect(url_for("my_applications"))

    app_rec = row.iloc[0].to_dict()

    # only owner can edit
    if app_rec.get("submitted_by_username") != session["username"]:
        flash("Not authorized to edit this application", "danger")
        return redirect(url_for("my_applications"))

    return render_template(
        "leave_form.html",
        leave_types=LEAVE_TYPES,
        form_data=app_rec
    )


@app.route("/view/<app_no>")
def user_view(app_no):
    if "username" not in session:
        return redirect(url_for("login"))
    df = read_all_applications()
    row = df[df["application_no"] == app_no]
    if row.empty:
        flash("Not found", "danger")
        return redirect(url_for("my_applications"))
    rec = row.iloc[0].to_dict()
    if rec["submitted_by_username"] != session["username"]:
        flash("Not authorized", "danger")
        return redirect(url_for("my_applications"))
    return render_template("user_view.html", app=rec)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/generate_credentials")
def generate_credentials_and_pdf():
    users = [{"username": f"user{i:02d}", "password": f"pass{i:02d}"} for i in range(1, 21)]
    pd.DataFrame(users).to_csv(CREDENTIALS_CSV, index=False)
    flash("Generated credentials.csv", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
