import math
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import db
import calculator


# --- calculate_tax ---

def test_calculate_tax_single_month(tmp_db):
    key_id = db.add_key(1, "X", "y")
    db.upsert_report(key_id, 1, "2026-01-01", "2026-01-07", 1, 10000.0)
    db.upsert_report(key_id, 2, "2026-01-08", "2026-01-14", 1, 5000.0)
    assert calculator.calculate_tax(key_id, (2026, 1), (2026, 1)) == math.ceil(15000.0 * 0.08)


def test_calculate_tax_rounds_up(tmp_db):
    key_id = db.add_key(1, "X", "y")
    db.upsert_report(key_id, 1, "2026-01-01", "2026-01-07", 1, 100.50)
    assert calculator.calculate_tax(key_id, (2026, 1), (2026, 1)) == math.ceil(100.50 * 0.08)


def test_calculate_tax_no_data_returns_none(tmp_db):
    key_id = db.add_key(1, "X", "y")
    assert calculator.calculate_tax(key_id, (2026, 1), (2026, 1)) is None


def test_calculate_tax_multi_month(tmp_db):
    key_id = db.add_key(1, "X", "y")
    db.upsert_report(key_id, 1, "2026-01-01", "2026-01-07", 1, 10000.0)
    db.upsert_report(key_id, 2, "2026-02-01", "2026-02-07", 1, 20000.0)
    db.upsert_report(key_id, 3, "2026-03-01", "2026-03-07", 1, 5000.0)
    assert calculator.calculate_tax(key_id, (2026, 1), (2026, 3)) == math.ceil(35000.0 * 0.08)


# --- parse_period ---

def test_parse_period_valid():
    assert calculator.parse_period("01.26-03.26") == ((2026, 1), (2026, 3))


def test_parse_period_same_month():
    assert calculator.parse_period("05.26-05.26") == ((2026, 5), (2026, 5))


def test_parse_period_invalid_format_returns_string():
    result = calculator.parse_period("jan-feb")
    assert isinstance(result, str)


def test_parse_period_end_before_start_returns_string():
    result = calculator.parse_period("03.26-01.26")
    assert isinstance(result, str)
    assert "раньше" in result


def test_parse_period_invalid_month_returns_string():
    result = calculator.parse_period("13.26-14.26")
    assert isinstance(result, str)


def test_parse_period_before_2025_returns_string():
    result = calculator.parse_period("12.24-01.25")
    assert isinstance(result, str)
    assert "2025" in result


def test_parse_period_start_before_2025_returns_string():
    result = calculator.parse_period("06.24-03.26")
    assert isinstance(result, str)
    assert "2025" in result


# --- format_period ---

def test_format_period_single_month():
    assert calculator.format_period((2026, 1), (2026, 1)) == "январь 2026"


def test_format_period_range_same_year():
    assert calculator.format_period((2026, 1), (2026, 3)) == "январь–март 2026"


def test_format_period_cross_year():
    assert calculator.format_period((2025, 11), (2026, 2)) == "ноябрь 2025–февраль 2026"


# --- needs_sync ---

def test_needs_sync_none_returns_true():
    assert calculator.needs_sync(None) is True


def test_needs_sync_old_returns_true():
    old = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    assert calculator.needs_sync(old) is True


def test_needs_sync_recent_returns_false():
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert calculator.needs_sync(recent) is False


# --- validate_key (mocked httpx) ---

async def test_validate_key_returns_true_on_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        assert await calculator.validate_key("valid-token") is True


async def test_validate_key_returns_false_on_401():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        assert await calculator.validate_key("bad-token") is False


async def test_validate_key_returns_false_on_timeout():
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        assert await calculator.validate_key("any-token") is False


# --- sync_reports (mocked httpx) ---

async def test_sync_reports_saves_data(tmp_db):
    key_id = db.add_key(1, "Shop", "tok")
    wb_response = [
        {
            "realizationreportId": 101,
            "dateFrom": "2026-01-01",
            "rr_dt": "2026-01-07",
            "reportType": 1,
            "retailAmountSum": "10000.50",
        }
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = wb_response
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await calculator.sync_reports(key_id, "tok", "2025-01-01")
    assert result is True
    conn = db.get_conn()
    reports = conn.execute("SELECT * FROM reports WHERE key_id=?", (key_id,)).fetchall()
    conn.close()
    assert len(reports) == 1
    assert reports[0]["retail_amount_sum"] == pytest.approx(10000.50)


async def test_sync_reports_returns_false_on_401(tmp_db):
    key_id = db.add_key(1, "Shop", "tok")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await calculator.sync_reports(key_id, "tok", "2025-01-01")
    assert result is False


async def test_sync_reports_returns_false_on_timeout(tmp_db):
    key_id = db.add_key(1, "Shop", "tok")
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        result = await calculator.sync_reports(key_id, "tok", "2025-01-01")
    assert result is False


def test_needs_sync_with_aware_datetime():
    recent_aware = datetime.now(timezone.utc).isoformat()
    assert calculator.needs_sync(recent_aware) is False
