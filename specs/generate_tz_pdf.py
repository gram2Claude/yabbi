# -*- coding: utf-8 -*-
"""Генератор PDF из финального ТЗ (specs/TZ_yabbi_automate.md, версия 2026-07-20 ФИНАЛ).

PDF — ПРОИЗВОДНЫЙ артефакт для передачи разработчику; источник правды — Markdown-ТЗ.
После правок md перегенерировать: python specs/generate_tz_pdf.py (из корня проекта).
Требует: pip install fpdf2. Выход: TZ_yabbi_automate.pdf в корне проекта.
Шаблон-основа: test/tz_templates/11_template_generate_tz_pdf.py.
"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONT_REG = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
FONT_ITAL = r"C:\Windows\Fonts\ariali.ttf"
FONT_MONO = r"C:\Windows\Fonts\consola.ttf"

NX = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

API_NAME = "Yabbi (my.yabbi.me)"
MODULE_NAME = "yabbi_automate"
OUT_FILE = f"TZ_{MODULE_NAME}.pdf"


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("arial", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Стр. {self.page_no()}", align="C")


def make_pdf() -> PDF:
    p = PDF(unit="mm", format="A4")
    p.set_margins(left=15, top=15, right=15)
    p.set_auto_page_break(auto=True, margin=15)
    p.add_font("arial", "", FONT_REG)
    p.add_font("arial", "B", FONT_BOLD)
    p.add_font("arial", "I", FONT_ITAL)
    p.add_font("mono", "", FONT_MONO)
    p.add_page()
    return p


pdf = make_pdf()


def H1(text):
    pdf.set_font("arial", "B", 16)
    pdf.set_text_color(20, 20, 20)
    pdf.ln(2)
    pdf.multi_cell(0, 8, text, **NX)
    pdf.ln(1)


def H2(text):
    pdf.set_font("arial", "B", 13)
    pdf.set_text_color(30, 30, 90)
    pdf.ln(2)
    pdf.multi_cell(0, 7, text, **NX)
    pdf.ln(1)


def P(text):
    pdf.set_font("arial", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5, text, **NX)
    pdf.ln(0.5)


def BUL(items):
    pdf.set_font("arial", "", 10)
    pdf.set_text_color(30, 30, 30)
    for it in items:
        pdf.cell(5)
        pdf.cell(3, 5, "•")
        pdf.multi_cell(0, 5, it, **NX)
    pdf.ln(0.5)


def CODE(text):
    pdf.set_font("mono", "", 8.5)
    pdf.set_text_color(20, 20, 20)
    pdf.set_fill_color(245, 245, 245)
    pdf.multi_cell(0, 4.2, text, fill=True, border=0, **NX)
    pdf.ln(0.5)


def TABLE(headers, rows, widths):
    pdf.set_font("arial", "B", 9)
    pdf.set_fill_color(220, 225, 240)
    pdf.set_text_color(20, 20, 20)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font("arial", "", 9)
    fill = False
    for row in rows:
        max_lines = 1
        for val, w in zip(row, widths):
            lines = pdf.multi_cell(w, 4.5, val, dry_run=True, output="LINES")
            max_lines = max(max_lines, len(lines))
        h = 4.5 * max_lines
        if pdf.get_y() + h > pdf.h - 15:
            pdf.add_page()
        for val, w in zip(row, widths):
            x, y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(w, 4.5, val, border=1, fill=fill, max_line_height=4.5)
            pdf.set_xy(x + w, y)
        pdf.ln(h)
        fill = not fill
    pdf.ln(1)


# ── Титул ─────────────────────────────────────────────────────────────────────
pdf.set_font("arial", "B", 20)
pdf.set_text_color(20, 30, 90)
pdf.multi_cell(0, 10, "Техническое задание", **NX)
pdf.set_font("arial", "B", 14)
pdf.set_text_color(60, 60, 60)
pdf.multi_cell(0, 8, f"Выгрузка статистики {API_NAME} — портирование на другой язык", **NX)
pdf.ln(2)
pdf.set_font("arial", "I", 10)
pdf.set_text_color(100, 100, 100)
pdf.multi_cell(
    0, 5,
    "Версия 2026-07-20 — ФИНАЛ (подтверждена заказчиком после двойного независимого ревью). "
    "Цель — портировать функциональность на целевой язык (PHP / Go / Java / ...) с сохранением "
    "структуры выходных данных. Документ самодостаточен; доступ к эталонному Python-коду не требуется.",
    **NX,
)
pdf.ln(3)

# ── 1. Цель ───────────────────────────────────────────────────────────────────
H1("1. Цель проекта")
P("Разработать библиотеку выгрузки статистики из рекламного кабинета Yabbi (my.yabbi.me). "
  "У площадки НЕТ публичного API — данные забираются из личного кабинета рекламодателя по "
  "cookie-сессии, а «методы» передаются в параметрах URL. Библиотека отдаёт 3 таблицы:")
BUL([
    "справочник кампаний;",
    "статистику по кампаниям по дням;",
    "статистику по баннерам по дням.",
])
P("Выход каждой функции — массив строк (таблица) с фиксированным набором и порядком колонок "
  "(разделы 4-5). Накопительный охват (amountIFA, метод campaigns-statistics) в объём НЕ входит.")

# ── 2. Общая логика ───────────────────────────────────────────────────────────
H1("2. Общая логика")
BUL([
    "Авторизация — один раз логинимся формой, получаем session-cookie, дальше все запросы идут с ней.",
    "Справочник кампаний — один запрос за окно [глобальная дата начала, вчера включительно].",
    "Статистика (кампании/баннеры) — по одному дню за запрос, склеиваем дни; "
    "id кампаний в /report-ajax — батчами по 5 (раздел 3.4).",
    "Обогащение — каждая таблица дополняется стандартными константными и вычисляемыми полями "
    "(раздел 4): account_id, source_type_id, id_key_*, для расходов — блок НДС/комиссии.",
])

H2("2.1. Конфигурация (нормативно)")
TABLE(
    ["Параметр", "Формат", "Назначение"],
    [
        ["YABBI_LOGIN, YABBI_PASSWORD", "string",
         "креды кабинета (вкладка «Рекламодатель»)"],
        ["YABBI_GLOBAL_START_DATE", "YYYY-MM-DD",
         "глобальная дата начала — startTime окна справочника campaign-list; используется во ВСЕХ "
         "трёх функциях (список кампаний всегда берётся за глобальное окно, раздел 5). "
         "Обязательный: отсутствие/невалидность = ошибка конфигурации. Для приёмки (раздел 10) = 2026-06-01."],
    ],
    [58, 26, 96],
)

# ── 3. Принципы ───────────────────────────────────────────────────────────────
H1(f"3. Ключевые принципы работы с {API_NAME}")

H2("3.1. Авторизация (cookie-сессия)")
BUL([
    "Вход: POST https://my.yabbi.me/login?method=account, тело application/x-www-form-urlencoded, "
    "поля login, password (вкладка «Рекламодатель»).",
    "(!) ОБЯЗАТЕЛЬНЫ заголовки Referer: https://my.yabbi.me/login?method=account и "
    "Origin: https://my.yabbi.me. Без них сервер отвечает «Неправильный логин или пароль» (антибот).",
    "Успех = редирект на /campaign?method=list + cookies as-account-session (HttpOnly), as-account, csrf.",
    "TTL сессии ~1 час (Max-Age=3600), продлевается каждым запросом. Клиент должен перелогиниваться "
    "сам по TTL и при ответе {\"err\": \"no access\"} (признак потерянной сессии).",
    "Капчи/2FA/CSRF-поля в форме нет.",
])

H2("3.2. Базовый URL и эндпоинты")
P("BASE_URL = https://my.yabbi.me. Все запросы данных — GET, ответ — JSON (Content-Type: text/plain).")
TABLE(
    ["Метод (в URL)", "Назначение"],
    [
        ["/ajax?method=campaign-list&startTime&endTime&status=all&type=all", "справочник кампаний"],
        ["/report-ajax?method=campaigns-statistics-daily&startTime&endTime&id=<csv>", "кампании x день"],
        ["/statistics/statistics-per-banners-per-days?startTime&endTime", "баннеры x день (аккаунт целиком)"],
        ["/report-ajax?method=campaigns-banners-daily&startTime&endTime&id=<csv>", "привязка баннер -> кампания"],
    ],
    [118, 62],
)
P("id — список ID кампаний через запятую (из справочника), батчами (раздел 3.4). "
  "На все GET к кабинету слать Referer: https://my.yabbi.me/campaign?method=list и непустой "
  "User-Agent — так делает эталон; безопасный дефолт против антибота (для GET обязательность "
  "не подтверждена, но и не опровергнута).")

H2("3.3. Даты — КРИТИЧНО (московские сутки)")
BUL([
    "startTime / endTime — Unix-время в миллисекундах.",
    "Сутки Yabbi бакетируются по МОСКОВСКОЙ полуночи (UTC+3), НЕ по UTC. Все границы дней считать "
    "в таймзоне Europe/Moscow: полночь дня D МСК = D 00:00:00+03:00 -> мс. (Полночь UTC сдвигает "
    "окно на 3 часа: дневной бакет теряет 00:00-03:00 МСК, цифры расходятся с кабинетом — проверено сверкой.)",
    "(!) startTime == endTime возвращает НЕ весь день, а лишь стартовый ~часовой бакет (занижение "
    "в 15-20 раз; кампании без ночного трафика выпадают вовсе). НЕ использовать никогда.",
    "campaigns-statistics-daily и campaigns-banners-daily: окно [D 00:00 МСК, D+1 00:00 МСК]; "
    "ответ keyed по датам — брать только ключ D, хвостовой бакет D+1 отбрасывать.",
    "statistics-per-banners-per-days: то же окно [D, D+1] (метод отвергает нулевой диапазон — "
    "startTime==endTime -> 400); из ответа брать только строки с day == D.",
    "Справочник campaign-list: startTime = глобальная дата начала (00:00 МСК), endTime = конец "
    "вчерашнего дня МСК (последняя мс дня, т.е. полночь сегодня МСК минус 1 мс).",
    "Пустой период -> тело null (для per-banners) — трактовать как «нет данных».",
])

H2("3.4. Медленный /report-ajax — id батчами")
BUL([
    "/report-ajax тратит ~5-7 секунд НА КАЖДУЮ кампанию из параметра id; полный список (40+ id) "
    "одним запросом в плохие дни не отвечает вовсе (скорость плавает день ко дню).",
    "Поэтому id кампаний передавать батчами по ID_CHUNK = 5 (каждая кампания ровно в одном батче), "
    "ответы склеивать (для keyed-ответов — слияние по датным ключам).",
    "Таймаут запроса — крупный: 180 сек (батч из 5 id — ~30-35 с, с запасом).",
])

H2("3.5. Сжатие и надёжность")
BUL([
    "Обязательно Accept-Encoding: gzip. Помимо экономии, это обходит сетевой затык: на части сетей "
    "несжатые ответы >~16 КБ «зависают» (воспроизведено). Клиент, посылающий gzip и распаковывающий "
    "ответ, проблемы не имеет (в большинстве HTTP-библиотек — по умолчанию).",
    "Явных rate-limit не наблюдалось; при сетевой ошибке/таймауте/протухшей сессии — повтор с "
    "экспоненциальным backoff (старт 2 сек, до 5 повторов) и перелогином.",
])

H2("3.6. Подводные камни данных")
BUL([
    "Маппинг метрик на кабинет («Мои кампании»), сверено до единицы: «Показы» = state.win, "
    "«Видимость» = state.load, «Клики» = state.click; CTR кабинета = click / win. "
    "(!) Поле state.view — это НЕ «Видимость» (оно чуть больше load) — не использовать.",
    "Деньги (state.budget) — десятичные рубли (float). (!) Расход Yabbi — БЕЗ НДС (раздел 4.3).",
    "URL баннера не уникален за день: одна ссылка встречается несколькими строками (разные баннеры) "
    "-> агрегировать суммой по (day, URL).",
    "Привязка баннера к кампании — НЕ парсингом URL (в URL зашит код медиаплана, а не имя кампании; "
    "у части ссылок, напр. yandex.maps, меток нет вовсе). Использовать campaigns-banners-daily, где "
    "у баннера есть url (посимвольно = URL) и campaign (id).",
    "В campaigns-statistics-daily поля type/status/owner/group пустые — при необходимости брать из "
    "справочника по id кампании.",
    "ID кампании — строка (Mongo ObjectId, напр. 69cf967d4fda22c9bfa33a69) — не приводить к числу.",
])

# ── 4. Стандарт выходных таблиц ───────────────────────────────────────────────
H1("4. Стандарт выходных таблиц (нейминг + обогащение)")

H2("4.1. Нейминг")
P("Все имена колонок — snake_case, английский. Дата = date (YYYY-MM-DD, день метрик). "
  "Идентификаторы — с суффиксом _id (голого id в выходных таблицах нет). Метрики: показы -> "
  "impressions, клики -> clicks, расход -> costs_nds, видео-досмотры 25/50/75/100% -> "
  "video_views_25 / video_views_50 / video_views_75 / video_views_100. Поля load, bid, auction "
  "аналога в стандарте не имеют и сохраняют имена источника. Имён кампаний в таблицах статистики "
  "НЕТ — только в справочнике (join по campaign_id).")

H2("4.2. Обязательное обогащение (константы и ключи)")
P("Каждая таблица дополняется полями (значения констант — заглушки, заменяются при интеграции; "
  "вынести в конфиг/константы модуля):")
TABLE(
    ["Константа", "Значение-заглушка", "Куда идёт"],
    [
        ["account_id", "1 (integer)", "все таблицы"],
        ["source_type_id", "9 (integer)", "все таблицы"],
        ["product_id", "1 (integer)", "только справочник"],
        ["product_name", "\"prod_test\" (string)", "только справочник"],
        ["camp_type", "\"camp_test\" (string)", "только справочник"],
        ["camp_category", "\"cat_test\" (string)", "только справочник"],
        ["owner_id", "1 (integer)", "только справочник"],
        ["ak", "0.5 (float, агентская комиссия 50%)", "статистика кампаний"],
    ],
    [36, 74, 70],
)
P("Составные ключи (string, разделитель \"_\"):")
BUL([
    "id_key_camp = \"<account_id>_\" + campaign_id -> напр. 1_69cf967d4fda22c9bfa33a69. "
    "(!) Префикс собирать из константы account_id, не хардкодить литерал \"1_\".",
    "id_key_ad = id_key_camp + \"_\" + url — только в таблице баннеров (своего id у баннера в Yabbi "
    "нет, идентификатор — url; ключ получается длинным — это нормально). Для баннера без найденной "
    "кампании campaign_id, id_key_camp, id_key_ad = null.",
])

H2("4.3. Деньги и НДС (только статистика кампаний)")
BUL([
    "costs_nds <- state.budget: float, округление до 2 знаков сразу после чтения, до вычисления "
    "производных. Режим округления — half-to-even («банковское», как pandas.Series.round(2) в "
    "эталоне); half-up даст расхождение +-0.01 на значениях вида .xx5.",
    "(!) Yabbi отдаёт расход БЕЗ НДС. По конвенции пайплайна колонка всё равно называется costs_nds "
    "и хранит значение источника КАК ЕСТЬ (единый контракт всех источников заказчика; семантическая "
    "оговорка фиксируется в README порта). Производные считаются единой формулой:",
    "costs_without_nds = costs_nds / делитель_НДС, где делитель зависит от ГОДА значения date "
    "строки: год >= 2026 -> 1.22 (ставка 22%), год < 2026 -> 1.20 (20%). Считать per-row.",
    "costs_nds_ak = costs_nds x (1 + ak) = costs_nds x 1.5.",
    "costs_without_nds_ak = costs_without_nds x (1 + ak).",
    "Производные не округлять (только costs_nds — round 2).",
])

# ── 5. Публичные функции ──────────────────────────────────────────────────────
H1("5. Публичные функции (контракты)")

H2("5.1. get_campaign_dict() — справочник кампаний")
P("GET /ajax?method=campaign-list&startTime=<глоб. дата начала 00:00 МСК>&endTime=<конец вчера МСК>"
  "&status=all&type=all. Строки ответа без id пропускать (до приведения к строке, построения "
  "id_key_camp и дедупликации). Дедупликация по campaign_id (выживает первая строка). "
  "13 колонок (порядок фиксирован):")
TABLE(
    ["#", "Колонка", "Тип", "Источник"],
    [
        ["1", "campaign_id", "string", "id (ObjectId)"],
        ["2", "campaign_name", "string", "name"],
        ["3", "campaign_type", "string", "type (rtb=баннер / vast=видео)"],
        ["4", "bid_type", "string", "bidType (click/show)"],
        ["5", "status", "string", "status (active/stopped/paused)"],
        ["6", "account_id", "integer", "константа"],
        ["7", "source_type_id", "integer", "константа"],
        ["8", "product_id", "integer", "константа"],
        ["9", "product_name", "string", "константа"],
        ["10", "camp_type", "string", "константа"],
        ["11", "camp_category", "string", "константа"],
        ["12", "id_key_camp", "string", "\"<account_id>_\" + campaign_id"],
        ["13", "owner_id", "integer", "константа"],
    ],
    [10, 44, 22, 104],
)

H2("5.2. get_campaigns_daily_stat(date_from, date_to) — кампания x день")
P("Список id кампаний — из справочника 5.1 за ГЛОБАЛЬНОЕ окно [глоб. дата начала, вчера], НЕ за "
  "[date_from, date_to] запроса (справочник период-зависим: короткое окно вернёт меньше кампаний, "
  "и статистика окажется занижена). Перебор дней; на каждый день D — GET "
  "/report-ajax?method=campaigns-statistics-daily с окном [D 00:00 МСК, D+1 00:00 МСК] и id=<батч "
  "из 5> (кол-во запросов на день = ceil(N кампаний / 5)). Ответ — объект "
  "{ \"YYYY-MM-DD\": [ {кампания, state}, ... ] } — брать только ключ D. Строки без id кампании "
  "пропускать. 19 колонок (порядок фиксирован):")
TABLE(
    ["#", "Колонка", "Тип", "Источник"],
    [
        ["1", "date", "date", "ключ объекта ответа (YYYY-MM-DD)"],
        ["2", "campaign_id", "string", "id"],
        ["3", "impressions", "int", "state.win («Показы» кабинета)"],
        ["4", "load", "int", "state.load («Видимость» кабинета; имя источника)"],
        ["5", "clicks", "int", "state.click"],
        ["6", "costs_nds", "float", "state.budget, round 2 ((!) БЕЗ НДС, раздел 4.3)"],
        ["7", "bid", "int", "state.bid (участия в торгах)"],
        ["8", "auction", "int", "state.auction"],
        ["9", "video_views_25", "int", "state.firstQuartile (0 у rtb, >0 у vast)"],
        ["10", "video_views_50", "int", "state.midpoint"],
        ["11", "video_views_75", "int", "state.thirdQuartile"],
        ["12", "video_views_100", "int", "state.complete"],
        ["13", "costs_without_nds", "float", "вычисление, раздел 4.3"],
        ["14", "ak", "float", "константа"],
        ["15", "costs_nds_ak", "float", "вычисление, раздел 4.3"],
        ["16", "costs_without_nds_ak", "float", "вычисление, раздел 4.3"],
        ["17", "account_id", "integer", "константа"],
        ["18", "source_type_id", "integer", "константа"],
        ["19", "id_key_camp", "string", "раздел 4.2"],
    ],
    [10, 46, 20, 104],
)

H2("5.3. get_banners_daily_stat(date_from, date_to) — баннер x день")
P("На каждый день D (окна — [D 00:00 МСК, D+1 00:00 МСК]): метрики — GET "
  "/statistics/statistics-per-banners-per-days, оставить строки day == D, строки без URL пропустить, "
  "агрегировать СУММОЙ show/click/complete по URL; карта url -> campaign — GET "
  "/report-ajax?method=campaigns-banners-daily&id=<батчи по 5> (id — из справочника 5.1 за "
  "глобальное окно, как в 5.2), брать только ключ D; привязка: per-banners.URL == "
  "campaigns-banners-daily.url -> campaign. 10 колонок (порядок фиксирован):")
TABLE(
    ["#", "Колонка", "Тип", "Источник"],
    [
        ["1", "date", "date", "day"],
        ["2", "campaign_id", "string / null", "карта url -> campaign"],
        ["3", "url", "string", "URL (идентификатор баннера)"],
        ["4", "impressions", "int", "сумма show по (date, url)"],
        ["5", "clicks", "int", "сумма click"],
        ["6", "video_views_100", "int", "сумма complete (досмотры видео 100%)"],
        ["7", "account_id", "integer", "константа"],
        ["8", "source_type_id", "integer", "константа"],
        ["9", "id_key_camp", "string / null", "раздел 4.2 (null, если кампания не найдена)"],
        ["10", "id_key_ad", "string / null", "id_key_camp + \"_\" + url (null, если кампания не найдена)"],
    ],
    [10, 40, 26, 104],
)
P("Расходов на уровне баннера у источника нет — денежный блок (раздел 4.3) не применяется.")

# ── 6. Алгоритм ───────────────────────────────────────────────────────────────
H1("6. Алгоритм (общий шаблон)")
CODE("""1. login() -> session-cookie (форма + Referer/Origin).
   Перелогин по TTL / {"err": "no access"}.
