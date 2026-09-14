#!/usr/bin/env python3
"""
Send tickets to a dummy bookings list to verify the send pipeline end-to-end.

This uses your real SMTP credentials from .env (so real emails ARE sent),
but writes to a temporary guests database so your real database/guests.csv
is never touched.

Usage:
  ./.venv/bin/python scripts/test_send_dummy.py you@example.com
  ./.venv/bin/python scripts/test_send_dummy.py you@example.com another@example.com

If no email is given, it defaults to SMTP_USER from .env (mails yourself).
"""
import os
import sys
import tempfile

here = os.path.abspath(os.path.dirname(__file__))
repo_root = os.path.abspath(os.path.join(here, ".."))
if repo_root not in sys.path:
	sys.path.insert(0, repo_root)


def _load_dotenv():
	dotenv_path = os.path.join(repo_root, ".env")
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


_load_dotenv()

from src.core import send_tickets, check_config, guests_csv_path  # noqa: E402


def main():
	recipients = sys.argv[1:] or [check_config("SMTP_USER=")]
	recipients = [r for r in recipients if r]
	if not recipients:
		print("[!] No recipient email given and SMTP_USER is not set in .env.")
		sys.exit(1)

	dummy_csv_lines = ["buyer_email,full_name,payment,table,baby_kid"]
	for index, email in enumerate(recipients, start=1):
		dummy_csv_lines.append("%s,Dummy Guest %s,paid,g%s,no" % (email, index, index))
	dummy_csv_text = "\n".join(dummy_csv_lines) + "\n"

	with tempfile.TemporaryDirectory() as tmp_dir:
		bookings_path = os.path.join(tmp_dir, "dummy_bookings.csv")
		with open(bookings_path, "w", encoding="utf-8") as handle:
			handle.write(dummy_csv_text)

		guests_path = os.path.join(tmp_dir, "guests.csv")

		smtp_user = check_config("SMTP_USER=")
		smtp_pass = check_config("SMTP_PASS=")
		smtp_server = check_config("SMTP_SERVER=")
		smtp_port = check_config("SMTP_PORT=")
		qr_host = check_config("QR_HOST=") or "http://localhost"
		event_name = check_config("EVENT_NAME=") or "Test Event"
		template = check_config("TICKET_TEMPLATE=")
		subject = check_config("TICKET_SUBJECT=") or "[TEST] Your ticket for {event}"
		ticket_logo_path = check_config("TICKET_LOGO_PATH=")

		print("[*] Dummy bookings CSV:\n%s" % dummy_csv_text)
		print("[*] Sending via %s:%s as %s ..." % (smtp_server, smtp_port, smtp_user))

		result = send_tickets(
			bookings_path,
			guests_path,
			qr_host,
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
			print("[!] Row %s error: %s" % (line_number, message))
		print(
			"[*] Sent %s email(s), created %s guest(s), %s pending."
			% (result["sent_emails"], result["created_guests"], result["pending"])
		)
		if result["sent_emails"] > 0:
			print("[OK] Check the inbox(es) of: %s" % (", ".join(recipients),))
		else:
			print("[!] Nothing was sent. Check SMTP settings in .env.")


if __name__ == "__main__":
	main()
