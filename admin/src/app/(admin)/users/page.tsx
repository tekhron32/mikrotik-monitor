import { prisma } from '@/lib/prisma'
import { UsersTable } from '@/components/users/users-table'
import { V1UsersTable } from '@/components/users/v1-users-table'
import { Client } from 'pg'

async function getV1Users() {
  const client = new Client({
    host: '127.0.0.1', port: 5432,
    database: 'nebulanet', user: 'nebulanet', password: 'nebulanet_secret',
  })
  try {
    await client.connect()
    const { rows } = await client.query(
      'SELECT id, username, full_name, role, is_active, created_at, last_login FROM org_admins ORDER BY created_at DESC'
    )
    await client.end()
    return rows
  } catch {
    try { await client.end() } catch {}
    return []
  }
}

async function getData() {
  const [users, organizations, v1Users] = await Promise.all([
    prisma.user.findMany({
      include: { organizations: { include: { org: { select: { id: true, name: true } } } } },
      orderBy: { createdAt: 'desc' },
    }),
    prisma.organization.findMany({ select: { id: true, name: true }, orderBy: { name: 'asc' } }),
    getV1Users(),
  ])
  return { users, organizations, v1Users }
}

export default async function UsersPage() {
  const { users, organizations, v1Users } = await getData()
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-white">Пользователи</h1>
        <p className="text-sm text-slate-500 mt-1">Управление доступом к мониторингу</p>
      </div>

      {/* Пользователи мониторинга v1.0 */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-medium text-slate-300">Мониторинг v1.0</span>
          <span className="text-xs px-2 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">:8000</span>
          <span className="text-xs text-slate-600">— логины для входа в мониторинг</span>
        </div>
        <V1UsersTable users={v1Users} />
      </div>

      {/* Разделитель */}
      <div className="border-t border-[#1e2535] my-6"></div>

      {/* Пользователи org-портала v2.0 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-medium text-slate-300">Org Portal v2.0</span>
          <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">будущее</span>
          <span className="text-xs text-slate-600">— пользователи с ролями</span>
        </div>
        <UsersTable users={users} organizations={organizations} />
      </div>
    </div>
  )
}
