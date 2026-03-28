import { prisma } from '@/lib/prisma'
import Link from 'next/link'
import { OrgToggleButton } from '@/components/organizations/org-toggle-button'

async function getOrganizations() {
  return prisma.organization.findMany({
    include: {
      industry: true,
      _count: { select: { devices: true, users: true, domains: true } },
    },
    orderBy: { createdAt: 'desc' },
  })
}

const planColors: Record<string, string> = {
  BASIC:      'bg-slate-500/10 text-slate-400 border-slate-500/20',
  PRO:        'bg-blue-500/10 text-blue-400 border-blue-500/20',
  ENTERPRISE: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
}

export default async function OrganizationsPage() {
  const orgs = await getOrganizations()

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-white">Организации</h1>
          <p className="text-sm text-slate-500 mt-1">{orgs.length} организаций в системе</p>
        </div>
        <Link
          href="/organizations/new"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-all"
        >
          + Добавить
        </Link>
      </div>

      <div className="border border-[#1e2535] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1e2535] bg-[#0d1018]">
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Организация</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Отрасль</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Тариф</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Устр.</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Польз.</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">AI</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Статус</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Вкл/Выкл</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2535]">
            {orgs.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-sm text-slate-600">
                  Организаций пока нет
                </td>
              </tr>
            ) : orgs.map(org => (
              <tr key={org.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[#1a1f2e] border border-[#1e2535] flex items-center justify-center flex-shrink-0">
                      <span className="text-xs text-slate-400 font-medium">
                        {org.name.slice(0, 2).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <div className="text-sm text-white font-medium">{org.name}</div>
                      <div className="text-xs text-slate-500">{org.slug}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-slate-400">
                  {org.industry ? (
                    <span>{org.industry.icon} {org.industry.name}</span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded border text-xs font-medium ${planColors[org.plan]}`}>
                    {org.plan}
                  </span>
                </td>
                <td className="px-4 py-3 text-center text-sm text-slate-300">{org._count.devices}</td>
                <td className="px-4 py-3 text-center text-sm text-slate-300">
                  {org._count.users} / {org.userLimit}
                </td>
                <td className="px-4 py-3 text-center">
                  {org.aiEnabled
                    ? <span className="inline-flex w-2 h-2 rounded-full bg-green-400"></span>
                    : <span className="inline-flex w-2 h-2 rounded-full bg-slate-600"></span>
                  }
                </td>
                <td className="px-4 py-3 text-center">
                  {org.isActive
                    ? <span className="inline-flex px-2 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20 text-xs">Активна</span>
                    : <span className="inline-flex px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 text-xs">Выключена</span>
                  }
                </td>
                <td className="px-4 py-3 text-center">
                  <OrgToggleButton
                    orgId={org.id}
                    orgName={org.name}
                    isActive={org.isActive}
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/organizations/${org.id}`}
                    className="text-xs text-slate-500 hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-blue-500/10"
                  >
                    Открыть →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
