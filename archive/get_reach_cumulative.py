"""АРХИВ (2026-07-20): накопительный охват по кампаниям — get_reach_cumulative.

Функция выведена из активной библиотеки `yabbi_automate/yabbi_automate.py` по решению
пользователя 2026-07-20 («пока не нужна»). Код сохранён РАБОЧИМ: fetch-обёртка
`fetch_campaigns_statistics_total` (была методом YabbiClient) перенесена сюда
standalone-функцией, остальное импортируется из библиотеки.

Знание об источнике (метод `campaigns-statistics`, свойства `amountIFA`: неаддитивен,
оценочный — increment бывает отрицательным, клампить к 0 нельзя) — SSOT
`info/00_yabbi_source.md` §5.4, оно из сводки НЕ удалялось.

Использование (из корня репо, .env как для основной библиотеки):
    import sys
    sys.path.insert(0, "yabbi_automate"); sys.path.insert(0, "archive")
    from get_reach_cumulative import get_reach_cumulative
    df = get_reach_cumulative()  # [YABBI_GLOBAL_START_DATE, вчера]

Восстановление в библиотеку: вернуть в yabbi_automate.py константу REACH_COLUMNS,
метод fetch_campaigns_statistics_total в YabbiClient (self._get_json вместо
client._get_json) и функцию get_reach_cumulative; либо взять из git-истории
(состояние до архивирования — коммит a9440a8).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

import yabbi_automate as y

REACH_COLUMNS = ["date", "campaign_id", "name", "reach", "increment"]


def fetch_campaigns_statistics_total(
    client: "y.YabbiClient", campaign_ids: list[str], start_ms: int, end_ms: int
) -> list[dict[str, Any]]:
    """Итог по кампаниям за период (несёт охват amountIFA). id — батчами по ID_CHUNK.

    В активной библиотеке был методом YabbiClient; здесь — standalone поверх клиента.
    """
    out: list[dict[str, Any]] = []
    for chunk in y._chunks(campaign_ids, y.ID_CHUNK):
        data = client._get_json(
            "/report-ajax",
            {"method": "campaigns-statistics", "startTime": start_ms,
             "endTime": end_ms, "id": ",".join(chunk)},
        )
        out.extend(data if isinstance(data, list) else [])
    return out


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
    gs = global_start_date or y._global_start_date()
    date_from = date_from or gs
    date_to = date_to or y._yesterday()
    gs_d = datetime.strptime(gs, "%Y-%m-%d").date()
    df_d = datetime.strptime(date_from, "%Y-%m-%d").date()
    if df_d < gs_d:
        raise ValueError(
            f"date_from ({date_from}) раньше глобальной даты начала ({gs}) — "
            "накопительный охват определён только от глобальной даты начала."
        )

    client = y.YabbiClient()
    dict_rows = client.fetch_campaign_list(y._to_ms(gs), y._end_of_day_ms(y._yesterday()))
    campaign_ids = list(dict.fromkeys(str(e["id"]) for e in dict_rows if e.get("id")))
    name_by_id = {str(e["id"]): e.get("name") for e in dict_rows if e.get("id")}
    if not campaign_ids:
        return pd.DataFrame(columns=REACH_COLUMNS)

    gs_ms = y._to_ms(gs)
    # Если date_from позже глобального старта — добавляем предыдущий день как baseline,
    # чтобы increment первого дня был приростом, а не всем накопленным охватом.
    query_days = y._date_range(date_from, date_to)
    baseline_day: str | None = None
    if df_d > gs_d:
        baseline_day = (df_d - timedelta(days=1)).isoformat()
        query_days = [baseline_day] + query_days

    all_rows: list[dict[str, Any]] = []
    for day in query_days:
        # Накопительно по КОНЕЦ дня D МСК (последняя мс дня — бакет D+1 не задевается).
        end_ms = y._end_of_day_ms(day)
        for row in fetch_campaigns_statistics_total(client, campaign_ids, gs_ms, end_ms):
            cid = str(row.get("id"))
            all_rows.append({
                "date": day, "campaign_id": cid,
                "name": name_by_id.get(cid, row.get("name")),
                "reach": y._int(row.get("amountIFA")),
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
