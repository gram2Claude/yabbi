"""Yabbi (my.yabbi.me) cabinet client — ЧЕРНОВИК.

Источник БЕЗ публичного API: статистика забирается из личного кабинета рекламодателя
по cookie-сессии; «методы» передаются в параметрах URL. Полная сводка источника —
`info/00_yabbi_source.md`.

Публичные функции (каждая возвращает pandas DataFrame):
- get_campaign_dict()                                   — справочник кампаний
- get_campaigns_daily_stat(date_from, date_to)          — статистика по кампаниям по дням
- get_banners_daily_stat(date_from, date_to)            — статистика по баннерам по дням (+ campaign_id)
- get_reach_cumulative(global_start_date, date_from, date_to) — накопительный охват по кампаниям

Учётные данные читаются из окружения YABBI_LOGIN / YABBI_PASSWORD
(или передаются явно в YabbiClient). Глобальная дата начала — YABBI_GLOBAL_START_DATE.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

# Перенастройка кодировки — обязательно на Windows (cp1251 по умолчанию).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

# ── Константы ─────────────────────────────────────────────────────────────────

BASE_URL = "https://my.yabbi.me"
LOGIN_PATH = "/login?method=account"

HTTP_TIMEOUT_SEC = 120          # эндпоинты кабинета медленные
RETRY_MAX = 5                   # повторов при сетевой ошибке / протухшей сессии
RETRY_BASE_SEC = 2              # начальная пауза (удваивается)
SESSION_TTL_SEC = 3600          # cookie as-account-session живёт 1 час (Max-Age=3600)
SESSION_REFRESH_LEEWAY_SEC = 120  # перелогиниваться заранее

# Правила запроса (см. info/00_yabbi_source.md, §5):
# - статистика по кампаниям/баннерам — по 1 дню за запрос (обход 16КБ-сетевого затыка);
# - охват (reach) — накопительно за [global_start_date, D] (неаддитивен, не по дням);
# - обязателен gzip (requests шлёт Accept-Encoding: gzip и распаковывает сам).

# ── Колонки итоговых DataFrame (фиксируют состав и порядок) ────────────────────

CAMPAIGN_DICT_COLUMNS = ["id", "name", "type", "bidType", "status"]

CAMPAIGNS_DAILY_COLUMNS = [
    "date", "id", "name",
    "win", "click", "budget",
    "bid", "auction",
    "firstQuartile", "midpoint", "thirdQuartile", "complete",
]

BANNERS_DAILY_COLUMNS = ["date", "campaign_id", "URL", "show", "click", "complete"]

REACH_COLUMNS = ["date", "campaign_id", "name", "reach", "increment"]


# ── Клиент ────────────────────────────────────────────────────────────────────

class YabbiClient:
    """HTTP-клиент к кабинету Yabbi с cookie-сессией.

    Авторизация — форма входа POST /login?method=account (login/password);
    ОБЯЗАТЕЛЬНЫ заголовки Referer и Origin, иначе сервер отвечает «неправильный
    логин/пароль». Сессия (cookie as-account-session) живёт ~1 час и продлевается
    каждым запросом; клиент перелогинивается сам при истечении/потере доступа.
    """

    def __init__(self, login: str | None = None, password: str | None = None) -> None:
        self._login = login or os.environ.get("YABBI_LOGIN")
        self._password = password or os.environ.get("YABBI_PASSWORD")
        if not self._login or not self._password:
            raise RuntimeError(
                "Учётные данные Yabbi не предоставлены. Передайте login/password "
                "или задайте YABBI_LOGIN и YABBI_PASSWORD."
            )
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "yabbi-automate/1.0"})
        self._authed_at: float = 0.0

    # ── Авторизация ────────────────────────────────────────────────────────────

    def _do_login(self) -> None:
        url = f"{BASE_URL}{LOGIN_PATH}"
        resp = self._session.post(
            url,
            data={"login": self._login, "password": self._password},
            headers={"Referer": url, "Origin": BASE_URL},
            timeout=HTTP_TIMEOUT_SEC,
            allow_redirects=True,
        )
        resp.raise_for_status()
        ok = ("as-account-session" in self._session.cookies) and ("error=" not in resp.url)
        if not ok:
            raise RuntimeError(
                "Не удалось авторизоваться в Yabbi (проверьте YABBI_LOGIN/YABBI_PASSWORD "
                "и вкладку «Рекламодатель»)."
            )
        self._authed_at = time.time()
        logger.info("Yabbi: сессия установлена")

    def _ensure_session(self) -> None:
        if time.time() >= self._authed_at + SESSION_TTL_SEC - SESSION_REFRESH_LEEWAY_SEC:
            self._do_login()

    # ── HTTP ───────────────────────────────────────────────────────────────────

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET с авто-сессией, gzip и повторами. Возвращает распарсенный JSON.

        Пустой ответ кабинета (`null`) отдаётся как None — это «нет данных».
        Строка `{"err": ...}` (напр. «no access») трактуется как потеря сессии → перелогин.
        """
        url = f"{BASE_URL}{path}"
        wait = RETRY_BASE_SEC
        last_exc: Exception | None = None
        for attempt in range(RETRY_MAX + 1):
            try:
                self._ensure_session()
                resp = self._session.get(
                    url,
                    params=params,
                    headers={
                        "Accept-Encoding": "gzip",
                        "Referer": f"{BASE_URL}/campaign?method=list",
                    },
                    timeout=HTTP_TIMEOUT_SEC,
                )
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and "err" in data:
                    # {"err": "no access", …} — сессия не действует (ключи-даты не бывают "err"),
                    # форсим перелогин и повтор
                    logger.warning("Yabbi err-ответ (%s) — перелогин", data.get("err"))
                    self._authed_at = 0.0
                    raise _SessionLost(str(data.get("err")))
                return data
            except (requests.RequestException, _SessionLost, ValueError) as exc:
                last_exc = exc
                if attempt == RETRY_MAX:
                    break
                logger.warning("GET %s: %s (попытка %d/%d)", path, exc, attempt + 1, RETRY_MAX)
                self._authed_at = 0.0  # на всякий случай пере-авторизуемся
                time.sleep(wait)
                wait *= 2
        raise RuntimeError(f"Не удалось получить {path}: {last_exc}") from last_exc

    # ── Эндпоинты кабинета ─────────────────────────────────────────────────────

    def fetch_campaign_list(self, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        """Справочник кампаний за период (status=all, type=all)."""
        data = self._get_json(
            "/ajax",
            {"method": "campaign-list", "startTime": start_ms, "endTime": end_ms,
             "status": "all", "type": "all"},
        )
        return data if isinstance(data, list) else []

    def fetch_campaigns_statistics_daily(
        self, campaign_ids: list[str], start_ms: int, end_ms: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Статистика по кампаниям, keyed by date. Требует id кампаний."""
        data = self._get_json(
            "/report-ajax",
            {"method": "campaigns-statistics-daily", "startTime": start_ms,
             "endTime": end_ms, "id": ",".join(campaign_ids)},
        )
        return data if isinstance(data, dict) else {}

    def fetch_campaigns_statistics_total(
        self, campaign_ids: list[str], start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]:
        """Итог по кампаниям за период (несёт охват amountIFA)."""
        data = self._get_json(
            "/report-ajax",
            {"method": "campaigns-statistics", "startTime": start_ms,
             "endTime": end_ms, "id": ",".join(campaign_ids)},
        )
        return data if isinstance(data, list) else []

    def fetch_per_banners_per_days(self, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        """Статистика по баннерам по дням (аккаунт целиком). Пустой период → []."""
        data = self._get_json(
            "/statistics/statistics-per-banners-per-days",
            {"startTime": start_ms, "endTime": end_ms},
        )
        return data if isinstance(data, list) else []

    def fetch_campaigns_banners_daily(
        self, campaign_ids: list[str], start_ms: int, end_ms: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Баннеры по дням для заданных кампаний, keyed by date. Несёт url + campaign."""
        data = self._get_json(
            "/report-ajax",
            {"method": "campaigns-banners-daily", "startTime": start_ms,
             "endTime": end_ms, "id": ",".join(campaign_ids)},
        )
        return data if isinstance(data, dict) else {}


class _SessionLost(Exception):
    """Внутренний сигнал: кабинет ответил err/no access — нужна пере-авторизация."""


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _to_ms(day: str) -> int:
    """`YYYY-MM-DD` → Unix-время в миллисекундах (полночь UTC).

    Проверено на живом кабинете: фильтр по дням работает с полуночью UTC.
    """
    dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp()) * 1000


def _yesterday() -> str:
    # UTC — согласовано с _to_ms (окна считаются в полночь UTC).
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def _date_range(date_from: str, date_to: str) -> list[str]:
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    if end < start:
        raise ValueError(f"date_to ({date_to}) раньше date_from ({date_from})")
    out, cur = [], start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _global_start_date() -> str:
    gs = os.environ.get("YABBI_GLOBAL_START_DATE")
    if not gs:
        raise RuntimeError("Не задана YABBI_GLOBAL_START_DATE (глобальная дата начала).")
    return gs


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def _int(value: Any) -> int:
    return int(_num(value))


# ── Публичные функции ─────────────────────────────────────────────────────────

def get_campaign_dict() -> pd.DataFrame:
    """Справочник кампаний.

    Источник: /ajax?method=campaign-list, окно [YABBI_GLOBAL_START_DATE, вчера],
    status=all. Ежедневно перезаписывается целиком. Дедуп по `id` (выживает первая).

    Колонки: id, name, type (rtb=баннер / vast=видео), bidType (click/show), status.
    """
    client = YabbiClient()
    start_ms = _to_ms(_global_start_date())
    end_ms = _to_ms(_yesterday())
    rows = client.fetch_campaign_list(start_ms, end_ms)
    if not rows:
        return pd.DataFrame(columns=CAMPAIGN_DICT_COLUMNS)
    df = pd.DataFrame([{c: e.get(c) for c in CAMPAIGN_DICT_COLUMNS} for e in rows])
    df = df.dropna(subset=["id"]).drop_duplicates(subset=["id"])
    return df.reindex(columns=CAMPAIGN_DICT_COLUMNS).reset_index(drop=True)


def get_campaigns_daily_stat(date_from: str, date_to: str) -> pd.DataFrame:
    """Статистика по кампаниям по дням.

    Источник: /report-ajax?method=campaigns-statistics-daily (нужны id кампаний
    из справочника). Забор — ПО ОДНОМУ ДНЮ за запрос.

    Колонки: date, id, name, win, click, budget, bid, auction,
             firstQuartile, midpoint, thirdQuartile, complete.
    """
    client = YabbiClient()
    dict_rows = client.fetch_campaign_list(_to_ms(_global_start_date()), _to_ms(_yesterday()))
    campaign_ids = list(dict.fromkeys(str(e["id"]) for e in dict_rows if e.get("id")))
    if not campaign_ids:
        return pd.DataFrame(columns=CAMPAIGNS_DAILY_COLUMNS)

    metric_keys = ["win", "click", "budget", "bid", "auction",
                   "firstQuartile", "midpoint", "thirdQuartile", "complete"]
    all_rows: list[dict[str, Any]] = []
    for day in _date_range(date_from, date_to):
        # endTime у Yabbi ВКЛЮЧАЕТ день endTime → для одного дня startTime==endTime==D.
        day_data = client.fetch_campaigns_statistics_daily(campaign_ids, _to_ms(day), _to_ms(day))
        for stat_day, camp_rows in (day_data or {}).items():
            if stat_day != day:
                continue
            for row in camp_rows:
                state = row.get("state", {}) or {}
                rec = {"date": stat_day, "id": row.get("id"), "name": row.get("name")}
                for k in metric_keys:
                    rec[k] = _num(state.get(k)) if k == "budget" else _int(state.get(k))
                all_rows.append(rec)
    if not all_rows:
        return pd.DataFrame(columns=CAMPAIGNS_DAILY_COLUMNS)
    df = pd.DataFrame(all_rows)
    df["budget"] = df["budget"].round(2)
    return df.reindex(columns=CAMPAIGNS_DAILY_COLUMNS).reset_index(drop=True)


def get_banners_daily_stat(date_from: str, date_to: str) -> pd.DataFrame:
    """Статистика по баннерам по дням.

    Источник метрик: /statistics/statistics-per-banners-per-days (аккаунт целиком),
    агрегируется суммой по (date, URL). campaign_id обогащается через
    /report-ajax?method=campaigns-banners-daily (URL == url → campaign). Забор по дням.

    Колонки: date, campaign_id, URL, show, click, complete.
    """
    client = YabbiClient()
    dict_rows = client.fetch_campaign_list(_to_ms(_global_start_date()), _to_ms(_yesterday()))
    campaign_ids = list(dict.fromkeys(str(e["id"]) for e in dict_rows if e.get("id")))

    all_rows: list[dict[str, Any]] = []
    for day in _date_range(date_from, date_to):
        day_ms = _to_ms(day)
        next_ms = _to_ms((datetime.strptime(day, "%Y-%m-%d").date() + timedelta(days=1)).isoformat())

        # 1) метрики по баннерам за день, агрегируем по URL.
        # per-banners НЕ принимает нулевой диапазон (startTime==endTime → 400), поэтому
        # запрашиваем [D, D+1] и оставляем только строки дня D (endTime включает след. день).
        agg: dict[str, dict[str, int]] = {}
        for r in client.fetch_per_banners_per_days(day_ms, next_ms):
            if r.get("day") != day:
                continue
            u = r.get("URL")
            if not u:  # строка без URL — идентификатора баннера нет, пропускаем
                continue
            a = agg.setdefault(u, {"show": 0, "click": 0, "complete": 0})
            a["show"] += _int(r.get("show"))
            a["click"] += _int(r.get("click"))
            a["complete"] += _int(r.get("complete"))

        # 2) карта URL → campaign за тот же день (только строки дня D — endTime включает D+1)
        url_to_camp: dict[str, str] = {}
        if campaign_ids:
            banners = client.fetch_campaigns_banners_daily(campaign_ids, day_ms, next_ms)
            for _dt, brows in (banners or {}).items():
                if _dt != day:
                    continue
                for b in brows:
                    if b.get("url"):
                        url_to_camp.setdefault(b["url"], b.get("campaign"))

        for u, a in agg.items():
            all_rows.append({
                "date": day, "campaign_id": url_to_camp.get(u), "URL": u,
                "show": a["show"], "click": a["click"], "complete": a["complete"],
            })
    if not all_rows:
        return pd.DataFrame(columns=BANNERS_DAILY_COLUMNS)
    df = pd.DataFrame(all_rows)
    return df.reindex(columns=BANNERS_DAILY_COLUMNS).reset_index(drop=True)


def get_reach_cumulative(
    global_start_date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Накопительный охват по кампаниям (кумулятивная метрика).

    Охват (amountIFA) неаддитивен → нельзя суммировать по дням. Для каждого дня D
    из [date_from, date_to] делается ОТДЕЛЬНЫЙ запрос /report-ajax?method=campaigns-statistics
    за период [global_start_date, D]; берётся amountIFA = накопительный охват.
    increment = reach[D] − reach[D−1] (для первого дня = reach).

    По умолчанию: global_start_date = YABBI_GLOBAL_START_DATE, date_from = та же дата,
    date_to = вчера.

    Колонки: date, campaign_id, name, reach, increment.
    """
    gs = global_start_date or _global_start_date()
    date_from = date_from or gs
    date_to = date_to or _yesterday()
    gs_d = datetime.strptime(gs, "%Y-%m-%d").date()
    df_d = datetime.strptime(date_from, "%Y-%m-%d").date()
    if df_d < gs_d:
        raise ValueError(
            f"date_from ({date_from}) раньше глобальной даты начала ({gs}) — "
            "накопительный охват определён только от глобальной даты начала."
        )

    client = YabbiClient()
    dict_rows = client.fetch_campaign_list(_to_ms(gs), _to_ms(_yesterday()))
    campaign_ids = list(dict.fromkeys(str(e["id"]) for e in dict_rows if e.get("id")))
    name_by_id = {str(e["id"]): e.get("name") for e in dict_rows if e.get("id")}
    if not campaign_ids:
        return pd.DataFrame(columns=REACH_COLUMNS)

    gs_ms = _to_ms(gs)
    # Если date_from позже глобального старта — добавляем предыдущий день как baseline,
    # чтобы increment первого дня был приростом, а не всем накопленным охватом.
    query_days = _date_range(date_from, date_to)
    baseline_day: str | None = None
    if df_d > gs_d:
        baseline_day = (df_d - timedelta(days=1)).isoformat()
        query_days = [baseline_day] + query_days

    all_rows: list[dict[str, Any]] = []
    for day in query_days:
        # endTime включает день D → накопительный охват за [global_start_date, D].
        end_ms = _to_ms(day)
        for row in client.fetch_campaigns_statistics_total(campaign_ids, gs_ms, end_ms):
            cid = str(row.get("id"))
            all_rows.append({
                "date": day, "campaign_id": cid,
                "name": name_by_id.get(cid, row.get("name")),
                "reach": _int(row.get("amountIFA")),
            })
    if not all_rows:
        return pd.DataFrame(columns=REACH_COLUMNS)
    df = pd.DataFrame(all_rows).sort_values(["campaign_id", "date"]).reset_index(drop=True)
    df["increment"] = df.groupby("campaign_id")["reach"].diff()
    # первый день ряда (от глобального старта) прироста «до» не имеет → increment = сам reach
    df["increment"] = df["increment"].fillna(df["reach"]).astype(int)
    if baseline_day is not None:  # baseline нужен только для расчёта, в выдачу не идёт
        df = df[df["date"] != baseline_day].reset_index(drop=True)
    return df.reindex(columns=REACH_COLUMNS).reset_index(drop=True)
