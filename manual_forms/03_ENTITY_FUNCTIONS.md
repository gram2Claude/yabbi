# Сущности и функции — Yabbi

Заполнено по зафиксированным решениям (см. `info/00_yabbi_source.md` §5 и память проекта).
Отличие от avito: у Yabbi **нет** сквозного обогащения (`account_id`/`source_type_id`/`id_key_*`,
`costs_nds`/НДС/`ak`) — колонки таблиц минимальны и заданы явно; деньги (`budget`) уже десятичные.

Порядок реализации: справочник → статистика по кампаниям → статистика по баннерам → охват.

---

## Функция 1 — get_campaign_dict()

```
Тип:       Справочник (уникальные кампании, без дат)
Источник:  GET /ajax?method=campaign-list&startTime=<глоб.дата начала>&endTime=<вчера>&status=all&type=all
Обновление: полная перезапись ежедневно; дедуп по id (выживает первая).
Колонки:   id, name, type (rtb=баннер/vast=видео), bidType (click/show), status (active/stopped/paused)
```

## Функция 2 — get_campaigns_daily_stat(date_from, date_to)

```
Тип:       Статистика (кампания × день)
Источник:  GET /report-ajax?method=campaigns-statistics-daily&startTime&endTime&id=<csv id из справочника>
Забор:     по 1 дню за запрос: окно [D 00:00 МСК, D+1 00:00 МСК] + фильтр по ключу дня == D
           (startTime==endTime даёт лишь стартовый ~часовой бакет — см. фикс 2026-07-04);
           id — батчами по ID_CHUNK=5.
Колонки:   date, id, name, win (показы), load (видимость), click, budget (₽, float),
           bid, auction, firstQuartile, midpoint, thirdQuartile, complete (метрики из state)
Примечание: type/status/owner/group в этом методе пустые — берутся из справочника по id.
```

## Функция 3 — get_banners_daily_stat(date_from, date_to)

```
Тип:       Статистика (баннер × день)
Источник:  метрики — GET /statistics/statistics-per-banners-per-days&startTime&endTime (аккаунт целиком);
           привязка campaign_id — GET /report-ajax?method=campaigns-banners-daily&id=<csv>
           (url==URL → campaign; id — батчами по ID_CHUNK=5)
Забор:     по 1 дню за запрос ([D 00:00 МСК, D+1 00:00 МСК], фильтр по day==D —
           per-banners не принимает нулевой диапазон).
Агрегация: сумма show/click/complete по (date, URL) — URL не уникален за день.
Колонки:   date, campaign_id, URL, show, click, complete
```

## Функция 4 — get_reach_cumulative(global_start_date, date_from, date_to)

```
Тип:       Охват — кумулятивная метрика (кампания × день)
Источник:  GET /report-ajax?method=campaigns-statistics&startTime=<глоб.дата начала 00:00 МСК>&endTime=<конец дня D МСК (последняя мс)>&id=<csv, батчами по ID_CHUNK=5>
Логика:    охват (amountIFA) неаддитивен → на каждый день D отдельный запрос за [global_start_date, D];
           reach = amountIFA; increment = reach[D] − reach[D−1] (первый день = reach).
           amountIFA — оценочная метрика: может проседать день-к-дню, increment иногда
           отрицателен — это свойство источника, к 0 не клампить (см. 00_yabbi_source.md §5).
Колонки:   date, campaign_id, name, reach, increment
Примечание: охват есть ТОЛЬКО в методе campaigns-statistics (в campaign-list = 0; в daily — фиктивно-константный).
```
