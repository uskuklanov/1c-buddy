# 1c-buddy-mcp

Минимальный MCP-сервер для [code.1c.ai](https://code.1c.ai): восемь инструментов, stdio по умолчанию, HTTP MCP — по желанию.

Это отдельный, урезанный дистрибутив полного пакета [`1c-buddy`](../README.md). Здесь нет веб-чата, OpenAI-совместимого API, статики и `tiktoken` — только MCP.

## Установка

```powershell
# stdio (для Codex, IDE и любого MCP-клиента поверх stdin/stdout)
python -m pip install .\mcp-package

# stdio + HTTP MCP
python -m pip install ".\mcp-package[http]"
```

После публикации:

```powershell
pip install 1c-buddy-mcp
pip install "1c-buddy-mcp[http]"
```

## Несовместим с полным пакетом в одном venv

`1c-buddy` и `1c-buddy-mcp` — **альтернативы, а не дополнения**. Ставьте в venv что-то одно.

Причина: оба дистрибутива кладут в окружение одни и те же файлы — модули пространства `app/` (`app/config.py`, `app/mcp/*` и другие) и команду `1c-buddy-mcp`. Для pip это два независимых пакета, и про общие файлы он не знает. Поэтому:

- **при установке** второй пакет молча перезапишет файлы первого;
- **при удалении** `pip uninstall` любого из двух снесёт общие файлы, и второй останется без части своих модулей — сломается.

Из второго пункта следует неочевидное: удалить «лишний» пакет и на этом успокоиться нельзя. `pip uninstall 1c-buddy-mcp` в таком окружении не чинит его, а как раз ломает `1c-buddy`. Безопасный путь один — **снести оба и поставить нужный заново**:

```powershell
pip uninstall -y 1c-buddy 1c-buddy-mcp
pip install <нужный пакет>
```

### Что делает сам инструмент

Если оба пакета всё-таки оказались рядом, `1c-buddy-mcp` при запуске это обнаружит, откажется работать (код возврата `2`) и напечатает те же две команды восстановления.

Но это **диагностика, а не защита**: она не может отменить уже выполненный `pip uninstall` — файлы к тому моменту удалены, — и не сработает, если установленный `1c-buddy` собран из версии репозитория, где этой проверки ещё не было.

## Запуск

```powershell
# stdio — режим по умолчанию, подкоманду можно не писать
1c-buddy-mcp --env-file .env
1c-buddy-mcp stdio --env-file .env

# HTTP MCP (нужен extra [http])
1c-buddy-mcp http --env-file .env
```

Флаги: `--env-file`, `--log-level`, а для `http` ещё `--host` (по умолчанию `127.0.0.1`), `--port` (`6002`), `--reload`. Их можно писать и до подкоманды, и после.

### Codex

```toml
[mcp_servers.onec-buddy]
command = 'C:\Users\<user>\.codex\mcp\1c-buddy\.venv\Scripts\1c-buddy-mcp.exe'
startup_timeout_sec = 30

[mcp_servers.onec-buddy.env]
ONEC_AI_TOKEN = "<your_1c_ai_token>"
ONEC_AI_UI_LANGUAGE = "russian"
MCP_TOOL_CALL_MODE = "direct"
```

## Переменные окружения

`ONEC_AI_TOKEN` обязателен. Пустой или состоящий из пробелов токен — ошибка конфигурации: процесс завершится с кодом `2` ещё до MCP-handshake, а не будет молча ходить в 1C.ai без учётных данных.

Остальные (`ONEC_AI_UI_LANGUAGE`, `ONEC_AI_TIMEOUT`, `MCP_TOOL_CALL_MODE`, `SSL_VERIFY`, прокси) — те же, что у полного пакета, см. [README_FULL.md](../README_FULL.md).

`.env` **никогда** не подхватывается автоматически из текущего каталога — только через `--env-file`. Существующее окружение приоритетнее файла.

## HTTP-режим

Extra `[http]` поднимает минимальный FastAPI ровно с тремя маршрутами:

| Маршрут | Назначение |
|---|---|
| `POST /mcp` | MCP JSON-RPC: `initialize`, `tools/list`, `tools/call` |
| `GET /mcp` | имя и версия сервера |
| `GET /health` | `{"status": "ok", "version": "..."}` |

Ни `/chat`, ни `/v1`, ни `/docs`, ни `/openapi.json` — документация FastAPI отключена.

## Инструменты

Те же восемь, что и в полном пакете, с теми же схемами:

`ask_1c_ai`, `explain_1c_syntax`, `check_1c_code`, `modify_1c_code`, `search_1c_documentation`, `search_its`, `fetch_its`, `diff_1c_documentation_versions`.

## Сборка

```powershell
python -m build mcp-package --wheel --outdir dist
```

Флаг `--wheel` обязателен. Исходники `app/` не копируются в этот каталог — они подтягиваются из `../app` при сборке (`force-include`), поэтому sdist не поддерживается: wheel, собранный из распакованного sdist, не найдёт `../app`.

## Лицензия

AGPL-3.0-only, как и у полного пакета.