2. Справочник: GET campaign-list [глоб. дата начала 00:00 МСК, конец вчера МСК]
   -> список кампаний, дедуп по id -> campaign_ids.
3. Статистика по дням: для каждого дня D - запросы с окном [D, D+1] МСК
   (report-ajax - батчами id по 5), из ответа только день D, склеить.
4. Переименовать поля по контрактам раздела 5, добавить обогащение раздела 4.
5. Все запросы - с gzip и ретраями; ответ null/{} -> нет данных
   (вернуть пустую таблицу с полным набором колонок).""")

# ── 7. Примеры ────────────────────────────────────────────────────────────────
H1("7. Примеры запросов и ответов (реальные)")
P("Все таймстампы — московские полуночи: 2026-07-01 00:00 МСК = 1782853200000, "
  "2026-07-02 00:00 МСК = 1782939600000, 2026-06-01 00:00 МСК = 1780261200000, "
  "конец дня 2026-07-01 МСК = 1782939599999. Примеры даны «как при запуске 2026-07-02» "
  "(тогда «вчера» = 2026-07-01 — контрольный день приёмки, раздел 10).")

H2("7.1. Логин")
CODE("""POST https://my.yabbi.me/login?method=account
Content-Type: application/x-www-form-urlencoded
Referer: https://my.yabbi.me/login?method=account
Origin: https://my.yabbi.me

