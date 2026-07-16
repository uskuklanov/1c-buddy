# 1C Buddy - Чат, MCP сервер и OpenAI совместимый API шлюз для общения с 1С:Напарник

Комплексный сервис-шлюз, предоставляющий OpenAI-совместимые API эндпоинты на базе 1C.ai, вместе с веб-интерфейсом чата и интеграцией инструментов MCP (Model Context Protocol). Идеально подходит для интеграции ИИ-помощника 1C:Предприятие в существующие рабочие процессы с OpenAI SDK.

## Возможности

### 🚀 OpenAI-совместимый API
- OpenAI-совместимый формат для `/v1/models` и `/v1/chat/completions`
- Потоковые и непотоковые ответы с поддержкой Server-Sent Events (SSE)
- Bearer-аутентификация для `/v1/*` через `OPENAI_COMPAT_API_KEY`
- Поддержка непрерывности разговора через заголовок `X-1C-Conversation-Id` или `metadata.conversation_id`
- Если `X-1C-Conversation-Id` отсутствует, полный `messages[]` преобразуется во внутренний transcript для нового upstream-контекста
- Если `X-1C-Conversation-Id` передан, upstream-сессия переиспользуется и в upstream отправляется только новый ход
- Автоматическое сопоставление и обработка ошибок
- Специальная поддержка KiloCode VSCode расширения с XML-оберткой ответов
- Поддержка `metadata.create_new_session` и `metadata.programming_language`
- События инструментов upstream отображаются в OpenAI-ответах как текстовые markdown-аннотации, а не как native OpenAI `tool_calls`

### 💬 Веб-интерфейс чата
- Современный, адаптивный интерфейс чата по адресу `/chat`
- Управление историей разговоров с изолированными контекстами (история хранится локально в браузере)
- Ответы в реальном времени с потоковой передачей
- Отдельное отображение tool call / tool result / follow-up блоков
- Опциональные инструкции рабочего пространства для веб-чата
- Опциональное подключение внешних Streamable HTTP MCP серверов из настроек чата
- Выбор активных внешних MCP инструментов для использования агентом в чате
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

### 🔧 Интеграция инструментов MCP
- Streamable HTTP / JSON-RPC 2.0 endpoint по адресу `/mcp`
- Управление сессиями MCP с TTL и автоматической очисткой
- Доступные инструменты:
  - `ask_1c_ai` - общий вопрос по платформе 1С и практическим сценариям
  - `explain_1c_syntax` - объяснение конкретного объекта, метода или конструкции 1С
  - `check_1c_code` - синтаксическая проверка или code review фрагмента кода 1С
  - `modify_1c_code` - изменение кода 1С по явному заданию пользователя
  - `search_1c_documentation` - поиск по документации платформы 1С:Предприятие
  - `search_its` - поиск по базе знаний ИТС
  - `fetch_its` - получение содержимого конкретного документа или раздела ИТС по `id`
  - `diff_1c_documentation_versions` - сравнение документации платформы между двумя версиями
- Прямой MCP tool mode по умолчанию (`MCP_TOOL_CALL_MODE=direct`)
- Валидация входных параметров с ограничениями длины

### 🔄 Управление сессиями и контекстом
- Автоматическое управление сессиями 1C.ai с TTL
- Поддержка до 300 одновременных активных сессий
- Лимиты на размер прикрепляемых файлов (до 100 КБ)
- Глобальный лимит размера входного текста для upstream (`ONEC_AI_INPUT_MAX_LENGTH`, по умолчанию 100000 символов)
- Управление памятью с автоматической очисткой истекших сессий

### 📊 Мониторинг и отладка
- Детальное логирование запросов/ответов с маскировкой чувствительных данных
- Middleware для логирования API вызовов с ограничением размера тела
- Проверка здоровья сервиса (`/health`)
- Подсчет токенов с использованием tiktoken
- Обработка ошибок с маппингом на HTTP статусы

### 🐳 Docker и развертывание
- Оптимизированный Dockerfile на базе Python 3.12-slim
- Docker Compose для простого развертывания
- Healthcheck без дополнительных зависимостей
- Переменные окружения для гибкой конфигурации
- Автоматический рестарт контейнера


## Быстрый старт

