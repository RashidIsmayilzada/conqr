from src.core import (
	check_in,
	extract_qr_code,
	load_guests,
	render_checkin_page,
	save_guests,
)


def seed(path, rows):
	save_guests(str(path), rows)


def guest(**overrides):
	row = {
		"qr_code": "aaaa-bbbb-cccc-dddd",
		"buyer_email": "anna@x.com",
		"full_name": "Anna Smith",
		"payment": "paid",
		"table": "12",
		"baby_kid": "no",
		"emailed": "yes",
		"checked_in": "no",
		"checked_in_at": "",
	}
	row.update(overrides)
	return row


def test_unknown_code_does_not_change_file(tmp_path):
	path = tmp_path / "guests.csv"
	seed(path, [guest()])
	result = check_in("nope-nope", str(path))
	assert result["status"] == "not_found"
	assert result["guest"] is None
	assert load_guests(str(path))[0]["checked_in"] == "no"
	assert "viewport" in result["html"]
	assert "Ticket not found" in result["html"]


def test_empty_query_not_found(tmp_path):
	path = tmp_path / "guests.csv"
	seed(path, [guest()])
	assert check_in("", str(path))["status"] == "not_found"
	assert check_in(extract_qr_code(""), str(path))["status"] == "not_found"


def test_substring_of_real_code_does_not_match(tmp_path):
	path = tmp_path / "guests.csv"
	seed(path, [guest(qr_code="aaaa-bbbb-cccc-dddd")])
	result = check_in("aaaa", str(path))
	assert result["status"] == "not_found"
	assert load_guests(str(path))[0]["checked_in"] == "no"


def test_first_scan_marks_checked_in_and_shows_fields(tmp_path):
	path = tmp_path / "guests.csv"
	seed(path, [guest(baby_kid="yes")])
	result = check_in("aaaa-bbbb-cccc-dddd", str(path))
	assert result["status"] == "ok"
	html = result["html"]
	assert "Anna Smith" in html
	assert "12" in html
	assert "paid" in html
	assert "yes" in html
	assert "anna@x.com" in html
	assert "viewport" in html
	assert "http-equiv" not in html.lower()
	assert 'content="10' not in html
	loaded = load_guests(str(path))[0]
	assert loaded["checked_in"] == "yes"
	assert loaded["checked_in_at"]


def test_second_scan_keeps_fields_and_timestamp(tmp_path):
	path = tmp_path / "guests.csv"
	seed(path, [guest()])
	first = check_in("aaaa-bbbb-cccc-dddd", str(path))
	stamp = first["guest"]["checked_in_at"]
	second = check_in("aaaa-bbbb-cccc-dddd", str(path))
	assert second["status"] == "already"
	assert "Anna Smith" in second["html"]
	assert "Already checked in" in second["html"]
	assert load_guests(str(path))[0]["checked_in_at"] == stamp


def test_group_checkin_only_one_person(tmp_path):
	path = tmp_path / "guests.csv"
	seed(
		path,
		[
			guest(qr_code="code-a", full_name="A"),
			guest(qr_code="code-b", full_name="B"),
			guest(qr_code="code-c", full_name="C"),
			guest(qr_code="code-d", full_name="D"),
			guest(qr_code="code-e", full_name="E"),
		],
	)
	check_in("code-a", str(path))
	states = {row["full_name"]: row["checked_in"] for row in load_guests(str(path))}
	assert states == {"A": "yes", "B": "no", "C": "no", "D": "no", "E": "no"}


def test_unpaid_banner_distinct(tmp_path):
	paid = render_checkin_page("ok", guest(payment="paid"))
	unpaid = render_checkin_page("ok", guest(payment="pay_at_restaurant"))
	assert "PAY AT RESTAURANT" in unpaid
	assert "PAY AT RESTAURANT" not in paid
	assert "unpaid" in unpaid


def test_baby_kid_visible():
	html = render_checkin_page("ok", guest(baby_kid="yes"))
	assert "Baby / kid" in html
	assert "yes" in html


def test_missing_guests_csv_is_not_found(tmp_path):
	missing = tmp_path / "nope.csv"
	result = check_in("anything", str(missing))
	assert result["status"] == "not_found"


def test_extra_query_params_still_resolve(tmp_path):
	path = tmp_path / "guests.csv"
	seed(path, [guest(qr_code="aaaa-bbbb-cccc-dddd")])
	code = extract_qr_code("q=aaaa-bbbb-cccc-dddd&foo=bar")
	assert code == "aaaa-bbbb-cccc-dddd"
	assert check_in(code, str(path))["status"] == "ok"