login=<LOGIN>&password=<PASSWORD>
-> 302 на /campaign?method=list;
   Set-Cookie: as-account-session=...; Max-Age=3600""")

H2("7.2. Справочник кампаний (окно [глоб. дата начала, конец вчера МСК])")
CODE("""GET /ajax?method=campaign-list&startTime=1780261200000
    &endTime=1782939599999&status=all&type=all
-> [ { "id":"69cf967d4fda22c9bfa33a69",
       "name":"Перекрёсток_Усиление Select_apr-aug_2026",
       "type":"rtb", "bidType":"show", "status":"active",
       "state":{...}, ... }, ... ]""")

H2("7.3. Кампании x день (окно [D, D+1] МСК; id — батч <=5)")
CODE("""GET /report-ajax?method=campaigns-statistics-daily
    &startTime=1782853200000&endTime=1782939600000
    &id=69cf967d...,6a0c5cbf...
-> { "2026-07-01": [ { "id":"69cf967d...", "name":"Перекрёсток...",
       "state": { "win":4958, "load":4931, "click":42, "budget":198.22,
                  "bid":8670, "auction":8670, "firstQuartile":0,
                  "midpoint":0, "thirdQuartile":0, "complete":0, ... } } ],
     "2026-07-02": [ ... хвостовой бакет - ОТБРОСИТЬ ... ] }""")

H2("7.4. Баннеры x день")
CODE("""GET /statistics/statistics-per-banners-per-days
    ?startTime=1782853200000&endTime=1782939600000
