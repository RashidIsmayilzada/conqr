###########################################
#
# QRCode Core Library for ConQr
#
###########################################
import csv
import hashlib
import html
import io
import os
import random
import re
import shutil
import smtplib
import textwrap
import urllib.error
import urllib.request
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders as Encoders
from urllib.parse import parse_qs

from src.qrcode import QRCode, QRErrorCorrectLevel

definepath = os.getcwd()

GUEST_FIELDNAMES = [
	"qr_code",
	"buyer_email",
	"full_name",
	"payment",
	"table",
	"baby_kid",
	"emailed",
	"checked_in",
	"checked_in_at",
]
BOOKING_FIELDNAMES = ["buyer_email", "full_name", "payment", "table", "baby_kid"]
VALID_PAYMENT = {"paid", "pay_at_restaurant"}
VALID_BABY_KID = {"yes", "no"}
PAYMENT_ALIASES = {
	"paid": "paid",
	"pay_at_restaurant": "pay_at_restaurant",
	"pay at restaurant": "pay_at_restaurant",
	"pay in restaurant": "pay_at_restaurant",
	"unpaid": "pay_at_restaurant",
	"odenilib": "paid",
	"\u00f6d\u0259nilib": "paid",
	"restoranda odenish": "pay_at_restaurant",
	"restoranda \u00f6d\u0259ni\u015f": "pay_at_restaurant",
}
BABY_KID_ALIASES = {
	"yes": "yes",
	"y": "yes",
	"true": "yes",
	"no": "no",
	"n": "no",
	"false": "no",
}

# Column headers used by the Google Form response sheet, mapped to the internal
# booking field names. Keys are matched case-insensitively after stripping
# whitespace. A value of None means the column is ignored (not needed).
HEADER_ALIASES = {
	"timestamp": None,
	"email": "buyer_email",
	"buyer_email": "buyer_email",
	"ad soyad": "full_name",
	"full_name": "full_name",
	"odenish": "payment",
	"\u00f6d\u0259ni\u015f": "payment",
	"payment": "payment",
	"stol nomresi": "table",
	"stol n\u00f6m\u0259si": "table",
	"table": "table",
	"ushag sayi": "baby_kid",
	"u\u015fa\u011f say\u0131": "baby_kid",
	"baby_kid": "baby_kid",
}


def canonical_header(name):
	key = (name or "").strip().lower()
	if key in HEADER_ALIASES:
		return HEADER_ALIASES[key]
	return (name or "").strip()


def normalize_payment(value):
	return PAYMENT_ALIASES.get((value or "").strip().lower())


def normalize_baby_kid(value):
	text = (value or "").strip().lower()
	if text in BABY_KID_ALIASES:
		return BABY_KID_ALIASES[text]
	try:
		count = int(text)
	except ValueError:
		return None
	return "yes" if count > 0 else "no"


class BookingCSVError(Exception):
	pass


class MailError(Exception):
	pass


def check_config(param, base_path=None):
	env_name = (param or "").split("=", 1)[0].strip()
	if env_name:
		env_value = os.environ.get(env_name)
		if env_value not in (None, ""):
			return env_value
	root = base_path if base_path is not None else definepath
	config_path = os.path.join(root, "configuration", "config")
	if not os.path.isfile(config_path):
		return None
	with open(config_path, "r") as fileopen:
		for line in fileopen:
			if line.startswith("#"):
				continue
			if line.startswith(param):
				line = line.rstrip()
				line = line.replace('"', "")
				line = line.replace("'", "")
				parts = line.split("=", 1)
				if len(parts) == 2:
					return parts[1].strip()
	return None


def hash():
	rand_num = random.randrange(5, 9)
	random_data = os.urandom(256)
	return hashlib.md5(random_data).hexdigest()[:rand_num]


def guests_csv_path(base_path=None):
	root = base_path if base_path is not None else definepath
	return os.path.join(root, "database", "guests.csv")