1. **Получите токен 1C.ai** с сайта [code.1c.ai](https://code.1c.ai)

2. **Клонируйте и настройте:**
   ```bash
   git clone <repository-url>
   cd 1c-buddy
   cp .env.example .env
   # Отредактируйте .env с вашими токенами
   ```

3. **Запустите с Docker:**
   ```bash
   docker compose up --build -d
   ```

4. **Начните общение:**
   - Веб-интерфейс: http://localhost:6002/chat
   - OpenAI API: используйте любой OpenAI SDK с `base_url="http://localhost:6002/v1"` и `OPENAI_COMPAT_API_KEY`
   - MCP endpoint: `http://localhost:6002/mcp`

## Установка и развертывание

### Предварительные требования

- Для Docker: Docker & Docker Compose
- Для нативного запуска: Python 3.10+
- Аккаунт code.1c.ai с доступом к API
- Минимум 512MB RAM, 1GB дискового пространства

### Установка пакета

Проект устанавливается как Python-пакет. Зависимости разделены на extras, чтобы каждый режим ставил только то, что ему нужно:

| Команда | Что ставится | Для чего |
|---|---|---|
| `pip install ".[http]"` | FastAPI, Uvicorn, tiktoken | Чат, HTTP MCP, OpenAI API |
| `pip install ".[stdio]"` | MCP Python SDK | Только MCP через stdin/stdout |
| `pip install ".[all]"` | всё сразу | Оба режима |
| `pip install -e ".[all,dev]"` | + pytest, build, hatchling | Разработка |

`pip install -r requirements.txt` продолжает работать: файл стал shim и разворачивается в `.[http]` (запускать из корня репозитория).

После установки доступны две команды: `1c-buddy` (HTTP или stdio) и `1c-buddy-mcp` (сразу stdio).

### Минимальный MCP-only wheel

Если нужен **только MCP-сервер** (Codex, IDE), есть отдельный дистрибутив `1c-buddy-mcp` в каталоге [`mcp-package/`](mcp-package/README.md). В нём нет ни чата, ни OpenAI-совместимого API, ни статики, ни `tiktoken` — только MCP и его восемь инструментов.

```powershell
# stdio
python -m pip install .\mcp-package
1c-buddy-mcp --env-file .env

# stdio + HTTP MCP (/mcp и /health)
python -m pip install ".\mcp-package[http]"
1c-buddy-mcp http --env-file .env
```

Оба дистрибутива ставят console script с одним и тем же именем — `1c-buddy-mcp`. Поэтому конфиг Codex, который указывает на `...\Scripts\1c-buddy-mcp.exe`, работает с любым из них: при переезде с полного пакета на минимальный править конфиг не нужно.

> **Ставить рядом с полным пакетом нельзя.** `1c-buddy` и `1c-buddy-mcp` — альтернативы, а не дополнения.
>
> Причина в том, что оба дистрибутива кладут в venv одни и те же файлы: модули пространства `app/` (`app/config.py`, `app/mcp/*` и другие) и команду `1c-buddy-mcp`. Для pip это два независимых пакета, и он не знает, что файлы общие. Отсюда два следствия:
>
> - **при установке** второй пакет молча перезапишет файлы первого;
> - **при удалении** `pip uninstall` любого из двух снесёт общие файлы — и второй пакет останется без половины своих модулей, то есть сломается.
>
> Именно поэтому удалить «лишний» пакет и на этом успокоиться нельзя: `pip uninstall 1c-buddy-mcp` в таком venv не чинит окружение, а как раз и ломает `1c-buddy`. Единственный безопасный путь — **снести оба и поставить один**:
>
> ```powershell
> pip uninstall -y 1c-buddy 1c-buddy-mcp
> pip install <нужный пакет>
> ```
>
> **Что делает сам инструмент.** Если оба пакета всё-таки оказались в одном venv, команда `1c-buddy-mcp` при запуске это обнаружит, откажется работать (код возврата 2) и напечатает те же две строки восстановления. Команда `1c-buddy` при этом продолжит работать, если версии обоих пакетов совпадают (тогда общие файлы одинаковы), и откажется, если версии разные.
>
> Но это **диагностика, а не защита**. Она не может отменить уже выполненный `pip uninstall` — файлы к тому моменту уже удалены. И она не сработает, если установленный у вас `1c-buddy` собран из версии репозитория, где этой проверки ещё не было: старый код о ней просто не знает.

Сборка wheel вручную (флаг `--wheel` обязателен — исходники `app/` подтягиваются из родительского каталога, поэтому sdist не поддерживается):

```powershell
python -m build mcp-package --wheel --outdir dist
```

> **Windows vs Linux/macOS.** Исполняемые файлы виртуального окружения лежат в разных каталогах:
>
> | | Python | Команда |
> |---|---|---|
> | Windows | `.venv\Scripts\python.exe` | `.venv\Scripts\1c-buddy.exe` |
> | Linux / macOS | `.venv/bin/python` | `.venv/bin/1c-buddy` |
>
> Ниже все команды приведены для обеих ОС. Если активировать окружение (`.\.venv\Scripts\Activate.ps1` или `source .venv/bin/activate`), можно писать просто `1c-buddy` без пути.

### Локальная разработка

1. **Установите зависимости.**

    Windows (PowerShell):
    ```powershell
    py -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install -e ".[all,dev]"
    ```

    Linux / macOS:
    ```bash
    python3 -m venv .venv
    ./.venv/bin/python -m pip install -e ".[all,dev]"
    ```

    Ставьте пакет **тем же** Python, что лежит в `.venv`. Если выполнить просто `pip install ".[all]"` системным интерпретатором, команды `1c-buddy` окажутся не в `.venv`, и запуск по пути из venv не сработает.

2. **Настройте переменные окружения:**
    ```bash
    cp .env.example .env
    # Отредактируйте .env с вашими токенами
    ```

3. **Запустите приложение.**

    Windows (PowerShell):
    ```powershell
    & .\.venv\Scripts\1c-buddy.exe --env-file .env http
    # или, без установки пакета:
    & .\.venv\Scripts\python.exe -m app --env-file .env http
    ```

    Linux / macOS:
    ```bash
    ./.venv/bin/1c-buddy --env-file .env http
    # или, без установки пакета:
    ./.venv/bin/python -m app --env-file .env http
    ```

    > **Важно:** приложение **не читает `.env` автоматически** — ни из текущего каталога, ни откуда-либо ещё. Файл подключается только явным флагом `--env-file PATH`. Альтернатива — экспортировать переменные в окружение процесса. Значения уже существующего окружения имеют приоритет над значениями из `--env-file`.
    >
    > Итоговый приоритет: аргументы CLI → окружение процесса → `--env-file` → значения по умолчанию.


### Запуск MCP через stdio (Codex, IDE)

Windows (PowerShell):
```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install ".[stdio]"
[Environment]::SetEnvironmentVariable("ONEC_AI_TOKEN", "<your_1c_ai_token>", "User")
& .\.venv\Scripts\1c-buddy-mcp.exe
```

Linux / macOS:
```bash
python3 -m venv .venv
./.venv/bin/python -m pip install ".[stdio]"
export ONEC_AI_TOKEN=<your_1c_ai_token>
./.venv/bin/1c-buddy-mcp
```

Режим не открывает HTTP-порт и не поднимает чат: он общается по stdin/stdout и предоставляет те же восемь инструментов, что и HTTP `/mcp`, с теми же схемами. Запущенный вручную он будет молча ждать MCP-фреймы на stdin — это нормально, обычно его запускает сам Codex/IDE. Готовые сниппеты конфигурации Codex — в [README.md](README.md#mcp-через-stdio-для-codex--ide).

### Развертывание в Docker

1. **Клонируйте и настройте:**
    ```bash
    git clone <repository-url>
    cd 1c-buddy
    cp .env.example .env
    # Отредактируйте .env с вашими значениями
    ```

2. **Соберите и запустите:**
    ```bash
    docker compose up --build -d
    ```

3. **Проверьте статус:**
    ```bash
    docker compose ps
    curl http://localhost:6002/health
    ```

4. **Просмотр логов:**
    ```bash
    docker compose logs -f 1c-buddy
    ```

5. **Остановите сервис:**
    ```bash
    docker compose down
    ```

## Конфигурация

Создайте файл `.env` на основе `.env.example`:

```bash
# Ключ API шлюза (клиенты используют его для аутентификации)
OPENAI_COMPAT_API_KEY=your_secure_gateway_key

# Учетные данные upstream code.1c.ai
ONEC_AI_TOKEN=your_1c_ai_token_from_code.1c.ai

# Опционально: настройте значения по умолчанию
ONEC_AI_BASE_URL=https://code.1c.ai
ONEC_AI_TIMEOUT=30
PUBLIC_MODEL_ID=1c-buddy

# Управление сессиями
MAX_ACTIVE_SESSIONS=300
SESSION_TTL=3600

# Ограничения
ONEC_AI_INPUT_MAX_LENGTH=100000
MAX_ATTACHED_FILES_SIZE_KB=100
MCP_TOOL_INPUT_MAX_LENGTH=100000

# Проверка TLS исходящих запросов (см. раздел «Прокси и TLS»)
SSL_VERIFY=true

# Контекст проекта для MCP-инструментов (опционально)
DEFAULT_SSL_VERSION=
DEFAULT_1C_CONFIGURATION=

# Дополнительные настройки веб-чата (опционально)
CHAT_CUSTOM_INSTRUCTIONS_ENABLED=false
CHAT_CUSTOM_MCP_ENABLED=false
CHAT_CUSTOM_INSTRUCTIONS_MAX_LENGTH=4000
CHAT_CUSTOM_MCP_MAX_SERVERS=10
CHAT_CUSTOM_MCP_MAX_TOOLS_PER_SERVER=100
```

### Переменные окружения

#### Основные настройки

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `OPENAI_COMPAT_API_KEY` | Ключ API для аутентификации шлюза | Обязательно |
| `ONEC_AI_TOKEN` | Ваш токен API 1C.ai | Обязательно |
| `ONEC_AI_BASE_URL` | Базовый URL API 1C.ai | `https://code.1c.ai` |
| `ONEC_AI_TIMEOUT` | Таймаут запроса в секундах | `30` |
| `PUBLIC_MODEL_ID` | Имя модели для клиентов | `1c-buddy` |

#### Управление сессиями

`MAX_ACTIVE_SESSIONS` и `SESSION_TTL` применяются только к разговорам чата и OpenAI API. Сессии MCP имеют фиксированный TTL 3600 секунд и не зависят от этих настроек.

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `MAX_ACTIVE_SESSIONS` | Максимум одновременных сессий чата/OpenAI | `300` |
| `SESSION_TTL` | Таймаут сессии чата/OpenAI в секундах | `3600` |

#### Настройки языка и UI

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `ONEC_AI_UI_LANGUAGE` | Язык интерфейса 1C.ai | `russian` |
| `ONEC_AI_PROGRAMMING_LANGUAGE` | Язык программирования по умолчанию | `""` |
| `ONEC_AI_SCRIPT_LANGUAGE` | Язык скриптов по умолчанию | `""` |

#### Ограничения входа

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `ONEC_AI_INPUT_MAX_LENGTH` | Максимальная длина входного текста для upstream | `100000` |

#### Ограничения MCP

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `MCP_TOOL_INPUT_MIN_LENGTH` | Минимальная длина входных данных | `4` |
| `MCP_TOOL_INPUT_MAX_LENGTH` | Максимальная длина входных данных | `100000` |
| `MCP_TOOL_CALL_MODE` | Режим MCP-вызова upstream (`direct` или `standard`) | `direct` |

#### Дополнительные настройки веб-чата

Эти флаги включают расширенные настройки в UI `/chat`. Если оба флага выключены, кнопка настроек в чате не отображается.

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `CHAT_CUSTOM_INSTRUCTIONS_ENABLED` | Разрешить пользовательские инструкции рабочего пространства | `false` |
| `CHAT_CUSTOM_MCP_ENABLED` | Разрешить подключение внешних HTTP MCP серверов из чата | `false` |
| `CHAT_CUSTOM_INSTRUCTIONS_MAX_LENGTH` | Максимальная длина пользовательских инструкций | `4000` |
| `CHAT_CUSTOM_MCP_MAX_SERVERS` | Максимальное количество внешних MCP серверов | `10` |
| `CHAT_CUSTOM_MCP_MAX_TOOLS_PER_SERVER` | Максимальное количество tools на один внешний MCP сервер | `100` |

#### Прокси и TLS

Настройки применяются ко **всем** исходящим HTTPS-соединениям приложения: чат, OpenAI-совместимый API, MCP-upstream к `code.1c.ai` и подключаемые внешние HTTP MCP-серверы.

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `SSL_VERIFY` | Проверять TLS-сертификаты исходящих HTTPS-запросов | `true` |
| `HTTP_PROXY` | Прокси для HTTP | — |
| `HTTPS_PROXY` | Прокси для HTTPS | — |
| `ALL_PROXY` | Прокси для всех схем | — |
| `NO_PROXY` | Список адресов в обход прокси | — |
| `SSL_CERT_FILE` | Путь к доверенному CA bundle (PEM) | — |
| `SSL_CERT_DIR` | Каталог с доверенными CA (альтернатива `SSL_CERT_FILE`) | — |

В `Settings` приложения входит только `SSL_VERIFY`. Остальные переменные — стандартные инфраструктурные, их напрямую обрабатывает `httpx`; приложение не парсит и не переопределяет их.

**Сценарий 1. Обычная работа.** Ничего настраивать не нужно, проверка сертификатов включена:

```dotenv
SSL_VERIFY=true
```

**Сценарий 2. Прозрачный прокси, расшифровывающий HTTPS.** Прокси подменяет цепочку сертификатов на корпоративную — достаточно указать доверенный CA bundle:

```dotenv
SSL_VERIFY=true
SSL_CERT_FILE=/certs/company-ca-bundle.pem
```

**Сценарий 3. Явный прокси.**

```dotenv
SSL_VERIFY=true
SSL_CERT_FILE=/certs/company-ca-bundle.pem

HTTP_PROXY=http://proxy.company.local:3128
HTTPS_PROXY=http://proxy.company.local:3128
NO_PROXY=localhost,127.0.0.1,host.docker.internal
```

**Сценарий 4. Аварийный режим без проверки сертификатов.**

```dotenv
SSL_VERIFY=false

HTTP_PROXY=http://proxy.company.local:3128
HTTPS_PROXY=http://proxy.company.local:3128
NO_PROXY=localhost,127.0.0.1
```

> ⚠️ `SSL_VERIFY=false` отключает проверку подлинности сервера. При перехвате трафика могут быть раскрыты `ONEC_AI_TOKEN`, переписка и вложенные файлы. Используйте только как временную меру, пока не получен корректный CA bundle.

Важные детали:

- При `SSL_VERIFY=false` значение `SSL_CERT_FILE` **не используется**.
- `SSL_CERT_FILE` должен указывать на **полный** PEM-бандл. Если он задан, публичные корневые сертификаты берутся только из него, поэтому в файле должны быть и публичные CA, и корпоративный — иначе перестанут работать остальные HTTPS-соединения.
- Просто положить файл сертификата в контейнер **недостаточно**: путь обязан быть передан через `SSL_CERT_FILE`.
- `NO_PROXY` должен включать адреса локальных MCP-серверов, если они не должны идти через корпоративный прокси.
- При запуске приложение пишет в лог только **факт** наличия прокси или CA bundle. Сами URL прокси, учётные данные и пути к сертификатам не логируются. При `SSL_VERIFY=false` выводится предупреждение уровня `WARNING`.

Передача сертификата в контейнер (образ не меняется):

```bash
docker run \
  -v "$PWD/certs/company-ca-bundle.pem:/certs/company-ca-bundle.pem:ro" \
  -e "SSL_CERT_FILE=/certs/company-ca-bundle.pem" \
  -e "SSL_VERIFY=true" \
  -e "ONEC_AI_TOKEN=<token>" \
  -p 6002:6002 \
  roctup/1c-buddy
```

Основной `docker-compose.yml` намеренно не содержит volume с сертификатом — у большинства пользователей корпоративного CA нет. Для корпоративной установки используйте `docker-compose.override.yml`:

```yaml
services:
  1c-buddy:
    volumes:
      - ./certs/company-ca-bundle.pem:/certs/company-ca-bundle.pem:ro
```

Сами переменные (`SSL_CERT_FILE`, `SSL_VERIFY`, `HTTPS_PROXY`, `NO_PROXY`) кладутся в `.env`, который уже подключён через `env_file`.

#### Логирование и отладка

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `LOG_LEVEL` | Уровень логирования (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `LOG_REQUEST_BODY_MAX_LENGTH` | Максимальный размер тела запроса в логах | `40000` |

#### Файлы и вложения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `MAX_ATTACHED_FILES_SIZE_KB` | Максимальный размер прикрепленных файлов | `100` |

#### Контекст проекта для MCP

Эти переменные задают контекст по умолчанию, который добавляется в запросы к инструментам `ask_1c_ai`, `explain_1c_syntax` и `search_its`. Агент также может передать эти значения явно через параметры инструмента — тогда переданное значение имеет приоритет над дефолтом.

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `DEFAULT_SSL_VERSION` | Версия Библиотеки Стандартных Подсистем (БСП/SSL) по умолчанию | `""` |
| `DEFAULT_1C_CONFIGURATION` | Конфигурация 1С по умолчанию (например: `Бухгалтерия предприятия`, `ERP`) | `""` |

## Использование

### OpenAI-совместимый API

Используйте любой OpenAI SDK или клиентскую библиотеку:

#### Пример на Python
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:6002/v1",
    api_key="your_gateway_key"
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

#### Пример с cURL
```bash
curl -X POST "http://localhost:6002/v1/chat/completions" \
  -H "Authorization: Bearer your_gateway_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "1c-buddy",
    "messages": [{"role": "user", "content": "Что такое ТаблицаЗначений?"}],
    "stream": false
  }'
```

#### Как работает контекст

- Если **заголовок `X-1C-Conversation-Id` отсутствует**, сервер создает новый upstream-разговор и собирает контекст из всего `messages[]`.
- Если **заголовок `X-1C-Conversation-Id` передан**, сервер переиспользует существующую upstream-сессию и отправляет в upstream только новый пользовательский ход.
- Если нужно принудительно начать новую upstream-сессию, передайте заголовок `X-1C-Create-New-Session: true` или `metadata.create_new_session=true`.
- Поле `metadata.programming_language` задаёт язык программирования для нового разговора (`BSL`, `SQL`, `JSON`, `HTTP`).

#### Непрерывность разговора
Используйте заголовок `X-1C-Conversation-Id` для поддержания контекста:

```bash
# Первый запрос
curl -X POST "http://localhost:6002/v1/chat/completions" \
  -H "Authorization: Bearer your_gateway_key" \
  -H "Content-Type: application/json" \
  -d '{"model": "1c-buddy", "messages": [{"role": "user", "content": "Привет"}]}'

# Ответ включает: X-1C-Conversation-Id: conv-123

# Продолжение разговора
curl -X POST "http://localhost:6002/v1/chat/completions" \
  -H "Authorization: Bearer your_gateway_key" \
  -H "X-1C-Conversation-Id: conv-123" \
  -H "Content-Type: application/json" \
  -d '{"model": "1c-buddy", "messages": [{"role": "user", "content": "Расскажи подробнее"}]}'
```

#### Инструменты в OpenAI-ответах

- Внутренние tool call upstream выполняются сервером автоматически.
- В `stream=true` активность инструментов приходит как markdown-текст в `delta.content`: блок вызова, краткий результат, подробности и follow-up модели.
- В `stream=false` эти же блоки включаются в итоговый `message.content`.
- Это совместимо с обычными OpenAI-клиентами, но **не является native OpenAI tools protocol**: сервер не возвращает структурированные `tool_calls` / `tool` messages.

### Поддержка KiloCode
Для интеграции с KiloCode VSCode расширением добавьте метаданные:

```python
response = client.chat.completions.create(
    model="1c-buddy",
    messages=[{"role": "user", "content": "Как создать запрос в 1С?"}],
    metadata={
        "conversation_id": "custom-conv-id",
        "programming_language": "BSL"
    }
)
```

#### SSE события `/chat/api/stream`

Поток событий Server-Sent Events в формате `event: <тип>\ndata: <json>\n\n`:

| Событие | Данные | Описание |
|---------|--------|----------|
| `meta` | `{"conversation_id": "..."}` | Первое событие — ID созданного/переиспользованного разговора |
| `delta` | `{"text": "...", "message_id": "..."}` | Фрагмент текста ответа |
| `reasoning` | `{"text": "..."}` | Дельта reasoning-блока (рассуждения модели) |
| `tool_call` | `{...}` | Начало вызова инструмента upstream |
| `tool_result` | `{...}` | Результат вызова инструмента |
| `tool_followup` | `{...}` | Текст модели после результата инструмента |
| `reset` | `{}` | Upstream перезапустил ответ — клиент должен сбросить накопленный текст |
| `tokens` | `{"input_tokens": N, "output_tokens": N, "total_tokens": N}` | Статистика токенов (перед `done`) |
| `done` | `{}` | Поток завершён |
| `error` | `{"message": "...", "status_code": N}` | Ошибка (за ним следует `done`) |

### Веб-интерфейс чата

Доступ к веб-интерфейсу по адресу `http://localhost:6002/chat`:

- **Чат в реальном времени** с помощником 1C.ai
- **Управление разговорами** - создание, переключение и управление множественными разговорами
- **Подсветка синтаксиса** для блоков кода 1C
- **Адаптивный дизайн** работает на десктопе и мобильных устройствах
- **Функционал экспорта** истории разговоров

#### Настройки чата

Если включены `CHAT_CUSTOM_INSTRUCTIONS_ENABLED` или `CHAT_CUSTOM_MCP_ENABLED`, в верхней панели чата появляется кнопка настроек.

На вкладке **Инструкции** можно задать инструкции рабочего пространства. Они хранятся в `localStorage`, могут экспортироваться/импортироваться JSON-файлом и передаются агенту вместе с сообщениями чата. На первом сообщении нового разговора backend дополнительно усиливает применение этих инструкций, чтобы повысить шанс их учета сразу с первого ответа.

На вкладке **MCP сервера** можно подключить несколько внешних Streamable HTTP MCP серверов. Поддерживаются только URL на `localhost` или private-сетях. Имя сервера должно быть ASCII-идентификатором: латиница, цифры, `_` и `-`, первый символ — буква. Это имя используется в отображаемом имени инструмента вида `<serverName>__<toolName>`.

В UI можно включать/выключать серверы и отдельные tools, обновлять список tools конкретного сервера и выбрать активные инструменты для агента. Одновременно активными могут быть максимум два внешних MCP инструмента. В чате они отображаются как фактические MCP инструменты, например `toolkit__get_metadata`. В раскрывающемся блоке tool result показывается содержимое, которое вернул реальный MCP tool.

#### Параметры запроса `/chat/api/send` и `/chat/api/stream`

| Поле | Тип | Описание |
|------|-----|----------|
| `message` | string | Текст сообщения (обязательно) |
| `conversation_id` | string | ID существующего разговора |
| `create_new_session` | bool | Создать новый разговор (`false` по умолчанию) |
| `programming_language` | string | Язык для нового разговора (`BSL`, `SQL`, и т.д.) |
| `parent_uuid` | string | UUID родительского сообщения для ответа в ветке диалога |
| `workspace_instructions` | string | Пользовательские инструкции рабочего пространства для `/chat/api/stream` |
| `mcp_config` | object | Конфигурация внешних MCP серверов и включенных tools для `/chat/api/stream` |
| `active_mcp_mapping` | object | Первый активный внешний MCP tool для агента |
| `active_mcp_find_mapping` | object | Второй активный внешний MCP tool для агента |

### Интеграция инструментов MCP

Сервис реализует MCP (Model Context Protocol) для интеграции с ИИ-помощниками и инструментами.

#### Два транспорта, один набор инструментов

| Транспорт | Как запускается | Что даёт |
|---|---|---|
| **HTTP** | Docker или `1c-buddy http` | `POST /mcp` (Streamable HTTP, JSON-RPC), плюс чат и опциональный `/v1` |
| **stdio** | `1c-buddy-mcp` или `1c-buddy stdio` | Только MCP через stdin/stdout. Порт не открывается |

Имена инструментов, описания и JSON-схемы у обоих транспортов **идентичны** — они строятся из одного каталога. Различается только оформление результата: HTTP добавляет в текст строки `Сессия:` и `Разговор:`, stdio возвращает чистый результат инструмента, а ошибки помечает флагом `isError`.

#### Валидация аргументов

Аргументы проверяются по объявленной JSON-схеме на обоих транспортах: обязательные поля, типы, `enum`, `minLength` / `maxLength`. Границы длины задаются через `MCP_TOOL_INPUT_MIN_LENGTH` (по умолчанию 4) и `MCP_TOOL_INPUT_MAX_LENGTH`. Незнакомые аргументы игнорируются.

#### Доступные инструменты

1. **`ask_1c_ai`** - Общие вопросы по 1C:Предприятие
   ```json
   {
     "question": "Как правильно использовать HTTPЗапрос?",
     "programming_language": "BSL",
     "ssl_version": "3.2.1",
     "configuration": "Бухгалтерия предприятия"
   }
   ```

2. **`explain_1c_syntax`** - Объяснение конкретных объектов или синтаксиса 1C
   ```json
   {
     "syntax_element": "HTTPСоединение",
     "context": "аутентификация и повторные попытки",
     "ssl_version": "3.2.1",
     "configuration": "Бухгалтерия предприятия"
   }
   ```

3. **`check_1c_code`** - Проверка и валидация кода
   ```json
   {
     "code": "Процедура Тест()\n  Сообщить(\"Привет\");\nКонецПроцедуры",
     "check_type": "syntax",
     "extended": false
   }
   ```

4. **`modify_1c_code`** - Изменение кода 1С по заданию
   ```json
   {
     "instruction": "Добавь проверку заполненности параметра",
     "code": "Процедура Тест(Знач Параметр)\nКонецПроцедуры"
   }
   ```

5. **`search_1c_documentation`** - Поиск по документации платформы
   ```json
   {
     "query": "HTTPСоединение",
     "version": "v8.5.1"
   }
   ```

6. **`search_its`** - Поиск по базе знаний ИТС
   ```json
   {
     "query": "начало работы разработка 1С предприятие обучение",
     "ssl_version": "3.2.1",
     "configuration": "Бухгалтерия предприятия"
   }
   ```

7. **`fetch_its`** - Получение содержимого документа ИТС по `id`
   ```json
   {
     "id": "root"
   }
   ```

8. **`diff_1c_documentation_versions`** - Сравнение документации между версиями
   ```json
   {
     "version_a": "v8.3.26",
     "version_b": "v8.3.27",
     "query": "HTTP соединение"
   }
   ```


## Справочник API

### Основные эндпоинты

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Редирект на `/chat` |
| `/v1/models` | GET | Список доступных моделей, если включен OpenAI API |
| `/v1/chat/completions` | POST | OpenAI-совместимый chat completions endpoint, если включен OpenAI API |
| `/chat` | GET | Веб-интерфейс чата |
| `/chat/api/send` | POST | Отправка сообщения (непотоковый режим) |
| `/chat/api/stream` | POST | Отправка сообщения (потоковый режим SSE) |
| `/chat/api/config` | GET | Конфигурация чата, лимиты и флаги расширенных настроек |
| `/chat/api/mcp/list-tools` | POST | Получение списка tools внешних MCP серверов, если включен `CHAT_CUSTOM_MCP_ENABLED` |
| `/mcp` | POST | Эндпоинт протокола MCP (JSON-RPC) |
| `/mcp` | GET | Информация о MCP сервере |
| `/health` | GET | Проверка здоровья сервиса |

### MCP методы

| Метод | Описание |
|-------|----------|
| `initialize` | Инициализация MCP сессии |
| `initialized` | Подтверждение инициализации |
| `tools/list` | Список доступных инструментов |
| `tools/call` | Вызов инструмента |

### Заголовки запросов

| Заголовок | Описание |
|-----------|----------|
| `Authorization` | Bearer токен для `/v1/*` |
| `X-1C-Conversation-Id` | ID разговора для непрерывности контекста |
| `X-1C-Create-New-Session` | Создать новый разговор (`true`, `1`, `yes`) |
| `x-kilocode-version` | Наличие заголовка активирует режим KiloCode |
| `MCP-Session-Id` | ID сессии MCP (возвращается сервером при `initialize`, передаётся клиентом в последующих запросах) |

### Аутентификация

Bearer-аутентификация сейчас применяется только к OpenAI-совместимым эндпоинтам `/v1/*`.

```http
Authorization: Bearer <OPENAI_COMPAT_API_KEY>
```

Чатовый UI `/chat` и MCP endpoint `/mcp` в текущей реализации не используют gateway API key. Если сервис публикуется наружу, их нужно закрывать обратным прокси, сетевым периметром или отдельной внешней аутентификацией.

### Когда монтируется OpenAI API

Роуты `/v1/models` и `/v1/chat/completions` подключаются только если задан `OPENAI_COMPAT_API_KEY`.

Если переменная не задана:
- `/chat` и `/mcp` продолжают работать
- `/v1/*` не монтируются

### Для MCP

Для MCP используется заголовок сессии:
```
MCP-Session-Id: <session_id>
```

### Коды ошибок

#### HTTP статусы
- `200` - Успешный запрос
- `202` - Запрос принят (для уведомлений MCP)
- `400` - Некорректный запрос / JSON-RPC ошибка
- `401` - Ошибка аутентификации
- `403` - Запрещенный origin
- `404` - Неизвестная сессия MCP / метод не найден
- `429` - Превышен лимит запросов
- `502` - Ошибка upstream 1C.ai
- `500` - Внутренняя ошибка сервера

#### JSON-RPC коды ошибок (MCP)
- `-32600` - Invalid Request
- `-32601` - Method not found / Tool not found
- `-32602` - Invalid params
- `-32603` - Internal error

### Форматы данных

#### Сообщения чата
```json
{
  "role": "user|assistant",
  "text": "Текст сообщения",
  "ts": 1640995200000,
  "files": [
    {
      "name": "example.bsl",
      "size": 1024,
      "content": "Код файла...",
      "type": "text/plain"
    }
  ],
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 20,
    "total_tokens": 30
  }
}
```