-> [ { "day":"2026-07-01", "URL":"https://trk.mail.ru/c/olnrs6?...",
       "show":17840, "click":119, "complete":0 }, ... ]

GET /report-ajax?method=campaigns-banners-daily
    &startTime=1782853200000&endTime=1782939600000&id=<батч>
-> { "2026-07-01": [ { "id":"...", "campaign":"6a0c6fea...",
       "url":"https://trk.mail.ru/c/olnrs6?...", "state":{...} }, ... ] }""")

# ── 8. Примеры таблиц ─────────────────────────────────────────────────────────
H1("8. Примеры таблиц на выходе (реальные строки, 2026-07-01)")

H2("8.1. get_campaign_dict — справочник")
TABLE(
    ["campaign_id", "campaign_name", "campaign_type", "bid_type", "status"],
    [
        ["69cf967d4fda22c9bfa33a69", "Перекрёсток_Усиление Select_apr-aug_2026", "rtb", "show", "active"],
        ["69a5819293bf90dfd5b7dff7", "Чижик_mar-apr_2026 OLV", "vast", "show", "stopped"],
    ],
    [46, 70, 26, 18, 20],
)
P("Константные поля и вычисляемый ключ (для тех же 2 строк в том же порядке):")
TABLE(
    ["account_id", "source_type_id", "product_id", "product_name", "camp_type", "camp_category", "owner_id", "id_key_camp"],
    [
        ["1", "9", "1", "prod_test", "camp_test", "cat_test", "1", "1_69cf967d4fda22c9bfa33a69"],
        ["1", "9", "1", "prod_test", "camp_test", "cat_test", "1", "1_69a5819293bf90dfd5b7dff7"],
    ],
    [18, 24, 18, 22, 20, 24, 14, 40],
)
P("Значения констант — заглушки, при интеграции заменить на актуальные (раздел 4.2).")

H2("8.2. get_campaigns_daily_stat — кампания x день")
TABLE(
    ["date", "campaign_id", "impressions", "load", "clicks", "costs_nds", "bid", "auction"],
    [
        ["2026-07-01", "69cf967d4fda22c9bfa33a69", "4958", "4931", "42", "198.22", "8670", "8670"],
    ],
    [20, 44, 22, 14, 14, 20, 14, 16],
)
P("video_views_25/50/75/100 для этой строки = 0/0/0/0 (кампания rtb, не видео). "
  "Денежный блок и константы (та же строка):")
TABLE(
    ["costs_without_nds", "ak", "costs_nds_ak", "costs_without_nds_ak", "account_id", "source_type_id", "id_key_camp"],
    [
        ["162.47541", "0.5", "297.33", "243.713115", "1", "9", "1_69cf967d4fda22c9bfa33a69"],
    ],
    [28, 10, 22, 32, 18, 24, 46],
)
P("Производные показаны так, как их печатает эталон (полный float без принудительного округления, "
  "отображение может усекать хвост); контракт — формулы раздела 4.3, не количество знаков.")

H2("8.3. get_banners_daily_stat — баннер x день")
TABLE(
    ["date", "campaign_id", "url", "impressions", "clicks", "video_views_100"],
    [
        ["2026-07-01", "6a452cec175b4776e85f9e45",
         "https://eye.targetads.io/view/click?pid=12795&cn=36058&...", "59120", "634", "49490"],
    ],
    [20, 42, 66, 20, 14, 18],
)
P("Константы и ключи (та же строка): account_id = 1, source_type_id = 9, "
  "id_key_camp = 1_6a452cec175b4776e85f9e45, "
  "id_key_ad = 1_6a452cec175b4776e85f9e45_https://eye.targetads.io/view/click?pid=12795&cn=36058&...")

# ── 9. Рекомендации ───────────────────────────────────────────────────────────
H1("9. Рекомендации по реализации")
BUL([
    "HTTP-клиент с session-хранилищем cookie, автоматическим gzip и retry-middleware.",
    "Логин: форма + заголовки Referer/Origin; кэшировать сессию, перелогинивать по TTL (~1 ч, "
    "с запасом ~2 мин) и на {\"err\": ...}.",
    "Даты: строго раздел 3.3 — единица мс, границы по МСК; окно дня [D, D+1] + фильтр по дню; "
    "startTime==endTime НЕ использовать никогда.",
    "Батчинг: id в /report-ajax — по 5; keyed-ответы сливать по датным ключам.",
    "Баннер -> кампания: только через campaigns-banners-daily (url == URL), не парсить URL.",
    "Константы: HTTP_TIMEOUT_SEC=180, RETRY_MAX=5, RETRY_BASE_SEC=2, SESSION_TTL_SEC=3600, "
    "SESSION_REFRESH_LEEWAY_SEC=120, ID_CHUNK=5 + константы обогащения раздела 4.2 (в конфиге, заглушки).",
    "Обогащение — применять до финального упорядочивания колонок; порядок колонок = раздел 5.",
])

# ── 10. Критерии приёмки ──────────────────────────────────────────────────────
H1("10. Критерии приёмки")
BUL([
    "Все 3 функции возвращают колонки, типы и порядок ровно по разделу 5 (включая обогащение раздела 4).",
    "Логин формой с Referer/Origin; сессия автоматически переустанавливается (TTL, {\"err\": ...}).",
    "Даты: границы суток — московские; день забирается окном [D, D+1] с фильтром по дню; "
    "per-banners не падает на одном дне; startTime==endTime нигде не используется.",
    "id в /report-ajax уходят батчами <=5; полная выгрузка дня на 40+ кампаниях не «висит».",
    "Контрольная сверка за 2026-07-01 (impressions / load / clicks, до единицы; выполняется на живом "
    "кабинете с кредами заказчика; имена кампаний — через join статистики со справочником по "
    "campaign_id, т.к. имён в статистике нет): «Пятёрочка_Fame to Flame_jul_2026» = 348563 / 324747 "
    "/ 2179; «Перекрёсток_Усиление Select_apr-aug_2026» = 4958 / 4931 / 42; «Чижик_Имидж_jul_2026» "
    "= 59120 / 53513 / 634. Денежный блок: costs_without_nds = costs_nds/1.22, costs_nds_ak = "
    "costs_nds x 1.5 (проверить на любой строке).",
    "Баннеры: агрегация суммой по (date, url); campaign_id — из campaigns-banners-daily; у баннеров "
    "без кампании campaign_id/id_key_camp/id_key_ad = null (не строка \"None\").",
    "gzip включён; крупные выгрузки не «висят».",
    "README + .env.example (YABBI_LOGIN, YABBI_PASSWORD, YABBI_GLOBAL_START_DATE); в README "
    "зафиксирована оговорка раздела 4.3 (расход Yabbi — без НДС, costs_nds хранит как есть).",
])

pdf.output(OUT_FILE)
print(f"OK: {OUT_FILE}")
