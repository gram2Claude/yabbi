# Реестр реализованных функций — Yabbi

Статус: **черновик** (draft). 3 активные функции реализованы в `yabbi_automate/yabbi_automate.py`
и проверены smoke-тестом на живом кабинете 2026-07-03. Ожидают двойного ревью до сходимости.
Четвёртая (`get_reach_cumulative`, охват) — в архиве с 2026-07-20 (см. раздел «Архив» ниже).

---

## get_campaign_dict() — справочник кампаний

- **Метод:** `GET /ajax?method=campaign-list&startTime&endTime&status=all&type=all`.
- **Окно:** `[YABBI_GLOBAL_START_DATE, вчера]`. Дедуп по `id`.
- **Колонки:** `id, name, type, bidType, status`.
- **Проверено:** 41 кампания (окно `[глоб. дата начала=2026-06-01, вчера]`; на других окнах число иное:
  120 дней → 43, 400 дней → 55), колонки/типы корректны.

## get_campaigns_daily_stat(date_from, date_to) — кампания × день

- **Метод:** `GET /report-ajax?method=campaigns-statistics-daily&id=<csv>` по 1 дню:
  окно `[D 00:00 МСК, D+1 00:00 МСК]`, из ответа только ключ `D`; id — батчами по `ID_CHUNK=5`.
- **Колонки:** `date, id, name, win, load, click, budget, bid, auction, firstQuartile, midpoint, thirdQuartile, complete`
  (метрики из `state`; `budget` — float, округл. до 2). Кабинет: «Показы»=`win`, «Видимость»=`load`, «Клики»=`click`.
- **Проверено:** 2026-07-04, сверка с кабинетом («Мои кампании», 01.07.2026) по 3 кампаниям — до единицы.

## get_banners_daily_stat(date_from, date_to) — баннер × день

- **Метод:** метрики — `GET /statistics/statistics-per-banners-per-days` (`[D 00:00 МСК, D+1 00:00 МСК]`
  + фильтр `day==D`); `campaign_id` — через `GET /report-ajax?method=campaigns-banners-daily&id=<csv>`
  (`url==URL` → `campaign`; id — батчами по `ID_CHUNK=5`).
- **Агрегация:** сумма `show/click/complete` по `(date, URL)`.
- **Колонки:** `date, campaign_id, URL, show, click, complete`.
- **Проверено:** 36 баннеров за 2026-07-01; `campaign_id` заполняется по карте.

---

# Архив

## get_reach_cumulative(global_start_date, date_from, date_to) — накопительный охват

**⚠ В АРХИВЕ с 2026-07-20** (решение пользователя: пока не нужна). Из библиотеки удалена
(вместе с `fetch_campaigns_statistics_total` и `REACH_COLUMNS`); рабочий код —
`archive/get_reach_cumulative.py`. Описание ниже сохранено на случай возврата.

- **Метод:** `GET /report-ajax?method=campaigns-statistics&startTime=<глоб.дата начала 00:00 МСК>&endTime=<конец дня D МСК>&id=<csv>` на каждый день D (id — батчами по `ID_CHUNK=5`).
- **Логика:** `reach = amountIFA` (накопительно); `increment = reach[D] − reach[D−1]`.
- **Колонки:** `date, campaign_id, name, reach, increment`.
- **Проверено:** монотонный рост (68811 → 74975 → 78469), increment положителен.

---

## История изменений

- **2026-07-20** — `get_reach_cumulative` перенесена в архив (`archive/get_reach_cumulative.py`)
  по решению пользователя «пока не нужна»: из библиотеки удалены сама функция, метод клиента
  `fetch_campaigns_statistics_total` и `REACH_COLUMNS`. Активных функций — 3. Знание об
  источнике охвата (`campaigns-statistics`, свойства `amountIFA`) сохранено в
  `info/00_yabbi_source.md` §5.4.
- **2026-07-04** — два системных фикса по итогам сверки со скриншотом кабинета («Мои кампании», 01.07):
  1. **МСК-окна дней.** Сутки Yabbi бакетируются по московской полуночи, а `startTime==endTime` возвращает
     лишь стартовый ~часовой бакет (daily занижался в 15–20 раз, кампании без ночного трафика выпадали).
     `_to_ms` переведён на полночь МСК; daily — окно `[D, D+1]` + фильтр ключа дня; banners — то же окно;
     reach и справочник — инклюзивный `endTime` = последняя мс дня. Допущение 2026-07-03 «endTime включает
     свой день» снято как неверное. Сверка с кабинетом: 3 кампании (F2F, Перекрёсток, Чижик) — до единицы;
     маппинг: «Показы»=`win`, «Видимость»=`load`, «Клики»=`click`.
  2. **Батчинг id.** `/report-ajax` тратит ~5–7 с на кампанию (41 id разом в плохие дни не отвечает и за
     300 с) — все fetch-методы с `id` шлют батчами по `ID_CHUNK=5` и склеивают; `HTTP_TIMEOUT_SEC` 120→180.
  Плюс: в `get_campaigns_daily_stat` добавлена колонка `load` («Видимость» кабинета).
- **2026-07-03** — первичная реализация 4 функций (черновик). Исправлен off-by-one в диапазонах дат
  (`endTime` включает свой день): daily/reach брали лишний день; per-banners — фильтр по `day`. Smoke зелёный.
