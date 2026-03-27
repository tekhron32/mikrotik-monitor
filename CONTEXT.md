# NebulaNet — Контекст проекта для Claude

## Что это
SaaS платформа мониторинга сети на базе MikroTik.

## Версии
- **v1.0** — работает, папка `/home/tehron/nebulanet/` (api/, collector/)
- **v2.0** — в разработке, папка `/home/tehron/nebulanet/admin/` (Next.js 16 + Prisma 6)

## Сервер
- IP: 192.168.1.53 (user: tehron)
- Path v1.0: /home/tehron/nebulanet
- Path v2.0: /home/tehron/nebulanet/admin
- GitHub: github.com/boykulov/mikrotik-monitor

## MikroTik
- IP: 192.168.1.200 (CCR2004-16G-2S+, RouterOS 7.16.2)
- API user: nebulanet (group: write)
- NetFlow → :2055/udp, Syslog → :514/udp

## Стек v1.0
- FastAPI + Python (api/main.py)
- Dashboard: Single HTML (api/dashboard.html)
- PostgreSQL + ClickHouse + Redis
- Docker Compose

## Стек v2.0 (Super Admin Portal)
- Next.js 16 + TypeScript + Tailwind
- Shadcn/ui компоненты
- Prisma 6 + PostgreSQL (nebulanet_v2)
- Cookie-based auth (nebulanet_session)
- Порт: 3001

## БД v2.0 PostgreSQL (nebulanet_v2)
- super_admins — SuperAdmin аккаунты
- organizations — организации (Uzbfreight мигрирован)
- users + user_organizations — пользователи с ролями
- mikrotik_devices — устройства
- industries — отрасли (8 шт)
- categories + domains — категории и домены
- org_relations — связи между орг-ми
- audit_logs — журнал действий
- platform_settings — настройки платформы

## БД v1.0 PostgreSQL (nebulanet)
- devices, users, domain_categories (535+)
- blocked_domains, departments

## ClickHouse (v1.0)
- nebulanet.flows — NetFlow TTL 90д
- nebulanet.dns_log — DNS запросы TTL 90д

## Credentials v2.0
- SuperAdmin: admin@nebulanet.local / NebulaAdmin2024!
- DB: postgresql://nebulanet:nebulanet_secret@127.0.0.1:5432/nebulanet_v2

## Что сделано в v2.0
1. Prisma schema (12 таблиц) + миграции
2. NextAuth → cookie auth (nebulanet_session)
3. Страница логина
4. Dashboard (статистика из БД)
5. Sidebar навигация
6. Страница организаций (таблица)

## План v2.0 (следующий этап)
1. Карточка организации /organizations/[id]
2. Форма создания организации /organizations/new
3. Страница устройств /devices
4. Страница пользователей /users
5. API роуты CRUD
6. Telegram алерты
7. PDF отчёты
8. AI детекция аномалий

## Подсети
- 192.168.1.0/24 — User (основная)
- 192.168.10.0/23 — wifi_admin
- 192.168.12.0/23 — staffwifi
- 192.168.20.0/23 — hotspot

## Команды v2.0
cd /home/tehron/nebulanet/admin
PORT=3001 npm run dev
npx prisma studio   # GUI для БД
npx prisma migrate dev --name NAME

## Команды v1.0
cd /home/tehron/nebulanet
docker compose up -d
docker compose logs api -f
docker compose logs collector -f
