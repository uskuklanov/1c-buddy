# 1C Buddy - Чат, MCP сервер и OpenAI совместимый API шлюз для общения с 1С:Напарник

## Возможности

### 💬 Веб-интерфейс чата
- Современный, адаптивный интерфейс чата
- Управление историей разговоров с изолированными контекстами (история хранится локально в браузере)
- Ответы в реальном времени с потоковой передачей
- Отдельное отображение tool call / tool result / follow-up блоков
- Пользовательские инструкции рабочего пространства
- Подключение внешних HTTP MCP серверов прямо из настроек чата
- Отображение reasoning-дельт в процессе генерации
- Подсветка синтаксиса для кода 1C (BSL) и XML с автоопределением
- Прикрепление файлов (.bsl, .xml, .txt)
- Просмотр содержимого прикрепленных файлов в браузере
- Поиск по содержимому прикрепленных файлов
- Визуализация mermaid диаграмм с возможностью сохранить в png 
- Поиск по истории сообщений
- Экспорт истории разговоров в JSON
- Отображение статистики токенов (входящие/исходящие/всего)
- Копирование сообщений в буфер обмена
- Контекстное меню форматирования кода с горячими клавишами

![Интерфейс чата](chat_ui.png)

### 🔧 MCP сервер
- Два транспорта поверх одного набора инструментов:
  - **HTTP** — `POST /mcp` внутри основного сервиса (нужен запущенный контейнер или `1c-buddy http`)
  - **stdio** — `1c-buddy-mcp` для Codex / IDE: не открывает порт, не поднимает чат, не требует FastAPI
- Доступные инструменты:
  - `ask_1c_ai` - общие вопросы по платформе 1С и практическим сценариям
  - `explain_1c_syntax` - объяснение конкретного объекта, метода или конструкции 1С
  - `check_1c_code` - синтаксическая проверка или code review фрагмента кода 1С
  - `modify_1c_code` - изменение кода 1С по явному заданию пользователя
  - `search_1c_documentation` - поиск по документации платформы 1С:Предприятие
  - `search_its` - поиск по базе знаний ИТС
  - `fetch_its` - получение содержимого конкретного документа или раздела ИТС по `id`
  - `diff_1c_documentation_versions` - сравнение документации платформы между двумя версиями

### 🚀 OpenAI-совместимый API
- OpenAI-совместимый формат для `/v1/models` и `/v1/chat/completions`
- Потоковые и непотоковые ответы с поддержкой Server-Sent Events (SSE)
- Стандартная аутентификация с Bearer токенами


## Быстрый старт

