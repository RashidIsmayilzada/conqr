from pathlib import Path

import pytest

from src.core import (
	build_qr_url,
	load_guests,
	send_tickets,
)


def write_bookings(path, rows):
	path.write_text(
		"buyer_email,full_name,payment,table,baby_kid\n" + "\n".join(rows) + "\n",
		encoding="utf-8",
	)


def fake_image(code, host, port, dest):
	Path(dest).write_bytes(b"%PDF-1.4")
	return build_qr_url(host, port, code)


def send(tmp_path, rows, existing=None, mail_fn=None, **kwargs):
	bookings = tmp_path / "bookings.csv"
	write_bookings(bookings, rows)
	guests = tmp_path / "database" / "guests.csv"
	guests.parent.mkdir(parents=True, exist_ok=True)
	if existing:
		guests.write_text(existing, encoding="utf-8")
	sent = []

	def capture_mail(to, subject, text, attachments, user, pwd, server, port):
		sent.append(
			{
				"to": to,
				"subject": subject,
				"text": text,
				"attachments": list(attachments),
				"names": [Path(path).name for path in attachments],
			}
		)

	result = send_tickets(
		str(bookings),
		str(guests),
		qr_host="192.168.1.20",
		qr_port="8080",
		event_name="Saturday dinner",
		mail_fn=mail_fn or capture_mail,
		make_image_fn=fake_image,
		qr_dir=str(tmp_path / "qr_tmp"),
		**kwargs,
	)
	return result, sent, guests


def test_one_guest_one_email_one_attachment(tmp_path):
	result, sent, guests = send(tmp_path, ["a@x.com,Anna,paid,1,no"])
	assert result["sent_emails"] == 1
	assert result["created_guests"] == 1
	assert sent[0]["to"] == "a@x.com"
	assert len(sent[0]["attachments"]) == 1
	assert sent[0]["names"][0].endswith(".pdf")
	loaded = load_guests(str(guests))
	assert loaded[0]["emailed"] == "yes"
	assert loaded[0]["qr_code"]


def test_five_guests_one_email(tmp_path):
	rows = ["anna@x.com,Guest %s,paid,12,no" % (i,) for i in range(1, 6)]
	result, sent, guests = send(tmp_path, rows)
	assert result["sent_emails"] == 1
	assert result["created_guests"] == 5
	assert len(sent[0]["attachments"]) == 5
	assert all(name.endswith(".pdf") for name in sent[0]["names"])
	codes = [row["qr_code"] for row in load_guests(str(guests))]
	assert len(codes) == len(set(codes))
	assert all(row["buyer_email"] == "anna@x.com" for row in load_guests(str(guests)))


def test_two_buyers_two_emails(tmp_path):
	result, sent, _ = send(
		tmp_path,
		["a@x.com,Anna,paid,1,no", "b@x.com,Bob,paid,2,no"],
	)
	assert result["sent_emails"] == 2
	assert {item["to"] for item in sent} == {"a@x.com", "b@x.com"}
	assert all(len(item["attachments"]) == 1 for item in sent)


def test_rerun_skips_already_emailed(tmp_path):
	rows = ["a@x.com,Anna,paid,1,no"]
	send(tmp_path, rows)
	result, sent, guests = send(tmp_path, rows)
	assert result["sent_emails"] == 0
	assert result["created_guests"] == 0
	assert sent == []
	assert len(load_guests(str(guests))) == 1


def test_new_guest_later_for_same_buyer(tmp_path):
	send(tmp_path, ["a@x.com,Anna,paid,1,no"])
	result, sent, guests = send(tmp_path, ["a@x.com,Anna,paid,1,no", "a@x.com,Bob,paid,1,no"])
	assert result["sent_emails"] == 1
	assert result["created_guests"] == 1
	assert "Bob" in sent[0]["text"]
	assert "Anna" not in sent[0]["text"]
	names = [row["full_name"] for row in load_guests(str(guests))]
	assert names == ["Anna", "Bob"]


def test_smtp_failure_does_not_mark_group(tmp_path):
	def boom(*args, **kwargs):
		raise OSError("smtp down")

	with pytest.raises(OSError):
		send(tmp_path, ["a@x.com,A,paid,1,no", "a@x.com,B,paid,1,no"], mail_fn=boom)
	guests = tmp_path / "database" / "guests.csv"
	assert load_guests(str(guests)) == []


def test_qr_url_uses_lan_host_not_folder_name():
	url = build_qr_url("192.168.1.20", "8080", "abc-def")
	assert url == "http://192.168.1.20:8080/qrcode?q=abc-def"
	assert "saturdaydinner" not in url
	assert build_qr_url("10.0.0.5", "80", "zz") == "http://10.0.0.5/qrcode?q=zz"


def test_twins_distinct_qrs(tmp_path):
	result, sent, guests = send(
		tmp_path,
		["a@x.com,Alex,paid,3,no", "a@x.com,Alex,paid,3,no"],
	)
	assert result["created_guests"] == 2
	codes = [row["qr_code"] for row in load_guests(str(guests))]
	assert codes[0] != codes[1]
	assert len(sent[0]["attachments"]) == 2


def test_split_tables_same_email(tmp_path):
	_, sent, guests = send(
		tmp_path,
		["a@x.com,Anna,paid,1,no", "a@x.com,Bob,paid,8,no"],
	)
	assert len(sent) == 1
	loaded = load_guests(str(guests))
	assert {row["table"] for row in loaded} == {"1", "8"}


def test_mixed_payment_in_one_group(tmp_path):
	_, sent, guests = send(
		tmp_path,
		["a@x.com,Anna,paid,1,no", "a@x.com,Bob,pay_at_restaurant,1,no"],
	)
	text = sent[0]["text"]
	assert "paid" in text
	assert "pay at restaurant" in text
	payments = {row["payment"] for row in load_guests(str(guests))}
	assert payments == {"paid", "pay_at_restaurant"}


def test_invalid_row_skipped_valid_still_sent(tmp_path):
	result, sent, guests = send(
		tmp_path,
		["a@x.com,Anna,paid,1,no", "b@x.com,Bob,cash,1,no"],
	)
	assert result["errors"]
	assert result["created_guests"] == 1
	assert load_guests(str(guests))[0]["full_name"] == "Anna"


def test_unique_codes_across_emails(tmp_path):
	_, _, guests = send(
		tmp_path,
		["a@x.com,Anna,paid,1,no", "b@x.com,Bob,paid,2,no", "c@x.com,Cara,paid,3,yes"],
	)
	codes = [row["qr_code"] for row in load_guests(str(guests))]
	assert len(codes) == len(set(codes))
