#
#
# ConQR - Restaurant event QR ticketing
# Written by: David Kennedy
# Twitter: @HackingDave @TrustedSec
# Website: https://www.trustedsec.com
#
#
import os
import subprocess
import sys
import time


def _load_dotenv():
	here = os.path.abspath(os.path.dirname(__file__))
	root = os.path.abspath(os.path.join(here, ".."))
	dotenv_path = os.path.join(root, ".env")
	if not os.path.isfile(dotenv_path):
		return
	with open(dotenv_path, "r", encoding="utf-8") as handle:
		for raw_line in handle:
			line = raw_line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			key = key.strip()
			if not key or key in os.environ:
				continue
			value = value.strip().strip('"').strip("'")
			os.environ[key] = value


def _bootstrap_pillow():
	"""Homebrew python3 has no Pillow; re-run inside the project venv."""
	if os.environ.get("CONQR_BOOTSTRAPPED") == "1":
		return
	try:
		import PIL  # noqa: F401
		return
	except ImportError:
		pass

	here = os.path.abspath(os.path.dirname(__file__))
	candidates = [
		os.path.join(here, ".venv", "bin", "python"),
		os.path.join(here, "..", ".venv", "bin", "python"),
		os.path.join(here, "..", "..", ".venv", "bin", "python"),
	]
	venv_python = None
	for path in candidates:
		path = os.path.abspath(path)
		if os.path.isfile(path):
			venv_python = path
			break

	if venv_python is None:
		repo = os.path.abspath(os.path.join(here, "..", ".."))
		if not os.path.isfile(os.path.join(repo, "requirements.txt")):
			repo = os.path.abspath(os.path.join(here, ".."))
		venv_dir = os.path.join(repo, ".venv")
		venv_python = os.path.join(venv_dir, "bin", "python")
		print("[*] Pillow is missing. Creating %s and installing Pillow..." % (venv_dir,))
		subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
		pip = os.path.join(venv_dir, "bin", "pip")
		req = os.path.join(repo, "requirements.txt")
		if os.path.isfile(req):
			subprocess.check_call([pip, "install", "-r", req])
		else:
			subprocess.check_call([pip, "install", "Pillow"])

	os.environ["CONQR_BOOTSTRAPPED"] = "1"
	os.execv(venv_python, [venv_python] + sys.argv)


_load_dotenv()
_bootstrap_pillow()

from src.core import *

USAGE = """  ,----..                           ,----..
 /   /   \\                         /   /   \\
|   :     :  ,---.        ,---,   /   .     :    __  ,-.
.   |  ;. / '   ,'\\   ,-+-. /  | .   /   ;.  \\ ,' ,'/ /|
.   ; /--` /   /   | ,--.'|'   |.   ;   /  ` ; '  | |' |
;   | ;   .   ; ,. :|   |  ,"' |;   |  ; \\ ; | |  |   ,'
|   : |   '   | |: :|   | /  | ||   :  | ; | ' '  :  /
.   | '___'   | .; :|   | |  | |.   |  ' ' ' : |  | '
'   ; : .'|   :    ||   | |  |/ '   ;  \\; /  | ;  : |
'   | '/  :\\   \\  / |   | |--'   \\   \\  ',  . \\|  , ;
|   :    /  `----'  |   |/        ;   :      ; |---'
 \\   \\ .'           '---'          \\   \\ .'`--"
  `---`                             `---`
ConQR - Restaurant event QR tickets

Options:

send <bookings.csv|sheet-url>   Email unique QR tickets (one QR per guest)
watch <bookings.csv|sheet-url>  Poll for new rows and email only new guests
4                     Start the QRCode Server for check-in (includes DNS server)

Bookings CSV columns:

buyer_email,full_name,payment,table,baby_kid

payment must be paid or pay_at_restaurant
baby_kid must be yes or no
One row per person. Same buyer_email on several rows sends several QRs to that inbox.

Usage:
  python conqr.py send bookings.csv
  python conqr.py send
  python conqr.py watch
  python conqr.py watch bookings.csv
  python conqr.py 4

If you omit the file, BOOKINGS_URL in configuration/config is used (Google Sheet CSV).
"""


