import { prisma } from '@/lib/prisma'
import { UsersTable } from '@/components/users/users-table'

async function getData() {
  const [users, organizations] = await Promise.all([
    prisma.user.findMany({
      include: {
        organizations: {
          include: { org: { select: { id: true, name: true } } },
        },
      },
      orderBy: { createdAt: 'desc' },
    }),
    prisma.organization.findMany({
      select: { id: true, name: true },
      orderBy: { name: 'asc' },
    }),
  ])
  return { users, organizations }
}

export default async function UsersPage() {
  const { users, organizations } = await getData()
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-white">Пользователи</h1>
          <p className="text-sm text-slate-500 mt-1">{users.length} пользователей в системе</p>
        </div>
      </div>
      <UsersTable users={users} organizations={organizations} />
    </div>
  )
}
