# NebulaNet — Контекст проекта для Claude

## Что это
SaaS платформа мониторинга сети на базе MikroTik.
Архитектура: v2.0 (Super Admin) управляет множеством v1.0 (мониторинг локаций).

## Серверы
- **Текущий сервер**: 192.168.1.53 (user: tehron, root)
- **v1.0 path**: /home/tehron/nebulanet (порт 8000)
- **v2.0 path**: /home/tehron/nebulanet/admin (порт 3001)
- **GitHub**: github.com/boykulov/mikrotik-monitor

## Архитектура (Путь A)
```
VPS-2 (центральный — будущее)    VPS-1 / локально (клиент)
┌─────────────────────┐          ┌──────────────────────┐
│ v2.0 Super Admin    │◄────────►│ v1.0 Мониторинг      │
│ :3001               │  license │ :8000                │
│ Только SuperAdmin   │  check   │ Клиент видит своё    │
└─────────────────────┘          └──────────────────────┘
```

## MikroTik (Uzbfreight)
- IP: 192.168.1.200 (CCR2004-16G-2S+, RouterOS 7.16.2)
- API user: nebulanet / Nebula2026! (group: write)
- NetFlow → :2055/udp, Syslog → :514/udp
- Docker network gateway: 172.18.0.1

## Стек v1.0
- FastAPI + Python (api/main.py) ~1100 строк
- Dashboard: Single HTML (api/dashboard.html)
- PostgreSQL (nebulanet) + ClickHouse + Redis
- Docker Compose (порт 8000)
- Авторизация: cookie nn_session, таблица org_admins
- Лицензия: LICENSE_KEY + ADMIN_URL в .env

## Стек v2.0 (Super Admin Portal)
- Next.js 16 + TypeScript + Tailwind + Shadcn/ui
- Prisma 6 + PostgreSQL (nebulanet_v2)
- Cookie auth (nebulanet_session)
- Порт 3001

## БД v1.0 PostgreSQL (nebulanet)
- devices — 161 устройство
- users — сетевые пользователи (не логины!)
- org_admins — логины для входа (admin / UzbAdmin2024!)
- domain_categories — 535+ категорий
- blocked_domains, departments, locations, routers

## БД v2.0 PostgreSQL (nebulanet_v2)
- super_admins — SuperAdmin (admin@nebulanet.local / NebulaAdmin2024!)
- organizations — Uzbfreight (PRO, AI включён, licenseKey сохранён)
- users + user_organizations — пользователи с ролями
- mikrotik_devices, industries (8 шт)
- categories, domains, org_relations
- audit_logs, platform_settings

## License Keys
- Uzbfreight: uzbfreight_JVVyyzkkBsoSQXkdxrhb4svpl6F8zoNt
- ADMIN_URL в v1.0 .env: http://172.18.0.1:3001

## ClickHouse (v1.0)
- nebulanet.flows — NetFlow TTL 90д
- nebulanet.dns_log — DNS запросы TTL 90д

## Что сделано в v1.0
1. Real-time мониторинг DNS + NetFlow (161 устройство)
2. AI анализ доменов (Claude API)
3. Блокировки по отделу/подсети через MikroTik
4. Авторизация: логин/пароль + кнопка выхода
5. Система лицензий:
   - Мгновенная блокировка при F5 (сброс кэша)
   - Блокировка при переключении вкладок (кэш 2 мин)
   - Страница блокировки с контактами (+998993570040, nebulanet.uz)
   - LICENSE_KEY + ADMIN_URL в .env + docker-compose.yml

## Что сделано в v2.0
1. Prisma schema (12 таблиц + licenseKey) + миграции
2. Login страница SuperAdmin
3. Dashboard (статистика из БД)
4. Sidebar навигация
5. Страница организаций (таблица)
6. Карточка организации (редактирование)
7. Форма создания организации
8. API: organizations CRUD
9. Endpoint GET /api/license/check?key=XXX
10. Middleware исправлен (API роуты публичные)

## Следующий этап
1. Кнопка быстрой блокировки в карточке орг-и (один клик)
2. Синхронизация доменов из v1.0 → v2.0
3. Docker шаблон для деплоя нового клиента на VPS
4. Страница устройств MikroTik в v2.0
5. Страница пользователей в v2.0
6. Telegram алерты

## Подсети Uzbfreight
- 192.168.1.0/24 — User (основная)
- 192.168.10.0/23 — wifi_admin
- 192.168.12.0/23 — staffwifi
- 192.168.20.0/23 — hotspot

## Команды v1.0
cd /home/tehron/nebulanet
docker compose up -d --build api
docker compose logs api -f

## Команды v2.0
cd /home/tehron/nebulanet/admin
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
PORT=3001 npm run dev
npx prisma migrate dev --name NAME
npx prisma studio

## Git
cd /home/tehron/nebulanet
git add -A && git commit -m "msg" && git push origin main
