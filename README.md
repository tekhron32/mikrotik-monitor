# NebulaNet Network Monitor

> SaaS платформа мониторинга сети на базе MikroTik с AI-анализом трафика

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Архитектура

```
┌─────────────────────────────┐       ┌──────────────────────────────┐
│   v2.0 Super Admin Portal   │◄─────►│   v1.0 Network Monitor       │
│   admin.nebulanet.uz:3001   │  sync │   client-server.com:8000     │
│                             │       │                              │
│  • Управление клиентами     │       │  • Real-time DNS мониторинг  │
│  • Лицензии и биллинг       │       │  • NetFlow v9 аналитика      │
│  • Heartbeat статус          │       │  • AI анализ доменов         │
│  • Синхронизация данных     │       │  • Блокировки через MikroTik │
└─────────────────────────────┘       └──────────────────────────────┘
```

---

## Быстрая установка v1.0 (для клиента)

### Способ 1 — Одна команда
```bash
curl -fsSL https://raw.githubusercontent.com/boykulov/mikrotik-monitor/main/deploy-template/install.sh | sudo bash
```

### Способ 2 — Вручную
```bash
git clone https://github.com/boykulov/mikrotik-monitor.git /opt/nebulanet
cd /opt/nebulanet
sudo bash deploy-template/install.sh
```

Скрипт установит Docker, настроит базы данных, создаст `.env` и запустит все сервисы.

---

## Установка v2.0 Super Admin Portal

### Требования
- Node.js 20+
- PostgreSQL 16
- Redis

### Установка
```bash
# Клонируем репозиторий
git clone https://github.com/boykulov/mikrotik-monitor.git
cd mikrotik-monitor/admin

# Устанавливаем зависимости
npm install

# Настраиваем окружение
cp .env.example .env
nano .env  # Заполни DATABASE_URL и AUTH_SECRET

# Запускаем миграции
npx prisma migrate deploy
npx prisma db seed

# Запускаем
PORT=3001 npm run dev
# или в продакшене:
PORT=3001 npm run build && npm start
```

### Первый вход
- URL: `http://YOUR_SERVER:3001`
- Email: `admin@nebulanet.local`
- Пароль: `NebulaAdmin2024!` (смени после входа в Настройках)

---

## Настройка MikroTik

Выполни на устройстве клиента (RouterOS 7.x):

```routeros
# 1. Создать пользователя для API
/user add name=nebulanet password=YOUR_PASSWORD group=write

# 2. NetFlow — отправка данных о трафике
/ip traffic-flow set enabled=yes interfaces=all
/ip traffic-flow set active-flow-timeout=1m inactive-flow-timeout=15s
/ip traffic-flow target add dst-address=SERVER_IP port=2055 version=9

# 3. DNS логирование через Syslog
/ip dns set allow-remote-requests=yes
/system logging action set remote remote=SERVER_IP remote-port=514
/system logging add topics=dns action=remote
/system logging add topics=dhcp action=remote

# 4. DNS редирект (для перехвата DNS запросов)
/ip firewall nat add chain=dstnat protocol=udp dst-port=53 \
  in-interface=bridge action=redirect to-ports=53
/ip firewall nat add chain=dstnat protocol=tcp dst-port=53 \
  in-interface=bridge action=redirect to-ports=53
```

---

## Добавление нового клиента (пошагово)

### Шаг 1 — Создать организацию в Super Admin
1. Зайди на `admin.nebulanet.uz:3001`
2. Перейди в **Организации → + Добавить**
3. Заполни название, отрасль, тариф
4. Скопируй **License Key** из карточки организации

### Шаг 2 — Развернуть v1.0 на сервере клиента
```bash
# На сервере клиента (Ubuntu 20.04+)
curl -fsSL https://raw.githubusercontent.com/boykulov/mikrotik-monitor/main/deploy-template/install.sh | sudo bash

# Скрипт спросит:
# • Название организации
# • License Key (из шага 1)
# • IP MikroTik
# • Логин/пароль MikroTik API
# • Anthropic API Key (опционально, для AI анализа)
```

### Шаг 3 — Настроить MikroTik
Выполни команды из раздела выше, указав `SERVER_IP` = IP сервера клиента

### Шаг 4 — Проверить работу
- Открой `http://CLIENT_SERVER:8000`
- В Super Admin Dashboard должен появиться **Online** статус для организации
- Heartbeat обновляется каждые 5 минут автоматически

---

## Управление лицензиями

### Заблокировать клиента
В Super Admin → Организации → нажми тогл **Вкл/Выкл**

Клиент немедленно увидит страницу блокировки при обновлении мониторинга.

### Разблокировать
Тот же тогл — клиент снова получает доступ мгновенно.

---

## Стек технологий

### v1.0 — Network Monitor
| Компонент | Технология |
|-----------|-----------|
| Backend | FastAPI + Python 3.12 |
| Frontend | Vanilla JS (Single HTML) |
| База данных | PostgreSQL 16 |
| Аналитика | ClickHouse |
| Кэш | Redis |
| Инфраструктура | Docker Compose |
| Router | MikroTik RouterOS 7.x |
| AI | Anthropic Claude API |