1. **Получите токен code.1c.ai** с сайта [code.1c.ai](https://code.1c.ai)


2. **Запустите с Docker:**
   ```bash
   docker pull roctup/1c-buddy
   
   docker run -d --name 1c-buddy --restart unless-stopped -p 6002:6002 -e "ONEC_AI_TOKEN=<your_1c_ai_token>" roctup/1c-buddy 
   ```
   
   Если нужен также OpenAI API шлюз:
   
   ```bash
   docker pull roctup/1c-buddy
   
   docker run -d --name 1c-buddy --restart unless-stopped -p 6002:6002 -e "ONEC_AI_TOKEN=<your_1c_ai_token>" -e "OPENAI_COMPAT_API_KEY=<your_custom_api_key>" roctup/1c-buddy 
   ```
   

3. **Начните общение:**
   - Веб-интерфейс чата: http://localhost:6002/chat

   Дополнительные настройки чата скрыты по умолчанию. Чтобы включить пользовательские инструкции и внешние MCP серверы, запустите контейнер с флагами:
   ```bash
   docker run -d --name 1c-buddy --restart unless-stopped -p 6002:6002 \
     -e "ONEC_AI_TOKEN=<your_1c_ai_token>" \
     -e "CHAT_CUSTOM_INSTRUCTIONS_ENABLED=true" \
     -e "CHAT_CUSTOM_MCP_ENABLED=true" \
     roctup/1c-buddy
   ```

   После этого в чате появится кнопка настроек. В ней можно задать инструкции рабочего пространства и подключить внешние Streamable HTTP MCP серверы, например `http://192.168.0.1:6003/mcp`.

   **Запуск за корпоративным прокси.** Сертификат передаётся снаружи через volume, образ не меняется:
   ```bash
   docker run -d --name 1c-buddy --restart unless-stopped -p 6002:6002 \
     -v "$PWD/certs/company-ca-bundle.pem:/certs/company-ca-bundle.pem:ro" \
     -e "SSL_CERT_FILE=/certs/company-ca-bundle.pem" \
     -e "HTTPS_PROXY=http://proxy.company.local:3128" \
     -e "NO_PROXY=localhost,127.0.0.1" \
     -e "ONEC_AI_TOKEN=<your_1c_ai_token>" \
     roctup/1c-buddy
   ```

   `SSL_CERT_FILE` должен указывать на **полный** PEM-бандл: если он задан, публичные корневые сертификаты берутся только из него, поэтому в файле должны быть и публичные CA, и корпоративный. Подробности и аварийный режим `SSL_VERIFY=false` — в [README_FULL.md](README_FULL.md#прокси-и-tls).

4. **Настройте MCP для IDE (HTTP-транспорт, нужен запущенный сервис):**
    ```bash
    {
      "mcpServers": {   
        "onec-buddy-mcp": {
          "url": "http://localhost:6002/mcp",
          "connection_id": "1c_buddy_service_001",
          "alwaysAllow": [],
          "type": "streamable-http",
          "timeout": 300,
          "disabled": false
       }
     }
   }
    ```

5.  **Отправляйте запросы по OpenAI API:**

    Используйте любой OpenAI SDK или клиентскую библиотеку:
	
  	```python
  	from openai import OpenAI
  
  	client = OpenAI(
  		base_url="http://localhost:6002/v1",
  		api_key="your_custom_api_key"
  	)
  
  	# Непотоковый режим
  	response = client.chat.completions.create(
  		model="1c-buddy",
  		messages=[{"role": "user", "content": "Как создать HTTPСоединение в 1С?"}]
  	)
  	print(response.choices[0].message.content)
  
  	# Потоковый режим
  	for chunk in client.chat.completions.stream(
  		model="1c-buddy",
  		messages=[{"role": "user", "content": "Объясни объект Запрос"}]
  	):
  		print(chunk.choices[0].delta.content, end="")
  	```


## Запуск без Docker

Проект устанавливается как обычный Python-пакет (требуется Python 3.10+). Зависимости разделены: HTTP-сервису не нужен MCP SDK, а stdio-режиму не нужен FastAPI.

### Нативный HTTP-сервис (чат + HTTP MCP + опциональный OpenAI API)

Windows:
```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install ".[http]"
& .\.venv\Scripts\1c-buddy.exe --env-file .env http
```

Linux / macOS:
```bash
python3 -m venv .venv
./.venv/bin/python -m pip install ".[http]"
./.venv/bin/1c-buddy --env-file .env http
```

Опции: `--host` (по умолчанию `0.0.0.0`), `--port` (`6002`), `--log-level`, `--reload`.

> ⚠️ По умолчанию сервис слушает `0.0.0.0`, а чат и `/mcp` **не имеют встроенной аутентификации**. Не выставляйте порт в недоверенную сеть; для локальной работы используйте `--host 127.0.0.1`. Маршруты `/v1/*` монтируются только при заданном `OPENAI_COMPAT_API_KEY`.

### MCP через stdio для Codex / IDE

Этот режим даёт **только** MCP-инструменты через stdin/stdout: порт не открывается, чат и OpenAI API не поднимаются.

Windows:
```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install ".[stdio]"
[Environment]::SetEnvironmentVariable("ONEC_AI_TOKEN", "<your_1c_ai_token>", "User")
```

Linux / macOS:
```bash
python3 -m venv .venv
./.venv/bin/python -m pip install ".[stdio]"
export ONEC_AI_TOKEN=<your_1c_ai_token>   # лучше прописать в ~/.profile
```

> **Есть и минимальный вариант.** Отдельный дистрибутив [`1c-buddy-mcp`](mcp-package/README.md) содержит только MCP — без чата, OpenAI API, статики и `tiktoken`:
>
> ```powershell
> & .\.venv\Scripts\python.exe -m pip install .\mcp-package          # stdio
> & .\.venv\Scripts\python.exe -m pip install ".\mcp-package[http]"  # + HTTP MCP
> ```
>
> Оба дистрибутива ставят console script с именем `1c-buddy-mcp`, поэтому конфиг Codex ниже подходит и полному пакету, и минимальному. Но ставить их **рядом**, в один venv, нельзя: они делят модули `app/` и саму команду. Подробности и порядок восстановления — в [README_FULL.md](README_FULL.md#минимальный-mcp-only-wheel).

Конфигурация Codex (`~/.codex/config.toml`) — Windows:
```toml
[mcp_servers.onec-buddy]
command = 'C:\Users\<user>\.codex\mcp\1c-buddy\.venv\Scripts\1c-buddy-mcp.exe'
startup_timeout_sec = 30

[mcp_servers.onec-buddy.env]
ONEC_AI_UI_LANGUAGE = "russian"
ONEC_AI_TIMEOUT = "30"
MCP_TOOL_CALL_MODE = "direct"
```

Linux / macOS:
```toml
[mcp_servers.onec-buddy]
command = "/home/<user>/.codex/mcp/1c-buddy/.venv/bin/1c-buddy-mcp"
startup_timeout_sec = 30

[mcp_servers.onec-buddy.env]
ONEC_AI_UI_LANGUAGE = "russian"
ONEC_AI_TIMEOUT = "30"
MCP_TOOL_CALL_MODE = "direct"
```

Токен лучше держать в пользовательском окружении, а не в конфиге. Явная альтернатива — передать файл: `1c-buddy-mcp --env-file C:\path\to\.env`. После изменения пользовательского окружения Codex нужно перезапустить.

`.env` **никогда** не подхватывается автоматически из текущего каталога — только через `--env-file`. Значения уже существующего окружения имеют приоритет над значениями из файла.

## Документация

Подробная документация доступна в [README_FULL.md](README_FULL.md).


## Благодарности

Огромное спасибо автору оригинального проекта MCP сервера для 1С:Напарник: **[artesk/1copilot_MCP](https://github.com/artesk/1copilot_MCP)** 

