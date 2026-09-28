# Архитектура

Независимый сервис (без форка сторонних репозиториев), Python/FastAPI,
SQLite, server-rendered UI (Jinja2 + немного vanilla JS).

## Пайплайн

```
Источники (RSS / сайты / Telegram / датасеты / прокси-API)
    │  адаптеры: fetch_raw() [сеть] → parse() [чистая функция, тестируется без сети]
    ▼
Article в БД (нормализация языка, извлечение CVE/CWE-тегов)
    ▼
Кандидаты за окно дайджеста (48ч daily / 31д monthly)
    ▼
Дедупликация: exact (нормализованный URL) + fuzzy (rapidfuzz, окно времени)
    ▼
Ранжирование: BM25(интересы профиля) + свежесть + доверие к источнику + feedback-сигнал
    ▼
Диверсифицированный top-K (кап на долю одного источника, round-robin довыбор)
    ▼
Кластеризация тем: TF-IDF + KMeans, подпись кластера — LLM или TF-IDF fallback
    ▼
Саммари каждой статьи: LLM-провайдер (pluggable) → extractive fallback при недоступности
    ▼
Markdown (+ персистентность в БД) → data/digests/*.md, отдача через веб-UI
```

## Модули

| Модуль | Ответственность |
|---|---|
| `app/sources/*` | Адаптеры источников: `base.SourceAdapter` (fetch_raw/parse), `rss`, `website`, `telegram`, `dataset`, `proxy`, `registry` |
| `app/pipeline/*` | `normalize` (язык, CVE/CWE-теги), `dedup`, `ranking` (BM25 + фидбек + свежесть + доверие), `clustering` (TF-IDF/KMeans), `types` (DB-agnostic dataclasses) |
| `app/llm/*` | `base.LLMProvider` интерфейс, `ollama_provider`, `openai_compatible_provider`, `anthropic_provider`, `extractive_fallback`, `factory.build_provider` (+ `FallbackProvider` graceful degradation) |
| `app/digest/*` | `builder.select_for_profile` / `build_digest` (оркестрация), `markdown.render_markdown` (детерминированный рендер) |
| `app/api/*` | FastAPI-роутеры: sources, profiles, digest, feedback, metrics, settings, compare |
| `app/models.py` | SQLAlchemy ORM: Source, Article, Profile, Feedback, DigestRun, DigestArticle, AppSetting |
| `app/metrics.py` | Расчёт метрик качества (см. `docs/metrics.md`) |
| `app/scheduler.py` | APScheduler: ежедневная/ежемесячная автогенерация дайджестов для всех профилей |
| `app/templates/`, `app/static/` | Тёмный SOC-интерфейс (server-rendered Jinja2 + CSS + минимальный JS) |
| `scripts/seed_fixtures.py`, `scripts/run_demo.py` | Загрузка демо-корпуса и end-to-end прогон без веб-сервера |

## Почему так

- **`fetch_raw` / `parse` разделены** в каждом адаптере источников: `parse`
  — чистая функция без сети, поэтому все 5 адаптеров тестируются на
  зафиксированных примерах ответов без реального HTTP.
- **`select_for_profile` вынесен из `build_digest`**: страница «Сравнение
  профилей» прогоняет ранжирование дважды без побочных эффектов (никаких
  LLM-вызовов, ничего не пишется в БД) — сравнение быстрое и бесплатное.
- **LLM — не хард-зависимость**: `FallbackProvider` перехватывает любую
  ошибку основного провайдера (сеть недоступна, нет ключа, таймаут) и
  подставляет экстрактивное саммари. Дайджест генерируется всегда, даже
  без единого настроенного LLM.
- **PipelineArticle вместо ORM-объектов** внутри pipeline/*: избегает
  DetachedInstanceError при работе вне сессии и делает ranking/dedup/
  clustering тестируемыми без БД.

## Источники данных для организаторов

Датасеты организаторов подключаются как источник типа `dataset` (JSON/CSV,
настраиваемый маппинг полей) или `proxy` (произвольный HTTP/JSON API с
заголовками и путём к списку статей в ответе) — см. `docs/sources.md`. Ни
один из адаптеров не форкает и не встраивает сторонний проект целиком:
сервис — самостоятельная кодовая база в этом репозитории.