### v2.0 — Super Admin Portal
| Компонент | Технология |
|-----------|-----------|
| Frontend + API | Next.js 16 (App Router) |
| База данных | PostgreSQL 16 + Prisma 6 |
| UI | Tailwind CSS + Shadcn/ui |
| Auth | Cookie-based JWT |
| Язык | TypeScript |

---

## Функциональность

### v1.0 Network Monitor
- ✅ Real-time DNS мониторинг (NetFlow v9 + Syslog)
- ✅ 161+ устройств с онлайн статусом
- ✅ Категории активности: Работа / Соцсети / Игры / Развлечения / Система
- ✅ Фильтр времени: 1ч / 24ч / Всё
- ✅ Трафик: 1ч / 1д / 7д / 30д
- ✅ AI анализ доменов (Claude API)
- ✅ Блокировки доменов через MikroTik API
- ✅ Управление отделами (address-list)
- ✅ Авторизация с ролями (admin / manager / viewer)
- ✅ Система лицензий (блокировка при неоплате)

### v2.0 Super Admin Portal
- ✅ Dashboard со статистикой платформы
- ✅ Управление организациями (CRUD + тогл блокировки)
- ✅ Управление устройствами MikroTik (CRUD + Ping)
- ✅ Управление пользователями с ролями
- ✅ База доменов (535+ категорий)
- ✅ Синхронизация данных v1.0 → v2.0
- ✅ Heartbeat мониторинг серверов
- ✅ License Key система
- ✅ Смена пароля через UI и терминал

---

## Структура репозитория

```
mikrotik-monitor/
├── api/                    # v1.0 FastAPI бэкенд
│   ├── main.py             # Основной сервер (~1100 строк)
│   ├── dashboard.html      # Single-page фронтенд
│   └── requirements.txt
├── collector/              # NetFlow + Syslog коллектор
├── migrations/             # Схемы БД
│   ├── clickhouse/
│   └── postgres/
├── admin/                  # v2.0 Super Admin Portal
│   ├── src/
│   │   ├── app/            # Next.js App Router
│   │   ├── components/     # React компоненты
│   │   ├── lib/            # Prisma, Auth
│   │   └── types/
│   └── prisma/
│       └── schema.prisma   # Схема БД v2.0
├── deploy-template/        # Шаблон для деплоя клиентов
│   ├── install.sh          # Скрипт установки
│   └── README.md
├── docker-compose.yml      # v1.0 Docker конфигурация
├── .env.example
└── CONTEXT.md              # Контекст для AI разработки
```

---

## Переменные окружения v1.0

| Переменная | Описание | Пример |
|------------|----------|--------|
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `secret123` |
| `CLICKHOUSE_PASSWORD` | Пароль ClickHouse | `secret123` |
| `ADMIN_PASSWORD` | Пароль для входа | `Admin2024!` |
| `ANTHROPIC_API_KEY` | Claude API ключ | `sk-ant-...` |
| `MIKROTIK_HOST` | IP MikroTik | `192.168.1.1` |
| `MIKROTIK_USER` | Пользователь API | `nebulanet` |
| `MIKROTIK_PASS` | Пароль API | `password` |
| `LICENSE_KEY` | Ключ лицензии от v2.0 | `org_abc123` |
| `ADMIN_URL` | URL Super Admin v2.0 | `http://admin.nebulanet.uz:3001` |

---

## Команды управления v1.0

```bash
cd /opt/nebulanet

# Статус
docker compose ps

# Логи API
docker compose logs api -f

# Логи коллектора
docker compose logs collector -f

# Перезапуск после обновления
git pull && docker compose up -d --build

# Бэкап БД
docker exec nebulanet-postgres pg_dump -U nebulanet nebulanet > backup_$(date +%Y%m%d).sql
```

## Команды управления v2.0

```bash
cd /opt/nebulanet/admin

# Разработка
PORT=3001 npm run dev

# Продакшен
npm run build && PORT=3001 npm start

# Миграции БД
npx prisma migrate dev --name НАЗВАНИЕ

# Просмотр БД
npx prisma studio

# Смена пароля SuperAdmin через терминал
python3 -c "import bcrypt; print(bcrypt.hashpw(b'НовыйПароль', bcrypt.gensalt(12)).decode())"
# Скопируй хеш и выполни:
docker exec nebulanet-postgres psql -U nebulanet -d nebulanet_v2 \
  -c "UPDATE super_admins SET password='ХЕШ' WHERE email='admin@nebulanet.local';"
```

---

## Открытые порты

| Порт | Протокол | Сервис |
|------|----------|--------|
| 8000 | TCP | v1.0 Web интерфейс |
| 3001 | TCP | v2.0 Super Admin |
| 2055 | UDP | NetFlow v9 |
| 514  | UDP | Syslog |

---

## Лицензия

MIT © 2026 NebulaNet
