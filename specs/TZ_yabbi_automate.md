# ТЗ: выгрузка статистики Yabbi (my.yabbi.me) — портирование на другой язык

Эталонная реализация: `yabbi_automate/yabbi_automate.py` (Python).
Цель — портировать функциональность на целевой язык (PHP / Go / Java / …) с сохранением
структуры выходных данных. Документ самодостаточен; доступ к Python-коду не требуется.

Версия документа: 2026-07-03 (черновик).

---

## 1. Цель проекта

Разработать библиотеку выгрузки статистики из рекламного кабинета **Yabbi** (`my.yabbi.me`).
У площадки **нет публичного API** — данные забираются из личного кабинета рекламодателя по
**cookie-сессии**, а «методы» передаются в параметрах URL. Библиотека отдаёт 4 таблицы:
справочник кампаний, статистику по кампаниям по дням, статистику по баннерам по дням и
накопительный охват по кампаниям. Выход каждой функции — массив строк с фиксированным набором колонок.

---

## 2. Общая логика

1. **Авторизация** — один раз логинимся формой, получаем session-cookie, дальше все запросы идут с ней.
2. **Справочник кампаний** — один запрос за окно `[глобальная дата начала, вчера]`.
3. **Статистика** (кампании/баннеры) — **по одному дню за запрос**, склеиваем дни.
4. **Охват** — кумулятивно: на каждый день D отдельный запрос за `[глобальная дата начала, D]`.

---

## 3. Ключевые принципы работы с Yabbi

### 3.1. Авторизация (cookie-сессия)

- Вход: `POST https://my.yabbi.me/login?method=account`, тело `application/x-www-form-urlencoded`,
  поля `login`, `password` (вкладка «Рекламодатель»).
- ⚠️ **ОБЯЗАТЕЛЬНЫ заголовки** `Referer: https://my.yabbi.me/login?method=account` и
  `Origin: https://my.yabbi.me`. Без них сервер отвечает «Неправильный логин или пароль» (антибот).
- Успех = редирект на `/campaign?method=list` + cookies `as-account-session` (HttpOnly), `as-account`, `csrf`.
- **TTL сессии ~1 час** (`Max-Age=3600`), продлевается каждым запросом. Клиент должен **перелогиниваться
  сам** по TTL и при ответе `{"err": "no access"}` (признак потерянной сессии).
- Капчи/2FA/CSRF-поля в форме нет.

### 3.2. Базовый URL и эндпоинты

`BASE_URL = https://my.yabbi.me`. Все — `GET`, ответ — JSON (`Content-Type: text/plain`).

| Метод (в URL) | Назначение |
|---|---|
| `/ajax?method=campaign-list&startTime&endTime&status=all&type=all` | справочник кампаний |
| `/report-ajax?method=campaigns-statistics-daily&startTime&endTime&id=<csv>` | кампании × день |
| `/statistics/statistics-per-banners-per-days?startTime&endTime` | баннеры × день (аккаунт целиком) |
| `/report-ajax?method=campaigns-banners-daily&startTime&endTime&id=<csv>` | баннеры × день с привязкой к кампании |
| `/report-ajax?method=campaigns-statistics&startTime&endTime&id=<csv>` | итог по кампаниям (несёт охват) |

`id` — список ID кампаний через запятую (из справочника).

### 3.3. Даты — критично

- `startTime` / `endTime` — **Unix-время в миллисекундах** (секунды × 1000; полночь UTC).
- ⚠️ **`endTime` ВКЛЮЧАЕТ свой день.** Для одного дня D:
  - `campaigns-statistics-daily`: `startTime == endTime == D` (вернёт только D);
  - `statistics-per-banners-per-days`: **`[D, D+1]`** — этот метод **отвергает нулевой диапазон**
    (`startTime==endTime` → `400`); из ответа брать только строки с `day == D`;
  - охват: `endTime = D` → накопительно за `[глобальная дата начала, D]`.
- Пустой период → тело `null` (для per-banners) — трактовать как «нет данных».

### 3.4. Сжатие и надёжность

- **Обязательно `Accept-Encoding: gzip`.** Помимо экономии, это обходит сетевой затык: на части сетей
  несжатые ответы >~16 КБ «зависают» (воспроизведено). Клиент, посылающий gzip и распаковывающий ответ,
  проблемы не имеет (в большинстве HTTP-библиотек — по умолчанию).
- Явных rate-limit не наблюдалось; при сетевой ошибке/таймауте/протухшей сессии — повтор с
  экспоненциальным backoff (старт 2 сек, до 5 повторов) и перелогином.
- Таймаут запроса — крупный (эндпоинты медленные): 120 сек.

### 3.5. Подводные камни данных

- **Деньги (`budget`) — десятичные ₽** (float), в отличие от целочисленных денег некоторых площадок.
- **Охват (`amountIFA`) неаддитивен** (уникальные пользователи): **нельзя суммировать по дням**; берётся
  только накопительно и только из метода `campaigns-statistics` (в `campaign-list` = 0; в
  `campaigns-statistics-daily` приходит фиктивной константой по всем дням — не использовать).
