# Реестр реализованных функций — Yabbi

Статус: **черновик** (draft). Все 4 функции реализованы в `yabbi_automate/yabbi_automate.py`
и проверены smoke-тестом на живом кабинете 2026-07-03. Ожидают двойного ревью до сходимости.

---

## get_campaign_dict() — справочник кампаний

- **Метод:** `GET /ajax?method=campaign-list&startTime&endTime&status=all&type=all`.
- **Окно:** `[YABBI_GLOBAL_START_DATE, вчера]`. Дедуп по `id`.
- **Колонки:** `id, name, type, bidType, status`.
- **Проверено:** 41 кампания (окно `[глоб. дата начала=2026-06-01, вчера]`; на других окнах число иное:
  120 дней → 43, 400 дней → 55), колонки/типы корректны.

## get_campaigns_daily_stat(date_from, date_to) — кампания × день

- **Метод:** `GET /report-ajax?method=campaigns-statistics-daily&id=<csv>` по 1 дню (`startTime==endTime==D`).
- **Колонки:** `date, id, name, win, click, budget, bid, auction, firstQuartile, midpoint, thirdQuartile, complete`
  (метрики из `state`; `budget` — float, округл. до 2).
- **Проверено:** 2026-07-01, активные кампании — по одному дню, значения совпадают с кабинетом.

## get_banners_daily_stat(date_from, date_to) — баннер × день

- **Метод:** метрики — `GET /statistics/statistics-per-banners-per-days` (`[D, D+1]` + фильтр `day==D`);
  `campaign_id` — через `GET /report-ajax?method=campaigns-banners-daily&id=<csv>` (`url==URL` → `campaign`).
- **Агрегация:** сумма `show/click/complete` по `(date, URL)`.
- **Колонки:** `date, campaign_id, URL, show, click, complete`.
- **Проверено:** 36 баннеров за 2026-07-01; `campaign_id` заполняется по карте.

## get_reach_cumulative(global_start_date, date_from, date_to) — накопительный охват

- **Метод:** `GET /report-ajax?method=campaigns-statistics&startTime=<глоб.дата начала>&endTime=D&id=<csv>` на каждый день D.
- **Логика:** `reach = amountIFA` (накопительно); `increment = reach[D] − reach[D−1]`.
- **Колонки:** `date, campaign_id, name, reach, increment`.
- **Проверено:** монотонный рост (68811 → 74975 → 78469), increment положителен.

---

## История изменений

- **2026-07-03** — первичная реализация 4 функций (черновик). Исправлен off-by-one в диапазонах дат
  (`endTime` включает свой день): daily/reach брали лишний день; per-banners — фильтр по `day`. Smoke зелёный.
