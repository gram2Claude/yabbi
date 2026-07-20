# Сущности и функции — Yabbi

Заполнено по зафиксированным решениям (см. `info/00_yabbi_source.md` §5 и память проекта).
**С 2026-07-20 нейминг и обогащение — по стандарту avito** (snake_case; показы=`impressions`,
клики=`clicks`, расход=`costs_nds`, видео=`video_views_*`; сквозное обогащение
`account_id`/`source_type_id`/`id_key_*` + денежный блок НДС/`ak` — полная сводка
в `info/00_yabbi_source.md` §5.0). Отличия от avito: `campaign_id` — строка (ObjectId);
`budget` Yabbi — БЕЗ НДС (`costs_nds` хранит значение источника, зафиксировано пометкой).

Порядок реализации: справочник → статистика по кампаниям → статистика по баннерам
(охват — функция 4 — в архиве с 2026-07-20).

---

## Функция 1 — get_campaign_dict()

```
Тип:       Справочник (уникальные кампании, без дат)
Источник:  GET /ajax?method=campaign-list&startTime=<глоб.дата начала>&endTime=<вчера>&status=all&type=all
Обновление: полная перезапись ежедневно; дедуп по campaign_id (выживает первая).
Колонки:   campaign_id (← id), campaign_name (← name), campaign_type (← type: rtb=баннер/vast=видео),
           bid_type (← bidType: click/show), status (active/stopped/paused)
           + обогащение справочника: account_id, source_type_id, product_id, product_name,
             camp_type, camp_category, id_key_camp, owner_id
```

## Функция 2 — get_campaigns_daily_stat(date_from, date_to)

```
Тип:       Статистика (кампания × день)
Источник:  GET /report-ajax?method=campaigns-statistics-daily&startTime&endTime&id=<csv id из справочника>
Забор:     по 1 дню за запрос: окно [D 00:00 МСК, D+1 00:00 МСК] + фильтр по ключу дня == D
           (startTime==endTime даёт лишь стартовый ~часовой бакет — см. фикс 2026-07-04);
           id — батчами по ID_CHUNK=5.
Колонки:   date, campaign_id (← id), impressions (← win, показы), load (видимость),
           clicks (← click), costs_nds (← budget, ₽ float, ⚠ у Yabbi БЕЗ НДС), bid, auction,
           video_views_25/50/75/100 (← firstQuartile/midpoint/thirdQuartile/complete)
           + денежный блок: costs_without_nds, ak, costs_nds_ak, costs_without_nds_ak
           + обогащение: account_id, source_type_id, id_key_camp
Примечание: имени кампании в таблице нет (по стандарту — join со справочником по campaign_id);
           type/status/owner/group в этом методе пустые — берутся из справочника.
```

## Функция 3 — get_banners_daily_stat(date_from, date_to)

```
Тип:       Статистика (баннер × день)
Источник:  метрики — GET /statistics/statistics-per-banners-per-days&startTime&endTime (аккаунт целиком);
           привязка campaign_id — GET /report-ajax?method=campaigns-banners-daily&id=<csv>
           (url==URL → campaign; id — батчами по ID_CHUNK=5)
Забор:     по 1 дню за запрос ([D 00:00 МСК, D+1 00:00 МСК], фильтр по day==D —
           per-banners не принимает нулевой диапазон).
Агрегация: сумма show/click/complete по (date, url) — url не уникален за день.
Колонки:   date, campaign_id, url (← URL, идентификатор баннера), impressions (← show),
           clicks (← click), video_views_100 (← complete)
           + обогащение: account_id, source_type_id, id_key_camp,
             id_key_ad (= id_key_camp + "_" + url; расходов на уровне баннера нет)
```

## Функция 4 — get_reach_cumulative(global_start_date, date_from, date_to) — В АРХИВЕ

**⚠ 2026-07-20: перенесена в архив** (пока не нужна) — из библиотеки удалена, рабочий код
`archive/get_reach_cumulative.py`. Спецификация ниже сохранена на случай возврата.

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
