import math
import re
import sqlite3
from datetime import date, datetime, timezone

import httpx

import db

WB_BASE = "https://finance-api.wildberries.ru"

MONTHS_RU = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]

MIN_YEAR, MIN_MONTH = 2025, 1


async def validate_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{WB_BASE}/api/v1/account/balance",
                headers={"Authorization": api_key},
            )
            return resp.status_code == 200
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
        return False


async def sync_reports(key_id: int, api_key: str, date_from: str) -> bool:
    """Возвращает True при успехе, False при 401 или сетевой ошибке."""
    date_to = date.today().isoformat()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{WB_BASE}/api/finance/v1/sales-reports/list",
                headers={"Authorization": api_key},
                json={"dateFrom": date_from, "dateTo": date_to},
            )
            if resp.status_code == 401:
                return False
            resp.raise_for_status()
            if db.get_key(key_id) is None:
                return True
            for item in resp.json():
                db.upsert_report(
                    key_id=key_id,
                    report_id=item["realizationreportId"],
                    date_from=item["dateFrom"],
                    date_to=item["rr_dt"],
                    report_type=item["reportType"],
                    retail_amount_sum=float(item["retailAmountSum"]),
                )
            db.update_last_synced(key_id)
            return True
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, sqlite3.IntegrityError):
        return False


def calculate_tax(
    key_id: int,
    month_from: tuple[int, int],
    month_to: tuple[int, int],
) -> int | None:
    reports = db.get_reports_for_period(key_id, month_from, month_to)
    if not reports:
        return None
    total = sum(r["retail_amount_sum"] for r in reports)
    return math.ceil(total * 0.08)


def parse_period(text: str) -> tuple[tuple[int, int], tuple[int, int]] | str:
    """Возвращает ((y1, m1), (y2, m2)) или строку с сообщением об ошибке."""
    m = re.fullmatch(r"(\d{2})\.(\d{2})-(\d{2})\.(\d{2})", text.strip())
    if not m:
        return "Неверный формат. Введите MM.YY-MM.YY, например 01.26-03.26"
    mm1, yy1, mm2, yy2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    y1, y2 = 2000 + yy1, 2000 + yy2
    if not (1 <= mm1 <= 12 and 1 <= mm2 <= 12):
        return "Неверный формат. Введите MM.YY-MM.YY, например 01.26-03.26"
    if (y1, mm1) < (MIN_YEAR, MIN_MONTH):
        return "Данные доступны с января 2025 года"
    if (y1, mm1) > (y2, mm2):
        return "Конец периода не может быть раньше начала"
    today = date.today()
    if (y2, mm2) > (today.year, today.month):
        return "Конец периода не может быть в будущем"
    return (y1, mm1), (y2, mm2)


def format_period(month_from: tuple[int, int], month_to: tuple[int, int]) -> str:
    y1, m1 = month_from
    y2, m2 = month_to
    if (y1, m1) == (y2, m2):
        return f"{MONTHS_RU[m1 - 1]} {y1}"
    if y1 == y2:
        return f"{MONTHS_RU[m1 - 1]}–{MONTHS_RU[m2 - 1]} {y1}"
    return f"{MONTHS_RU[m1 - 1]} {y1}–{MONTHS_RU[m2 - 1]} {y2}"


def needs_sync(last_synced_at: str | None) -> bool:
    if last_synced_at is None:
        return True
    dt = datetime.fromisoformat(last_synced_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() >= 600
