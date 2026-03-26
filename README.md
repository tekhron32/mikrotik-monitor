# NebulaNet Monitor v1.0

Система мониторинга сети на базе MikroTik с AI-анализом доменов.

## Стек
- **Backend**: FastAPI + Python
- **Frontend**: Vanilla JS (Single HTML)
- **БД**: PostgreSQL + ClickHouse + Redis
- **Инфра**: Docker Compose
- **Router**: MikroTik RouterOS 7.x

## Архитектура
```
MikroTik (192.168.1.200)
  ├── NetFlow v9 → :2055/udp
  └── Syslog DNS → :514/udp
          ↓
    Collector (Python)
          ↓
  ClickHouse (flows, dns_log)
  PostgreSQL (devices, users, categories, blocks)
          ↓
    FastAPI → Dashboard (port 8000)
```

## Быстрый старт

### 1. Клонирование
```bash
git clone git@github.com:boykulov/mikrotik-monitor.git
cd mikrotik-monitor
```

### 2. Настройка .env
```bash
cp .env.example .env
nano .env
```

Заполни:
```env
POSTGRES_PASSWORD=your_password
CLICKHOUSE_PASSWORD=your_password
ADMIN_PASSWORD=your_admin_password
ANTHROPIC_API_KEY=sk-ant-...
MIKROTIK_HOST=192.168.1.200
MIKROTIK_USER=nebulanet
MIKROTIK_PASS=your_mikrotik_password
MIKROTIK_ADMIN_PASS=your_admin_password
```

### 3. Запуск
```bash
docker compose up -d
```

### 4. Настройка MikroTik
```routeros
# Создать пользователя
/user add name=nebulanet password=YourPass group=write

# NetFlow
/ip traffic-flow set enabled=yes interfaces=all
/ip traffic-flow set active-flow-timeout=1m inactive-flow-timeout=15s
/ip traffic-flow target add dst-address=SERVER_IP port=2055 version=9

# DNS логирование
/ip dns set allow-remote-requests=yes
/system logging action set remote remote=SERVER_IP remote-port=514
/system logging add topics=dns action=remote
/system logging add topics=dhcp action=remote

# DNS редирект (для каждого интерфейса)
/ip firewall nat add chain=dstnat protocol=udp dst-port=53 \
  in-interface=User action=redirect to-ports=53
/ip firewall nat add chain=dstnat protocol=tcp dst-port=53 \
  in-interface=User action=redirect to-ports=53
```

## Структура проекта
```
mikrotik-monitor/
├── api/
│   ├── main.py          # FastAPI backend
│   ├── dashboard.html   # Single-page frontend
│   └── requirements.txt
├── collector/
│   └── main.py          # NetFlow + DNS collector
├── migrations/
│   ├── clickhouse/      # ClickHouse схемы
│   └── postgres/        # PostgreSQL схемы
├── docker-compose.yml
├── .env.example
└── README.md
```

## API эндпоинты

### Мониторинг
| Метод | URL | Описание |
|-------|-----|----------|
| GET | /api/devices | Список устройств |
| GET | /api/reports/summary | Общая статистика |
| GET | /api/reports/dns-activity | DNS активность |
| GET | /api/reports/ip-activity | Активность по IP |
| GET | /api/reports/device-traffic | Трафик по устройствам |
| GET | /api/reports/device-categories | Категории по устройствам |
| GET | /api/reports/domain-users | Кто заходил на домен |

### Категории
| Метод | URL | Описание |
|-------|-----|----------|
| GET | /api/domain-categories | Все категории |
| POST | /api/domain-categories | Сохранить категорию |
| DELETE | /api/domain-categories/{name} | Удалить категорию |
| GET | /api/domain-category?domain=X | AI анализ домена |

### Блокировки
| Метод | URL | Описание |
|-------|-----|----------|
| GET | /api/block/list | Список блокировок |
| POST | /api/block/domain | Заблокировать домен |
| POST | /api/block/unblock | Разблокировать |
| POST | /api/block/toggle | Вкл/выкл блокировку |
| GET | /api/mikrotik/subnets | Подсети из MikroTik |

### Отделы
| Метод | URL | Описание |
|-------|-----|----------|
| GET | /api/departments | Список отделов |
| POST | /api/departments | Добавить IP в отдел |
| DELETE | /api/departments/{dept}/members/{ip} | Удалить из отдела |

## Функции

### Мониторинг
- Real-time DNS мониторинг (NetFlow v9 + Syslog)
- 161+ устройств с онлайн статусом
- Категории активности: Работа / Соцсети / Игры / Развлечения / Система
- Фильтр времени: 1ч / 24ч / Всё
- Трафик: 1ч / 1д / 7д / 30д
- Поиск по IP, имени, MAC
- Фильтр по типу: ПК / Телефон / SIP / Другие

### AI анализ
- Категоризация доменов через Claude API
- Учёт кастомных правил компании
- Анализ субдоменов
- Проверка на вирусы/фишинг
- Пакетный анализ всех доменов пользователя

### Блокировки (MikroTik)
- Блокировка по отделу (address-list)
- Блокировка по подсети
- Вкл/выкл без удаления
- Автоматическое создание firewall правил
- Синхронизация с MikroTik

## База данных

### PostgreSQL
```sql
devices          -- устройства с last_seen
users            -- пользователи
domain_categories -- категории доменов (535+)
blocked_domains  -- история блокировок
departments      -- отделы (через MikroTik address-list)
```

### ClickHouse
```sql
flows     -- NetFlow данные (TTL 90 дней)
dns_log   -- DNS запросы (TTL 90 дней)
```

## Сервер
- **IP**: 192.168.1.53
- **OS**: Ubuntu 24
- **User**: tehron
- **Path**: /home/tehron/nebulanet

## Команды
```bash
# Запуск
docker compose up -d

# Логи коллектора
docker compose logs collector -f

# Логи API
docker compose logs api -f

# Перезапуск после изменений
docker compose up -d --build api

# Бэкап PostgreSQL
docker exec nebulanet-postgres pg_dump -U nebulanet nebulanet > backup.sql

# Статус
docker compose ps
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|--------------|
| POSTGRES_PASSWORD | Пароль PostgreSQL | nebulanet_secret |
| CLICKHOUSE_PASSWORD | Пароль ClickHouse | nebulanet_secret |
| ADMIN_PASSWORD | Пароль админки | admin2024 |
| ANTHROPIC_API_KEY | Claude API ключ | — |
| MIKROTIK_HOST | IP MikroTik | 192.168.1.200 |
| MIKROTIK_USER | Пользователь MikroTik | nebulanet |
| MIKROTIK_PASS | Пароль пользователя | — |
| MIKROTIK_ADMIN_PASS | Пароль admin | — |

## Лицензия
MIT
