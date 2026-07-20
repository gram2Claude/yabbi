# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Что это

Клиентская автоматизация выгрузки статистики из кабинета **Yabbi** (`my.yabbi.me`) —
источника **без публичного API**: данные забираются из личного кабинета рекламодателя по
cookie-сессии, «методы» передаются в параметрах URL. Единая сводка источника (авторизация,
endpoints, поля, зафиксированные решения) — **`info/00_yabbi_source.md`** (читать первым).

## Setup

```bash
pip install -r yabbi_automate/requirements.txt
```

Credentials в `yabbi_automate/.env` (копия из `.env.example`):

```
YABBI_LOGIN=...
YABBI_PASSWORD=...
YABBI_GLOBAL_START_DATE=2026-06-01   # startTime справочника и накопительного охвата; endTime = вчера
```

## Архитектура

Однофайловая библиотека: `yabbi_automate/yabbi_automate.py`.

**`YabbiClient`** — HTTP-клиент с cookie-сессией:
- Авторизация — форма `POST /login?method=account` (`login`/`password`), **обязательны заголовки
  `Referer` + `Origin`** (иначе «неправильный логин/пароль»). Сессия ~1 ч (cookie `as-account-session`),
  продлевается запросами; клиент перелогинивается сам (при протухании / ответе `{"err": "no access"}`).
- Все GET идут с `Accept-Encoding: gzip` (обходит сетевой затык >16 КБ; `requests` шлёт и распаковывает сам)
  и повторами с backoff.
- Методы-обёртки: `fetch_campaign_list`, `fetch_campaigns_statistics_daily`,
  `fetch_per_banners_per_days`, `fetch_campaigns_banners_daily`.

**Публичные функции** (возвращают `pd.DataFrame`):

| Функция | Гранулярность | Метод-источник |
|---------|---------------|----------------|
| `get_campaign_dict()` | справочник кампаний | `/ajax?method=campaign-list` |
| `get_campaigns_daily_stat(date_from, date_to)` | кампания × день (вкл. «Видимость» = `load`) | `/report-ajax?method=campaigns-statistics-daily` |
| `get_banners_daily_stat(date_from, date_to)` | баннер × день | `/statistics/statistics-per-banners-per-days` (+ `campaigns-banners-daily` для `campaign_id`) |

Колонки таблиц — минимальные и фиксированные (см. `manual_forms/03_ENTITY_FUNCTIONS.md`).

**Архив:** `get_reach_cumulative` (накопительный охват из `amountIFA`) выведена из библиотеки
2026-07-20 — пока не нужна; рабочий код в `archive/get_reach_cumulative.py`, знание об
источнике — `info/00_yabbi_source.md` §5.4.

## Ключевые правила источника (критично — легко ошибиться)

- **Сутки Yabbi — по МОСКОВСКОЙ полуночи; `startTime`/`endTime` — Unix-мс** (`_to_ms` даёт полночь МСК).
  ⚠️ `startTime==endTime` возвращает НЕ весь день, а лишь стартовый ~часовой бакет (проверено 2026-07-04:
  занижение в 15–20 раз). День D забирается окном **`[D 00:00 МСК, D+1 00:00 МСК]` + фильтр по ключу/полю
  дня `== D`** (daily и per-banners одинаково; per-banners нулевой диапазон отвергает `400`);
  охват — `endTime = конец дня D МСК` (последняя мс дня, накопительно).
- **Кабинет ↔ `state`: «Показы» = `win`, «Видимость» = `load`, «Клики» = `click`** (CTR = click/win;
  `view` — НЕ «Видимость», он чуть больше `load`). Сверено с кабинетом до единицы (3 кампании, 2026-07-04).
- **`/report-ajax` тратит ~5–7 с НА КАЖДУЮ кампанию из `id`** (в плохие дни полный список из 41 id не
  отвечает вовсе, скорость плавает день ко дню) → клиент шлёт id **батчами по `ID_CHUNK=5`** и склеивает.
- **Охват (`amountIFA`) неаддитивен** — только накопительно за `[global_start_date, D]`, не сумма по дням,
  и только из метода `campaigns-statistics` (в `campaign-list` = 0; в `daily` — фиктивная константа).
  Функция охвата — в архиве (см. выше), правило сохраняется на случай возврата.
- **`URL` в статистике по баннерам не уникален** за день → агрегировать суммой по `(date, URL)`.
- **Привязка баннер→кампания — через `campaigns-banners-daily`** (`url` == `URL`, → `campaign` id), НЕ парсингом URL.
- **gzip обязателен** для больших ответов (сетевой затык >16 КБ на некоторых сетях — воспроизведён на win-vm).

## Running

Smoke (живой кабинет, нужен `.env`):
```python
import sys; sys.path.insert(0, "yabbi_automate")
import yabbi_automate as y
print(y.get_campaign_dict().shape)
print(y.get_campaigns_daily_stat("2026-07-01", "2026-07-01").head())
```

## Reference

- `info/00_yabbi_source.md` — сводка источника (SSOT): авторизация, endpoints, поля, решения.
- `info/01_functions_implemented.md` — реестр реализованных функций.
- `test/` — шаблонная система (перенесена из avito, адаптируется под no-API сценарий; см. `test/SCENARIO_no_api_cabinet.md`).
- ТЗ для внешнего разработчика — `specs/TZ_yabbi_automate.md` (черновик).
