import sys
import types


fake_qrcode = types.ModuleType("src.qrcode")
fake_qrcode.QRCode = object
fake_qrcode.QRErrorCorrectLevel = types.SimpleNamespace(L="L")
sys.modules.setdefault("src.qrcode", fake_qrcode)

from src.core import check_config


def test_check_config_reads_environment(monkeypatch, tmp_path):
	monkeypatch.setenv("SMTP_USER", "env@example.com")
	assert check_config("SMTP_USER=", base_path=str(tmp_path)) == "env@example.com"


def test_check_config_missing_file_returns_none(tmp_path):
	assert check_config("SMTP_USER=", base_path=str(tmp_path)) is None


def test_check_config_reads_file_when_env_missing(tmp_path):
	config_dir = tmp_path / "configuration"
	config_dir.mkdir()
	(config_dir / "config").write_text('SMTP_USER="file@example.com"\n', encoding="utf-8")
	assert check_config("SMTP_USER=", base_path=str(tmp_path)) == "file@example.com"