def ensure_guests_csv(path):
	directory = os.path.dirname(path)
	if directory and not os.path.isdir(directory):
		os.makedirs(directory)
	if not os.path.isfile(path):
		with open(path, "w", newline="", encoding="utf-8") as handle:
			writer = csv.DictWriter(handle, fieldnames=GUEST_FIELDNAMES)
			writer.writeheader()


def load_guests(path):
	if not os.path.isfile(path):
		return []
	with open(path, newline="", encoding="utf-8") as handle:
		reader = csv.DictReader(handle)
		guests = []
		for row in reader:
			if not row:
				continue
			guest = {field: (row.get(field) or "").strip() for field in GUEST_FIELDNAMES}
			guests.append(guest)
		return guests


def save_guests(path, guests):
	directory = os.path.dirname(path)
	if directory and not os.path.isdir(directory):
		os.makedirs(directory)
	with open(path, "w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=GUEST_FIELDNAMES)
		writer.writeheader()
		for guest in guests:
			writer.writerow({field: guest.get(field, "") for field in GUEST_FIELDNAMES})


def booking_key(guest):
	return (
		guest["buyer_email"].lower(),
		guest["full_name"],
		guest["payment"],
		guest["table"],
		guest["baby_kid"],
	)


def parse_bookings_text(content):
	if not (content or "").strip():
		return [], []

	reader = csv.DictReader(io.StringIO(content))
	if not reader.fieldnames:
		return [], []

	raw_headers = [(name or "").strip() for name in reader.fieldnames]
	# Map each raw column header (e.g. "Ad Soyad", "Odenish") to the internal
	# field name (e.g. "full_name", "payment"). Unknown headers are ignored.
	header_map = {}
	for raw in raw_headers:
		mapped = canonical_header(raw)
		if mapped:
			header_map[mapped] = raw

	missing = [column for column in BOOKING_FIELDNAMES if column not in header_map]
	if missing:
		raise BookingCSVError("Missing required column: " + ", ".join(missing))

	valid = []
	errors = []
	for line_number, row in enumerate(reader, start=2):
		values = [(row.get(header_map[column]) or "").strip() for column in BOOKING_FIELDNAMES]
		if not any(values):
			continue
		guest = {column: (row.get(header_map[column]) or "").strip() for column in BOOKING_FIELDNAMES}
		if not guest["buyer_email"] or not guest["full_name"]:
			errors.append((line_number, "missing email or name"))
			continue
		payment = normalize_payment(guest["payment"])
		if payment is None:
			errors.append((line_number, "invalid payment"))
			continue
		guest["payment"] = payment
		baby_kid = normalize_baby_kid(guest["baby_kid"])
		if baby_kid is None:
			errors.append((line_number, "invalid baby_kid"))
			continue
		guest["baby_kid"] = baby_kid
		valid.append(guest)
	return valid, errors


def parse_bookings(path):
	if not os.path.isfile(path):
		raise BookingCSVError("Bookings file was not found.")
	with open(path, "r", encoding="utf-8") as handle:
		content = handle.read()
	return parse_bookings_text(content)


def google_sheet_csv_url(url):
	url = (url or "").strip()
	if not url:
		return url
	if "output=csv" in url or "export?format=csv" in url or "format=csv" in url:
		return url
	sheet_id = None
	match = re.search(r"/spreadsheets/d/(?:e/)?([a-zA-Z0-9-_]+)", url)
	if match:
		sheet_id = match.group(1)
	gid = "0"
	gid_match = re.search(r"[?#&]gid=([0-9]+)", url)
	if gid_match:
		gid = gid_match.group(1)
	if sheet_id and sheet_id != "e":
		return "https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s" % (sheet_id, gid)
	return url


def load_bookings(source):
	source = (source or "").strip()
	if source.startswith("http://") or source.startswith("https://"):
		url = google_sheet_csv_url(source)
		request = urllib.request.Request(url, headers={"User-Agent": "ConQR/1.0"})
		try:
			with urllib.request.urlopen(request, timeout=30) as response:
				content = response.read().decode("utf-8-sig")
		except urllib.error.HTTPError as error:
			raise BookingCSVError(
				"Could not download the Google Sheet (HTTP %s). Share it as "
				"'Anyone with the link can view', then try again." % (error.code,)
			)
		except Exception as error:
			raise BookingCSVError("Could not download the online CSV: %s" % (error,))
		return parse_bookings_text(content)
	return parse_bookings(source)


def unsent_bookings(bookings, existing_guests):
	# Duplicate identical rows are extra seats, not one person. Count emailed
	# matches and only send the leftover copies.
	emailed_counts = Counter()
	for guest in existing_guests:
		if guest.get("emailed") == "yes":
			emailed_counts[booking_key(guest)] += 1
	pending = []
	seen = Counter()
	for booking in bookings:
		key = booking_key(booking)
		seen[key] += 1
		if seen[key] > emailed_counts[key]:
			pending.append(booking)
	return pending


def group_by_email(bookings):
	groups = OrderedDict()
	for booking in bookings:
		email = booking["buyer_email"].lower()
		groups.setdefault(email, [])
		groups[email].append(booking)
	return groups


def qr_filename(full_name, index=None):
	safe = re.sub(r"[^\w\-. ]+", "_", full_name, flags=re.UNICODE)
	safe = "_".join(safe.split())
	if not safe:
		safe = "guest"
	if index is None:
		return safe + ".pdf"
	return "%s_%s.pdf" % (safe, index)


def unique_ticket_code(existing_codes):
	while True:
		code = hash() + "-" + hash() + "-" + hash() + "-" + hash()
		if code not in existing_codes:
			return code


def build_qr_url(qr_host, qr_port, code):
	host = (qr_host or "").strip()
	port = str(qr_port or "").strip()
	if not host:
		raise BookingCSVError("QR_HOST is not set. Put the laptop LAN IP or https://your-app.vercel.app in configuration/config.")
	if "://" in host:
		base = host.rstrip("/")
	elif host.endswith(".vercel.app") or ("." in host and not host[0].isdigit()):
		base = "https://%s" % (host.split(":")[0],)
	elif ":" in host:
		base = "http://%s" % (host,)
	elif port and port not in ("80", "443", ""):
		base = "http://%s:%s" % (host, port)
	else:
		base = "http://%s" % (host,)
	return "%s/qrcode?q=%s" % (base, code)


def qr_image(code, qr_host, qr_port):
	url = build_qr_url(qr_host, qr_port, code)
	qr = QRCode(5, QRErrorCorrectLevel.L)
	qr.addData(url)
	qr.make()
	return qr.makeImage(), url


def make_qr_image(code, qr_host, qr_port, dest_path):
	image, url = qr_image(code, qr_host, qr_port)
	image.save(dest_path, format="png")
	return url


def resolve_ticket_logo(logo_path):
	path = (logo_path or "").strip()
	if not path:
		return None
	if os.path.isfile(path):
		return path
	rooted = os.path.join(definepath, path)
	if os.path.isfile(rooted):
		return rooted
	return None


_UNICODE_FONTS_CACHE = {}


def _resolve_unicode_fonts():
	"""Register DejaVu Sans (bundled in assets/fonts) with reportlab so
	Azerbaijani characters (ə, ş, ö, ü, ğ, ı) render correctly. Falls back to the
	built-in Helvetica fonts (which cannot render those characters) if the
	bundled TTF files are missing."""
	if "regular" in _UNICODE_FONTS_CACHE:
		return _UNICODE_FONTS_CACHE["regular"], _UNICODE_FONTS_CACHE["bold"]

	try:
		from reportlab.pdfbase import pdfmetrics
		from reportlab.pdfbase.ttfonts import TTFont
	except ImportError:
		_UNICODE_FONTS_CACHE["regular"] = "Helvetica"
		_UNICODE_FONTS_CACHE["bold"] = "Helvetica-Bold"
		return "Helvetica", "Helvetica-Bold"

	here = os.path.abspath(os.path.dirname(__file__))
	candidates = [
		os.path.join(here, "..", "assets", "fonts"),
		os.path.join(here, "..", "..", "assets", "fonts"),
		os.path.join(here, "..", "..", "..", "assets", "fonts"),
	]
	regular_name = "Helvetica"
	bold_name = "Helvetica-Bold"
	for candidate in candidates:
		regular_path = os.path.join(candidate, "DejaVuSans.ttf")
		bold_path = os.path.join(candidate, "DejaVuSans-Bold.ttf")
		if os.path.isfile(regular_path) and os.path.isfile(bold_path):
			try:
				pdfmetrics.registerFont(TTFont("ConQRSans", regular_path))
				pdfmetrics.registerFont(TTFont("ConQRSans-Bold", bold_path))
				regular_name = "ConQRSans"
				bold_name = "ConQRSans-Bold"
			except Exception:
				regular_name = "Helvetica"
				bold_name = "Helvetica-Bold"
			break

	_UNICODE_FONTS_CACHE["regular"] = regular_name
	_UNICODE_FONTS_CACHE["bold"] = bold_name
	return regular_name, bold_name


def _draw_logo_fallback(canvas, event_name, x, y, width, height):
	_, bold_font = _resolve_unicode_fonts()
	initials = "".join(word[:1].upper() for word in (event_name or "Event").split()[:2]) or "E"
	radius = min(width, height) / 2.2
	center_x = x + width / 2
	center_y = y + height / 2
	canvas.setFillColorRGB(0.06, 0.23, 0.27)
	canvas.circle(center_x, center_y, radius, stroke=0, fill=1)
	canvas.setFillColorRGB(1, 1, 1)
	canvas.setFont(bold_font, max(18, min(26, height * 0.35)))
	canvas.drawCentredString(center_x, center_y - 8, initials)


def make_ticket_pdf(code, qr_host, qr_port, dest_path, guest=None, event_name="the event", logo_path=None):
	try:
		from reportlab.lib.colors import HexColor, white
		from reportlab.lib.units import mm
		from reportlab.lib.utils import ImageReader
		from reportlab.pdfgen import canvas as pdf_canvas
	except ImportError:
		raise MailError("PDF ticket generation requires reportlab. Install the updated requirements.txt.")

	guest = guest or {}
	regular_font, bold_font = _resolve_unicode_fonts()
	image, url = qr_image(code, qr_host, qr_port)
	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	buffer.seek(0)
	qr_reader = ImageReader(buffer)

	width = 210 * mm
	height = 99 * mm
	pdf = pdf_canvas.Canvas(dest_path, pagesize=(width, height))

	background = HexColor("#FBF7F0")
	panel = white
	primary = HexColor("#0F3D3E")
	accent = HexColor("#C9A227")
	muted = HexColor("#6B6B6B")
	text_dark = HexColor("#1F2421")
	alert = HexColor("#B3541E")

	header_height = 24 * mm
	margin = 10 * mm
	header_gap = margin
	header_y = height - header_height
	panel_top = header_y - header_gap
	panel_bottom = margin
	panel_left = margin
	panel_right = width - margin
	panel_height = panel_top - panel_bottom

	# Background and header band
	pdf.setFillColor(background)
	pdf.rect(0, 0, width, height, stroke=0, fill=1)
	pdf.setFillColor(primary)
	pdf.rect(0, header_y, width, header_height, stroke=0, fill=1)
	pdf.setFillColor(accent)
	pdf.rect(0, height - 2.2 * mm, width, 2.2 * mm, stroke=0, fill=1)

	# Logo
	logo_x = margin
	logo_y = header_y + (header_height - 16 * mm) / 2
	logo_width = 26 * mm
	logo_height = 16 * mm
	resolved_logo = resolve_ticket_logo(logo_path)
	if resolved_logo and os.path.splitext(resolved_logo)[1].lower() in {".png", ".jpg", ".jpeg"}:
		try:
			pdf.drawImage(resolved_logo, logo_x, logo_y, width=logo_width, height=logo_height, mask="auto", preserveAspectRatio=True, anchor="w")
		except Exception:
			_draw_logo_fallback(pdf, event_name, logo_x, logo_y, logo_width, logo_height)
	else:
		_draw_logo_fallback(pdf, event_name, logo_x, logo_y, logo_width, logo_height)

	# Event name / subtitle, vertically centered in the header band
	text_x = logo_x + logo_width + 8 * mm
	header_center_y = header_y + header_height / 2
	pdf.setFillColor(white)
	pdf.setFont(bold_font, 17)
	pdf.drawString(text_x, header_center_y + 3 * mm, textwrap.shorten(event_name or "the event", width=30, placeholder="..."))
	pdf.setFont(regular_font, 9)
	pdf.drawString(text_x, header_center_y - 5.5 * mm, "GİRİŞ BİLETİ")

	# Unpaid badge, top-right of header
	if guest.get("payment") != "paid":
		badge_w = 46 * mm
		badge_h = 9 * mm
		badge_x = panel_right - badge_w
		badge_y = header_y + (header_height - badge_h) / 2
		pdf.setFillColor(alert)
		pdf.roundRect(badge_x, badge_y, badge_w, badge_h, 4 * mm, stroke=0, fill=1)
		pdf.setFillColor(white)
		pdf.setFont(bold_font, 9)
		pdf.drawCentredString(badge_x + badge_w / 2, badge_y + 3 * mm, "RESTORANDA ÖDƏNİŞ")

	# Body panel
	pdf.setFillColor(panel)
	pdf.roundRect(panel_left, panel_bottom, panel_right - panel_left, panel_height, 5 * mm, stroke=0, fill=1)
	pdf.setStrokeColor(accent)
	pdf.setLineWidth(1)
	pdf.roundRect(panel_left, panel_bottom, panel_right - panel_left, panel_height, 5 * mm, stroke=1, fill=0)

	inner_pad = 8 * mm
	left_x = panel_left + inner_pad
	column_divider_x = panel_left + 122 * mm
	right_x = column_divider_x + 8 * mm

	# Guest name
	name_baseline = panel_top - 13 * mm
	pdf.setFillColor(text_dark)
	pdf.setFont(bold_font, 19)
	pdf.drawString(left_x, name_baseline, textwrap.shorten(guest.get("full_name") or "Guest", width=28, placeholder="..."))

	# Divider under name
	divider_y = name_baseline - 5 * mm
	pdf.setStrokeColor(HexColor("#E5DCC8"))
	pdf.setLineWidth(0.8)
	pdf.line(left_x, divider_y, column_divider_x - 6 * mm, divider_y)

	# Detail grid: 2 columns x 2 rows
	payment = "Paid" if guest.get("payment") == "paid" else "Pay at restaurant"
	kid = "Yes" if guest.get("baby_kid") == "yes" else "No"
	grid = [
		[("Stol", guest.get("table") or "-"), ("Ödəniş", payment)],
		[("Uşaq", kid), ("Bilet kodu", code)],
	]
	col_width = (column_divider_x - 6 * mm - left_x) / 2
	row_height = 15 * mm
	grid_top = divider_y - 6 * mm
	for row_idx, row in enumerate(grid):
		for col_idx, (label, value) in enumerate(row):
			cell_x = left_x + col_idx * col_width
			cell_y = grid_top - row_idx * row_height
			pdf.setFillColor(muted)
			pdf.setFont(bold_font, 7.5)
			pdf.drawString(cell_x, cell_y, label.upper())
			pdf.setFillColor(text_dark)
			pdf.setFont(regular_font, 11.5)
			pdf.drawString(cell_x, cell_y - 5.5 * mm, textwrap.shorten(str(value), width=22, placeholder="..."))

	# Footer note inside left column
	pdf.setFillColor(muted)
	pdf.setFont(regular_font, 7.5)
	pdf.drawString(left_x, panel_bottom + 5 * mm, "Bu bileti (çap edilmiş və ya telefonunuzda) girişdə təqdim edin.")

	# Vertical divider between columns
	pdf.setStrokeColor(HexColor("#E5DCC8"))
	pdf.setLineWidth(0.8)
	pdf.line(column_divider_x, panel_bottom + 6 * mm, column_divider_x, panel_top - 6 * mm)

	# QR code block, centered in right column (both horizontally and vertically
	# within the panel, so it stays balanced regardless of panel height)
	qr_size = 38 * mm
	qr_bg_pad = 4 * mm
	label_gap = 8 * mm
	right_col_width = panel_right - inner_pad - right_x
	qr_x = right_x + (right_col_width - qr_size) / 2
	block_height = qr_bg_pad + qr_size + qr_bg_pad + label_gap
	block_bottom = panel_bottom + (panel_height - block_height) / 2
	qr_y = block_bottom + label_gap + qr_bg_pad
	pdf.setFillColor(HexColor("#FCFAF6"))
	pdf.roundRect(qr_x - qr_bg_pad, qr_y - qr_bg_pad, qr_size + 2 * qr_bg_pad, qr_size + 2 * qr_bg_pad, 4 * mm, stroke=0, fill=1)
	pdf.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")
	pdf.setFillColor(primary)
	pdf.setFont(bold_font, 8.5)
	pdf.drawCentredString(qr_x + qr_size / 2, block_bottom + label_gap / 2 - 1.2 * mm, "GİRİŞDƏ SKAN EDİN")

	pdf.save()
	return url


def create_ticket_attachment(make_image_fn, code, qr_host, qr_port, dest_path, booking, event_name, logo_path):
	try:
		return make_image_fn(
			code,
			qr_host,
			qr_port,
			dest_path,
			guest=booking,
			event_name=event_name,
			logo_path=logo_path,
		)
	except TypeError as error:
		message = str(error)
		if "unexpected keyword argument" not in message and "positional arguments" not in message:
			raise
		return make_image_fn(code, qr_host, qr_port, dest_path)


def format_ticket_email(template, event_name, guests):
	text = (template or "Greetings!\n\nAttached are your ticket PDFs for {event}.").replace("\\n", "\n")
	text = text.replace("{event}", event_name or "the event")
	lines = []
	for guest in guests:
		payment = "paid" if guest["payment"] == "paid" else "pay at restaurant"
		kid = "yes" if guest["baby_kid"] == "yes" else "no"
		lines.append("- %s | stol %s | %s | uşaq: %s" % (guest["full_name"], guest["table"], payment, kid))
	return text.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def mail(to, subject, text, attachments, user, pwd, server, port):
	if isinstance(attachments, str):
		attachments = [attachments]
	msg = MIMEMultipart()
	msg["From"] = user
	msg["To"] = to
	msg["Subject"] = subject
	msg.attach(MIMEText(text))
	for attach in attachments or []:
		part = MIMEBase("application", "octet-stream")
		with open(attach, "rb") as attach_file:
			part.set_payload(attach_file.read())
		Encoders.encode_base64(part)
		part.add_header(
			"Content-Disposition",
			'attachment; filename="%s"' % os.path.basename(attach),
		)
		msg.attach(part)
	mailServer = smtplib.SMTP(server, int(port))
	try:
		mailServer.ehlo()
		mailServer.starttls()
		mailServer.ehlo()
		mailServer.login(user, pwd)
		mailServer.sendmail(user, to, msg.as_string())
	except smtplib.SMTPAuthenticationError:
		raise MailError(
			"Gmail/SMTP login failed. On macOS you must use a Gmail App Password, "
			"not your normal Gmail password. Create one at https://myaccount.google.com/apppasswords "
			"then put it in configuration/config as SMTP_PASS."
		)
	except smtplib.SMTPException as error:
		raise MailError("Could not send email: %s" % (error,))
	finally:
		try:
			mailServer.close()
		except Exception:
			pass


def send_tickets(
	bookings_path,
	guests_path,
	qr_host,
	qr_port="8080",
	event_name="the event",
	subject=None,
	template=None,
	smtp_user=None,
	smtp_pass=None,
	smtp_server=None,
	smtp_port=None,
	mail_fn=None,
	qr_dir=None,
	make_image_fn=None,
	ticket_logo_path=None,
):
	bookings, errors = load_bookings(bookings_path)
	ensure_guests_csv(guests_path)
	existing = load_guests(guests_path)
	pending = unsent_bookings(bookings, existing)
	if mail_fn is None:
		mail_fn = mail
	if make_image_fn is None:
		make_image_fn = make_ticket_pdf
	if subject is None:
		subject = "Your tickets for %s" % (event_name,)
	subject = subject.replace("{event}", event_name or "the event")

	sent_emails = 0
	created_guests = 0
	work_dir = qr_dir or os.path.join(os.path.dirname(guests_path) or ".", "qr_tmp")
	os.makedirs(work_dir, exist_ok=True)
	used_codes = {guest.get("qr_code") for guest in existing if guest.get("qr_code")}

	for email, group in group_by_email(pending).items():
		attachments = []
		prepared = []
		try:
			for index, booking in enumerate(group, start=1):
				code = unique_ticket_code(used_codes)
				used_codes.add(code)
				filename = qr_filename(booking["full_name"], index)
				dest = os.path.join(work_dir, filename)
				create_ticket_attachment(make_image_fn, code, qr_host, qr_port, dest, booking, event_name, ticket_logo_path)
				attachments.append(dest)
				row = {
					"qr_code": code,
					"buyer_email": booking["buyer_email"],
					"full_name": booking["full_name"],
					"payment": booking["payment"],
					"table": booking["table"],
					"baby_kid": booking["baby_kid"],
					"emailed": "yes",
					"checked_in": "no",
					"checked_in_at": "",
				}
				prepared.append(row)
			body = format_ticket_email(template, event_name, prepared)
			mail_fn(
				email,
				subject,
				body,
				attachments,
				smtp_user,
				smtp_pass,
				smtp_server,
				smtp_port,
			)
			existing.extend(prepared)
			save_guests(guests_path, existing)
			sent_emails += 1
			created_guests += len(prepared)
		finally:
			for path in attachments:
				try:
					os.remove(path)
				except OSError:
					pass

	return {
		"sent_emails": sent_emails,
		"created_guests": created_guests,
		"errors": errors,
		"pending": len(pending),
	}


def publish_guests_for_web(guests_path):
	dest = os.path.abspath(os.path.join(os.path.dirname(guests_path), "..", "..", "..", "web", "data", "guests.csv"))
	directory = os.path.dirname(dest)
	if os.path.isdir(directory):
		shutil.copy(guests_path, dest)
		return dest
	return None


def sync_guests_to_cloud(guests_path, url, secret):
	if not url or not secret:
		return
	with open(guests_path, "rb") as handle:
		body = handle.read()
	request = urllib.request.Request(
		url,
		data=body,
		method="POST",
		headers={
			"Authorization": "Bearer %s" % (secret,),
			"Content-Type": "text/csv; charset=utf-8",
		},
	)
	urllib.request.urlopen(request, timeout=30)


def extract_qr_code(query):
	params = parse_qs(query or "", keep_blank_values=True)
	values = params.get("q")
	if values:
		return values[0].strip()
	return ""


def find_guest_by_code(guests, qr_code):
	if not qr_code:
		return None
	for guest in guests:
		if guest.get("qr_code") == qr_code:
			return guest
	return None


def _now_stamp():
	return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def render_checkin_page(status, guest=None):
	if status == "ok":
		banner_class = "ok"
		banner = "Checked in"
	elif status == "already":
		banner_class = "already"
		banner = "Already checked in"
	else:
		banner_class = "notfound"
		banner = "Ticket not found"

	rows = ""
	unpaid = ""
	if guest:
		payment_label = "paid" if guest.get("payment") == "paid" else "pay at restaurant"
		if guest.get("payment") != "paid":
			unpaid = '<div class="unpaid">PAY AT RESTAURANT</div>'
		kid = "yes" if guest.get("baby_kid") == "yes" else "no"
		checked_at = guest.get("checked_in_at") or ""
		rows = """
<div class="name">%s</div>
<div class="row"><span>Table</span> %s</div>
<div class="row"><span>Payment</span> %s</div>
<div class="row"><span>Baby / kid</span> %s</div>
<div class="row"><span>Buyer email</span> %s</div>
<div class="row"><span>Checked in at</span> %s</div>
""" % (
			html.escape(guest.get("full_name") or ""),
			html.escape(guest.get("table") or ""),
			html.escape(payment_label),
			html.escape(kid),
			html.escape(guest.get("buyer_email") or ""),
			html.escape(checked_at),
		)

	return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Check-in</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; background: #111; color: #fff; }
.banner { padding: 16px; font-size: 1.6rem; font-weight: 700; border-radius: 8px; margin-bottom: 16px; }
.ok { background: #16a34a; }
.already { background: #d97706; color: #111; }
.notfound { background: #dc2626; }
.unpaid { background: #ea580c; padding: 14px; font-size: 1.4rem; font-weight: 800; border-radius: 8px; margin-bottom: 16px; letter-spacing: 0.04em; }
.name { font-size: 2.2rem; font-weight: 800; margin: 12px 0 20px; }
.row { font-size: 1.25rem; margin: 10px 0; line-height: 1.4; }
.row span { display: block; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #a3a3a3; }
</style>
</head>
<body>
<div class="banner %s">%s</div>
%s
%s
</body>
</html>
""" % (banner_class, html.escape(banner), unpaid, rows)


def render_home_page():
	return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scanner ready</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 24px; background: #111; color: #fff; }
h1 { font-size: 1.8rem; }
p { font-size: 1.15rem; line-height: 1.5; color: #d4d4d4; }
</style>
</head>
<body>
<h1>Scanner ready</h1>
<p>Scan a guest QR code with this phone. Guest name, table, payment, and baby/kid details will show on the next screen and stay there.</p>
</body>
</html>
"""


def notify_sheet_checkin(guest, url=None, secret=None):
	"""Best-effort push of a check-in event to a Google Apps Script Web App
	bound to the booking sheet, so the sheet itself shows Checked In /
	Checked In At for that guest. Configured via SHEET_CHECKIN_URL and
	SHEET_CHECKIN_SECRET (env or configuration/config). Any failure here is
	swallowed (printed as a warning) so a flaky network never blocks the
	door scanner from checking someone in locally."""
	url = url if url is not None else check_config("SHEET_CHECKIN_URL=")
	secret = secret if secret is not None else check_config("SHEET_CHECKIN_SECRET=")
	if not url or not secret:
		return
	try:
		import json

		payload = json.dumps({
			"secret": secret,
			"email": guest.get("buyer_email", ""),
			"full_name": guest.get("full_name", ""),
			"checked_in_at": guest.get("checked_in_at", ""),
		}).encode("utf-8")
		request = urllib.request.Request(
			url,
			data=payload,
			method="POST",
			headers={"Content-Type": "application/json"},
		)
		urllib.request.urlopen(request, timeout=15)
	except Exception as error:
		print("[!] Could not update the Google Sheet check-in status: %s" % (error,))


def check_in(qr_code, guests_path):
	guests = load_guests(guests_path)
	guest = find_guest_by_code(guests, qr_code)
	if guest is None:
		return {
			"status": "not_found",
			"guest": None,
			"html": render_checkin_page("not_found"),
		}
	if guest.get("checked_in") == "yes":
		return {
			"status": "already",
			"guest": guest,
			"html": render_checkin_page("already", guest),
		}
	guest["checked_in"] = "yes"
	guest["checked_in_at"] = _now_stamp()
	save_guests(guests_path, guests)
	notify_sheet_checkin(guest)
	return {
		"status": "ok",
		"guest": guest,
		"html": render_checkin_page("ok", guest),
	}


def gen_qrcode(user, con_name, option):
	qrcode = unique_ticket_code(set())
	qr = QRCode(5, QRErrorCorrectLevel.L)
	qr.addData("http://%s/qrcode?q=%s" % (con_name, qrcode))
	qr.make()
	im = qr.makeImage()
	im.save("qrcode.png", format="png")
	if not os.path.isfile("database/conference.txt"):
		with open("database/conference.txt", "w") as filewrite:
			filewrite.write("")
	if option == "1":
		option = "ATTENDEE"
	if option == "2":
		option = "SPEAKER"
	if option == "3":
		option = "SPONSOR"
	with open("database/conference.txt", "a") as filewrite:
		filewrite.write(qrcode + "," + user + "," + option + "\n")
	return qrcode
