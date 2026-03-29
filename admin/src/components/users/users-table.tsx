'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import type { User, UserOrganization, Organization, OrgRole } from '@prisma/client'

type UserWithOrgs = User & {
  organizations: (UserOrganization & { org: { id: string; name: string } })[]
}

const ROLES: OrgRole[] = ['ADMIN', 'MANAGER', 'VIEWER']
const roleColors: Record<string, string> = {
  ADMIN:   'bg-purple-500/10 text-purple-400 border-purple-500/20',
  MANAGER: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  VIEWER:  'bg-slate-500/10 text-slate-400 border-slate-500/20',
}

interface Props {
  users: UserWithOrgs[]
  organizations: Pick<Organization, 'id' | 'name'>[]
}

export function UsersTable({ users: initial, organizations }: Props) {
  const router = useRouter()
  const [users, setUsers] = useState(initial)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '',
    password: 'NebulaNet2024!', phone: '',
    position: '', department: '',
    orgId: organizations[0]?.id || '',
    role: 'VIEWER' as OrgRole,
  })

  async function createUser() {
    setSaving(true)
    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (res.ok) {
        setShowForm(false)
        router.refresh()
      }
    } finally {
      setSaving(false)
    }
  }

  async function toggleStatus(id: string) {
    await fetch(`/api/users/${id}/status`, { method: 'PATCH' })
    setUsers(prev => prev.map(u => u.id === id ? { ...u, isActive: !u.isActive } : u))
    router.refresh()
  }

  async function deleteUser(id: string) {
    if (!confirm('Удалить пользователя?')) return
    await fetch(`/api/users/${id}`, { method: 'DELETE' })
    setUsers(prev => prev.filter(u => u.id !== id))
  }

  return (
    <div>
      <div className="flex gap-3 mb-4">
        <button onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-all">
          + Создать пользователя
        </button>
      </div>

      {/* Форма создания */}
      {showForm && (
        <div className="border border-[#1e2535] rounded-xl p-4 mb-4 bg-[#0d1018]">
          <h3 className="text-sm font-medium text-slate-200 mb-4">Новый пользователь</h3>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Имя', key: 'firstName', placeholder: 'Иван' },
              { label: 'Фамилия', key: 'lastName', placeholder: 'Иванов' },
              { label: 'Email', key: 'email', placeholder: 'user@company.com' },
              { label: 'Пароль', key: 'password', placeholder: 'NebulaNet2024!' },
              { label: 'Телефон', key: 'phone', placeholder: '+998 90 123 45 67' },
              { label: 'Должность', key: 'position', placeholder: 'Системный администратор' },
              { label: 'Отдел', key: 'department', placeholder: 'IT' },
            ].map(field => (
              <div key={field.key}>
                <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">{field.label}</label>
                <input
                  value={(form as Record<string, string>)[field.key]}
                  onChange={e => setForm(p => ({ ...p, [field.key]: e.target.value }))}
                  placeholder={field.placeholder}
                  className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Организация</label>
              <select value={form.orgId} onChange={e => setForm(p => ({ ...p, orgId: e.target.value }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50">
                {organizations.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Роль</label>
              <select value={form.role} onChange={e => setForm(p => ({ ...p, role: e.target.value as OrgRole }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50">
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3 mt-4 justify-end">
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm text-slate-500 hover:text-slate-300">Отмена</button>
            <button onClick={createUser} disabled={saving}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-all">
              {saving ? 'Создаём...' : 'Создать'}
            </button>
          </div>
        </div>
      )}

      {/* Таблица */}
      <div className="border border-[#1e2535] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1e2535] bg-[#0d1018]">
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Пользователь</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Организации</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Контакт</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Статус</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Последний вход</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2535]">
            {users.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-600">
                  Пользователей нет — создайте первого
                </td>
              </tr>
            ) : users.map(u => (
              <tr key={u.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs text-blue-400 font-medium">
                        {u.firstName[0]}{u.lastName[0]}
                      </span>
                    </div>
                    <div>
                      <div className="text-sm text-white">{u.firstName} {u.lastName}</div>
                      <div className="text-xs text-slate-500">{u.email}</div>
                      {u.position && <div className="text-xs text-slate-600">{u.position}</div>}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {u.organizations.map(rel => (
                      <span key={rel.id} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs ${roleColors[rel.role]}`}>
                        {rel.org.name} · {rel.role}
                      </span>
                    ))}
                    {u.organizations.length === 0 && <span className="text-xs text-slate-600">—</span>}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {u.phone || '—'}
                  {u.department && <div className="text-slate-600">{u.department}</div>}
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => toggleStatus(u.id)}
                    className={`inline-flex px-2 py-0.5 rounded border text-xs cursor-pointer transition-all ${
                      u.isActive
                        ? 'bg-green-500/10 text-green-400 border-green-500/20 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20'
                        : 'bg-red-500/10 text-red-400 border-red-500/20 hover:bg-green-500/10 hover:text-green-400 hover:border-green-500/20'
                    }`}>
                    {u.isActive ? 'Активен' : 'Заблокирован'}
                  </button>
                </td>
                <td className="px-4 py-3 text-center text-xs text-slate-500">
                  {u.lastLogin ? new Date(u.lastLogin).toLocaleDateString('ru') : '—'}
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => deleteUser(u.id)}
                    className="text-xs text-slate-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-500/10">
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