- **`URL` баннера не уникален** за день: одна ссылка встречается несколькими строками (разные баннеры) →
  агрегировать суммой по `(day, URL)`.
- **Привязка баннера к кампании** — НЕ парсингом URL (в `URL` зашит код медиаплана, а не имя кампании;
  у части ссылок, напр. `yandex.maps`, меток нет вовсе). Использовать `campaigns-banners-daily`, где у
  баннера есть `url` (посимвольно = `URL`) и `campaign` (id) → джойн к справочнику.
- В `campaigns-statistics-daily` поля `type`/`status`/`owner`/`group` **пустые** — брать из справочника по `id`.

---

## 4. Публичные функции (контракты)

### 4.1. get_campaign_dict() — справочник кампаний

`GET /ajax?method=campaign-list&startTime=<глоб.дата начала>&endTime=<вчера>&status=all&type=all`.
Дедупликация по `id`. **5 колонок:**

| Поле | Тип | Источник |
|------|-----|----------|
| `id` | string | `id` (ObjectId) |
| `name` | string | `name` |
| `type` | string | `type` (`rtb`=баннер / `vast`=видео) |
| `bidType` | string | `bidType` (`click`/`show`) |
| `status` | string | `status` (`active`/`stopped`/`paused`) |

### 4.2. get_campaigns_daily_stat(date_from, date_to) — кампания × день

Перебор дней; на каждый день — `GET /report-ajax?method=campaigns-statistics-daily&startTime=D&endTime=D&id=<все id>`.
Ответ — объект `{ "YYYY-MM-DD": [ {кампания, state}, … ] }`. **12 колонок:**
`date`, `id`, `name`, и из `state`: `win` (показы), `click`, `budget` (₽, float, округл. 2),
`bid`, `auction`, `firstQuartile`, `midpoint`, `thirdQuartile`, `complete` (видео 25/50/75/100%; у баннеров = 0).

### 4.3. get_banners_daily_stat(date_from, date_to) — баннер × день

На каждый день D:
- метрики — `GET /statistics/statistics-per-banners-per-days?startTime=D&endTime=D+1`, оставить `day==D`,
  агрегировать суммой по `URL`;
- `campaign_id` — из `GET /report-ajax?method=campaigns-banners-daily&startTime=D&endTime=D+1&id=<все id>`
  (карта `url → campaign`).

**6 колонок:** `date`, `campaign_id`, `URL`, `show`, `click`, `complete`.

### 4.4. get_reach_cumulative(global_start_date, date_from, date_to) — накопительный охват

На каждый день D: `GET /report-ajax?method=campaigns-statistics&startTime=<глоб.дата начала>&endTime=D&id=<все id>`;
`reach = amountIFA`. **5 колонок:** `date`, `campaign_id`, `name`, `reach`, `increment`, где
`increment[D] = reach[D] − reach[D−1]`.
> ⚠️ `date_from` должен быть ≥ глобальной даты начала. Если `date_from` = глобальной дате начала — для
> первого дня `increment = reach` (прироста «до» нет). Если `date_from` **позже** — для корректного
> `increment` первого дня взять baseline: `reach` за `(date_from − 1)` и вычесть его. Иначе первая строка
> получит весь накопленный охват вместо дневного прироста.

---

## 5. Алгоритм (общий шаблон)

```
1. login() → session-cookie (форма + Referer/Origin). Перелогин по TTL / {"err": "no access"}.
2. Справочник: GET campaign-list [глоб.дата начала, вчера] → список кампаний, дедуп по id.
3. Статистика по дням: для каждого дня D — 1 запрос (endTime по правилам §3.3), развернуть, склеить.
4. Охват: для каждого дня D — запрос за [глоб.дата начала, D], взять amountIFA, посчитать increment.
5. Все запросы — с gzip и ретраями; ответ null/{} → нет данных.
```

---

## 6. Примеры запросов и ответов (реальные)

### 6.1. Логин
```
POST https://my.yabbi.me/login?method=account
Content-Type: application/x-www-form-urlencoded
Referer: https://my.yabbi.me/login?method=account
Origin: https://my.yabbi.me

login=<LOGIN>&password=<PASSWORD>
→ 302 на /campaign?method=list; Set-Cookie: as-account-session=…; Max-Age=3600
```

### 6.2. Справочник кампаний
```
GET /ajax?method=campaign-list&startTime=1780272000000&endTime=1782777600000&status=all&type=all
→ [ { "id":"69cf967d4fda22c9bfa33a69", "name":"Перекрёсток_Усиление Select_apr-aug_2026",
      "type":"rtb", "bidType":"show", "status":"active", "state":{…}, … }, … ]
```