def resolve_source(filename):
	source = filename or check_config("BOOKINGS_URL=")
	is_url = bool(source) and source.startswith(("http://", "https://"))
	if not source or (not is_url and not os.path.isfile(source)):
		raise BookingCSVError(
			"Provide a bookings.csv path, a Google Sheet URL, or set BOOKINGS_URL in configuration/config."
		)
	return source


def sync_checkin_copy(guests_path):
	publish_guests_for_web(guests_path)
	sync_url = check_config("CHECKIN_SYNC_URL=")
	sync_secret = check_config("CHECKIN_SYNC_SECRET=")
	if sync_url and sync_secret:
		try:
			sync_guests_to_cloud(guests_path, sync_url, sync_secret)
			print("[*] Updated the online check-in list.")
		except Exception as error:
			print("[!] Could not update the online check-in list: %s" % (error,))


def send_once(source):
	smtp_user = check_config("SMTP_USER=")
	smtp_pass = check_config("SMTP_PASS=")
	smtp_server = check_config("SMTP_SERVER=")
	smtp_port = check_config("SMTP_PORT=")
	qr_host = os.environ.get("CONQR_IP") or check_config("QR_HOST=")
	qr_port = os.environ.get("CONQR_PORT") or check_config("QR_PORT=") or "8080"
	event_name = check_config("EVENT_NAME=") or check_config("CONFERENCE_FOLDER=") or "the event"
	template = check_config("TICKET_TEMPLATE=")
	subject = check_config("TICKET_SUBJECT=")
	ticket_logo_path = check_config("TICKET_LOGO_PATH=")
	result = send_tickets(
		source,
		guests_csv_path(),
		qr_host,
		qr_port=qr_port,
		event_name=event_name,
		subject=subject,
		template=template,
		smtp_user=smtp_user,
		smtp_pass=smtp_pass,
		smtp_server=smtp_server,
		smtp_port=smtp_port,
		ticket_logo_path=ticket_logo_path,
	)
	for line_number, message in result["errors"]:
		print("[!] Skipping row %s: %s" % (line_number, message))
	print("[*] Sent %s email(s), created %s ticket(s)." % (result["sent_emails"], result["created_guests"]))
	if result["pending"] == 0 and not result["errors"]:
		print("[*] Nothing new to send (already emailed, or the CSV was empty).")
	sync_checkin_copy(guests_csv_path())
	return result


def poll_seconds():
	value = os.environ.get("BOOKINGS_POLL_SECONDS") or check_config("BOOKINGS_POLL_SECONDS=") or "15"
	try:
		seconds = int(value)
	except ValueError:
		raise BookingCSVError("BOOKINGS_POLL_SECONDS must be a whole number.")
	if seconds < 5:
		raise BookingCSVError("BOOKINGS_POLL_SECONDS must be at least 5 seconds.")
	return seconds

try:
	option = sys.argv[1]
except IndexError:
	print(USAGE)
	sys.exit()

filename = sys.argv[2] if len(sys.argv) > 2 else None

try:
	if option == "4":
		print("Launching the QRCode Server...")
		import src.qrcode_server
		sys.exit()

	if option == "send":
		source = resolve_source(filename)
		print("[*] Sending tickets from %s ..." % (source,))
		send_once(source)
		sys.exit(0)

	if option == "watch":
		source = resolve_source(filename)
		interval = poll_seconds()
		print("[*] Watching %s for new rows every %s seconds..." % (source, interval))
		while True:
			try:
				send_once(source)
			except KeyboardInterrupt:
				raise
			except Exception as error:
				print("[!] Watch cycle failed: %s" % (error,))
			time.sleep(interval)
		sys.exit(0)

	print(USAGE)
	sys.exit(1)

except KeyboardInterrupt:
	print("[*] Okay, exiting out, you got it. Thanks for using ConQR..")

except BookingCSVError as e:
	print("[!] %s" % (e,))
	sys.exit(1)

except MailError as e:
	print("[!] %s" % (e,))
	sys.exit(1)

except Exception as e:
	print("Something went wrong! Printing the error: " + str(e))
	sys.exit(1)
