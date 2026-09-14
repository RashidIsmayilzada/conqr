from pathlib import Path

import pytest

from src.core import (
	BookingCSVError,
	google_sheet_csv_url,
	load_bookings,
	parse_bookings,
	qr_filename,
	unsent_bookings,
)


FIXTURE = Path(__file__).parent / "fixtures" / "bookings_ok.csv"


def write_csv(path, header, rows):
	with open(path, "w", newline="", encoding="utf-8") as handle:
		handle.write(header + "\n")
		for row in rows:
			handle.write(row + "\n")


def test_header_only_sends_nothing(tmp_path):
	path = tmp_path / "bookings.csv"
	path.write_text("buyer_email,full_name,payment,table,baby_kid\n", encoding="utf-8")
	bookings, errors = parse_bookings(str(path))
	assert bookings == []
	assert errors == []


def test_empty_file_no_crash(tmp_path):
	path = tmp_path / "bookings.csv"
	path.write_text("", encoding="utf-8")
	bookings, errors = parse_bookings(str(path))
	assert bookings == []
	assert errors == []


def test_missing_required_column(tmp_path):
	path = tmp_path / "bookings.csv"
	path.write_text("buyer_email,full_name,table,baby_kid\n", encoding="utf-8")
	with pytest.raises(BookingCSVError) as err:
		parse_bookings(str(path))
	assert "payment" in str(err.value)


def test_blank_row_skipped(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"buyer_email,full_name,payment,table,baby_kid",
		["anna@x.com,Anna,paid,1,no", ",,,,", "bob@x.com,Bob,paid,1,no"],
	)
	bookings, errors = parse_bookings(str(path))
	assert errors == []
	assert [row["full_name"] for row in bookings] == ["Anna", "Bob"]


def test_missing_email_or_name_rejected(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"buyer_email,full_name,payment,table,baby_kid",
		[",Anna,paid,1,no", "anna@x.com,,paid,1,no"],
	)
	bookings, errors = parse_bookings(str(path))
	assert bookings == []
	assert len(errors) == 2
	assert all("missing email or name" in message for _, message in errors)


def test_sheet_aliases_paid_and_baby_one(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"buyer_email,full_name,payment,table,baby_kid",
		["a@x.com,A,Paid,g11,1"],
	)
	bookings, errors = parse_bookings(str(path))
	assert errors == []
	assert bookings[0]["payment"] == "paid"
	assert bookings[0]["baby_kid"] == "yes"
	assert bookings[0]["table"] == "g11"


def test_invalid_payment_and_baby_kid(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"buyer_email,full_name,payment,table,baby_kid",
		["a@x.com,A,cash,1,no", "b@x.com,B,paid,1,maybe"],
	)
	bookings, errors = parse_bookings(str(path))
	assert bookings == []
	assert errors[0][1] == "invalid payment"
	assert errors[1][1] == "invalid baby_kid"


def test_quoted_comma_in_name(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"buyer_email,full_name,payment,table,baby_kid",
		['anna@x.com,"Smith, Anna",paid,12,no'],
	)
	bookings, errors = parse_bookings(str(path))
	assert errors == []
	assert bookings[0]["full_name"] == "Smith, Anna"


def test_unicode_and_unsafe_filename():
	assert ".." not in qr_filename("José / Álvarez: kid")
	assert "/" not in qr_filename("a/b\\c:d")
	assert qr_filename("Anna Smith") == "Anna_Smith.pdf"
	assert qr_filename("Anna Smith", 2) == "Anna_Smith_2.pdf"


def test_whitespace_stripped(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"buyer_email,full_name,payment,table,baby_kid",
		["  anna@x.com  ,  Anna Smith  ,  PAID  ,  12  ,  NO  "],
	)
	bookings, errors = parse_bookings(str(path))
	assert errors == []
	assert bookings[0]["buyer_email"] == "anna@x.com"
	assert bookings[0]["full_name"] == "Anna Smith"
	assert bookings[0]["payment"] == "paid"
	assert bookings[0]["table"] == "12"
	assert bookings[0]["baby_kid"] == "no"


def test_identical_rows_are_two_seats():
	bookings = [
		{"buyer_email": "a@x.com", "full_name": "A", "payment": "paid", "table": "1", "baby_kid": "no"},
		{"buyer_email": "a@x.com", "full_name": "A", "payment": "paid", "table": "1", "baby_kid": "no"},
	]
	pending = unsent_bookings(bookings, [])
	assert len(pending) == 2


def test_fixture_parses():
	bookings, errors = parse_bookings(str(FIXTURE))
	assert errors == []
	assert len(bookings) == 4


def test_google_sheet_edit_url_becomes_csv_export():
	url = google_sheet_csv_url("https://docs.google.com/spreadsheets/d/abc123XYZ/edit?gid=7#gid=7")
	assert url == "https://docs.google.com/spreadsheets/d/abc123XYZ/export?format=csv&gid=7"


def test_google_sheet_csv_url_left_alone():
	raw = "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=0"
	assert google_sheet_csv_url(raw) == raw


def test_load_bookings_from_url(monkeypatch):
	class FakeResponse:
		def read(self):
			return b"buyer_email,full_name,payment,table,baby_kid\na@x.com,A,paid,1,no\n"

		def __enter__(self):
			return self

		def __exit__(self, *args):
			return False

	monkeypatch.setattr("src.core.urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
	bookings, errors = load_bookings("https://docs.google.com/spreadsheets/d/abc123/edit")
	assert errors == []
	assert bookings[0]["full_name"] == "A"
	assert bookings[0]["buyer_email"] == "a@x.com"


def test_google_form_azerbaijani_headers_are_mapped(tmp_path):
	path = tmp_path / "bookings.csv"
	write_csv(
		path,
		"Timestamp,Email,Ad Soyad,Odenish,Stol Nomresi,Ushag sayi",
		[
			"9/14/2026 10:00:00,anna@x.com,Anna Aliyeva,paid,g11,1",
			"9/14/2026 10:05:00,bob@x.com,Bob Mammadov,pay_at_restaurant,g12,0",
		],
	)
	bookings, errors = parse_bookings(str(path))
	assert errors == []
	assert bookings[0]["buyer_email"] == "anna@x.com"
	assert bookings[0]["full_name"] == "Anna Aliyeva"
	assert bookings[0]["payment"] == "paid"
	assert bookings[0]["table"] == "g11"
	assert bookings[0]["baby_kid"] == "yes"
	assert bookings[1]["payment"] == "pay_at_restaurant"
	assert bookings[1]["baby_kid"] == "no"

