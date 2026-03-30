# NebulaNet — Контекст проекта для Claude

## Что это
SaaS платформа мониторинга сети на базе MikroTik.
v2.0 (Super Admin) управляет множеством v1.0 (мониторинг локаций).

## Серверы
- IP: 192.168.1.53 (user: tehron / root)
- v1.0 path: /home/tehron/nebulanet (порт 8000)
- v2.0 path: /home/tehron/nebulanet/admin (порт 3001)
- GitHub: github.com/boykulov/mikrotik-monitor
- Docker network gateway: 172.18.0.1

## Запуск v2.0
cd /home/tehron/nebulanet/admin
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
pkill -f "next dev" 2>/dev/null; sleep 2
PORT=3001 npm run dev > /tmp/v2.log 2>&1 &

## Запуск v1.0
cd /home/tehron/nebulanet && docker compose up -d

## MikroTik (Uzbfreight)
- IP: 192.168.1.200 (CCR2004-16G-2S+, RouterOS 7.16.2)
- API user: nebulanet / Nebula2026!
- NetFlow → :2055/udp, Syslog → :514/udp

## БД v1.0 (nebulanet)
- devices, users — сетевые устройства
- org_admins — логины (admin / UzbAdmin2024!)
- domain_categories — 535 категорий
- blocked_domains, departments

## БД v2.0 (nebulanet_v2)
- super_admins: admin@nebulanet.local / NebulaAdmin2024!
- organizations: Uzbfreight (PRO, isActive=true)
  licenseKey: uzbfreight_JVVyyzkkBsoSQXkdxrhb4svpl6F8zoNt
- mikrotik_devices: CCR2004 (192.168.1.200, ONLINE)
- categories: 6 глобальных
- domains: 535 (мигрированы из v1.0)

## Лицензии
- ADMIN_URL в v1.0: http://172.18.0.1:3001
- Блокировка при F5 + вкладки (кэш 2 мин)
- Страница блокировки: +998993570040 / nebulanet.uz

## Что сделано в v2.0
1. Login + Dashboard + Sidebar
2. Организации: список + карточка + создание + тогл блокировки
3. Устройства MikroTik: CRUD + Ping
4. Пользователи: v1.0 org_admins + v2.0 users с ролями
5. Настройки: смена пароля
6. License endpoint GET /api/license/check
7. Sync endpoint POST /api/sync (v1.0→v2.0)
8. Heartbeat: автоматически каждые 5 мин
9. 535 доменов + 6 категорий мигрированы
10. Docker шаблон deploy-template/install.sh

## Что сделано в v1.0
1. Auth: логин/пароль + выход
2. Система лицензий (мгновенная блокировка)
3. Heartbeat отправка в v2.0 (фоновый loop)

## Следующий этап
1. Страница доменов в v2.0 (поиск + фильтр)
2. Telegram алерты (offline → уведомление)
3. Продакшен деплой (PM2 или systemd для v2.0)
4. HTTPS / домен для v2.0

## Git
cd /home/tehron/nebulanet
git add -A && git commit -m "msg" && git push origin main