### 6.3. Кампании × день
```
GET /report-ajax?method=campaigns-statistics-daily&startTime=1782864000000&endTime=1782864000000&id=69cf967d…
→ { "2026-07-01": [ { "id":"69cf967d…", "name":"Перекрёсток…",
      "state": { "win":294, "click":0, "budget":7.49, "bid":410, "auction":410,
                 "firstQuartile":0,"midpoint":0,"thirdQuartile":0,"complete":0, … } } ] }
```

### 6.4. Баннеры × день
```
GET /statistics/statistics-per-banners-per-days?startTime=1782864000000&endTime=1782950400000
→ [ { "day":"2026-07-01", "URL":"https://trk.mail.ru/c/olnrs6?…", "show":17840, "click":119, "complete":0 }, … ]

GET /report-ajax?method=campaigns-banners-daily&startTime=…&endTime=…&id=<csv>
→ { "2026-07-01": [ { "id":"…", "campaign":"6a0c6fea…", "url":"https://trk.mail.ru/c/olnrs6?…", "state":{…} }, … ] }
```

### 6.5. Охват (накопительно)
```
GET /report-ajax?method=campaigns-statistics&startTime=1780272000000&endTime=1782864000000&id=<csv>
→ [ { "id":"69cf967d…", "amountIFA":78469, "state":{…} }, … ]
(1780272000000 = 2026-06-01, 1782864000000 = 2026-07-01; amountIFA — накопительно за [06-01, 07-01])
```

---

## 7. Примеры таблиц на выходе (реальные строки)

### 7.1. get_campaign_dict
| id | name | type | bidType | status |
|---|---|---|---|---|
| 69cf967d4fda22c9bfa33a69 | Перекрёсток_Усиление Select_apr-aug_2026 | rtb | show | active |
| 69a5819293bf90dfd5b7dff7 | Чижик_mar-apr_2026 OLV | vast | show | stopped |

### 7.2. get_campaigns_daily_stat
| date | id | name | win | click | budget | bid | auction | firstQuartile | midpoint | thirdQuartile | complete |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-01 | 6a0c6fea… | Пятёрочка_Гарантия низкой цены_may-jul'26 | 850 | 6 | 24.32 | 1680 | 1680 | 0 | 0 | 0 | 0 |

### 7.3. get_banners_daily_stat
| date | campaign_id | URL | show | click | complete |
|---|---|---|---|---|---|
| 2026-07-01 | 6a0c5cbf… | https://trk.mail.ru/c/olnrs6?…aud_other | 8195 | 98 | 0 |

### 7.4. get_reach_cumulative
| date | campaign_id | name | reach | increment |
|---|---|---|---|---|
| 2026-06-29 | 69cf967d… | Перекрёсток_Усиление Select_apr-aug_2026 | 68811 | 3481 |
| 2026-06-30 | 69cf967d… | Перекрёсток_Усиление Select_apr-aug_2026 | 74975 | 6164 |
| 2026-07-01 | 69cf967d… | Перекрёсток_Усиление Select_apr-aug_2026 | 78469 | 3494 |

> Пример при `date_from = 2026-06-29` (> глобальной даты начала 2026-06-01): `increment` первого дня =
> прирост за день (`reach[06-29] − reach[06-28]` через baseline), а не весь накопленный охват. Если бы
> `date_from` = глобальной дате начала, для первого дня `increment` = `reach`.

---

## 8. Рекомендации по реализации

- **HTTP-клиент** с session-хранилищем cookie, автоматическим gzip и retry-middleware.
- **Логин**: форма + заголовки Referer/Origin; кэшировать сессию, перелогинивать по TTL (~1 ч) и на `{"err":…}`.
- **Даты**: строго по §3.3 (единица — мс; `endTime` инклюзивный; per-banners — `[D, D+1]` + фильтр по `day`).
- **Охват**: только накопительно, из `campaigns-statistics`; не суммировать по дням.
- **Баннер→кампания**: только через `campaigns-banners-daily` (`url`==`URL`), не парсить URL.
- **Забор по дням** для статистики; крупные ответы держать малыми (gzip + по 1 дню).
- **Константы:** `HTTP_TIMEOUT_SEC=120`, `RETRY_MAX=5`, `RETRY_BASE_SEC=2`, `SESSION_TTL_SEC=3600`.

---

## 9. Критерии приёмки

- [ ] Все 4 функции возвращают колонки и порядок из §4.
- [ ] Логин формой с Referer/Origin; сессия автоматически переустанавливается при истечении.
- [ ] Даты: `endTime` инклюзивный учтён; per-banners не падает на одном дне; охват накопительный (монотонный).
- [ ] Охват берётся из `campaigns-statistics` и НЕ суммируется по дням.
- [ ] `URL` агрегируется суммой по `(date, URL)`; `campaign_id` проставляется из `campaigns-banners-daily`.
- [ ] gzip включён; крупные выгрузки не «висят».
- [ ] README + `.env.example` (`YABBI_LOGIN`, `YABBI_PASSWORD`, `YABBI_GLOBAL_START_DATE`).
