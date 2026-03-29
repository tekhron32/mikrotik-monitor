'use client'

import { useState } from 'react'

interface V1User {
  id: number
  username: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
  last_login: string | null
}

const roleColors: Record<string, string> = {
  admin:   'bg-purple-500/10 text-purple-400 border-purple-500/20',
  manager: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  viewer:  'bg-slate-500/10 text-slate-400 border-slate-500/20',
}

export function V1UsersTable({ users: initial }: { users: V1User[] }) {
  const [users, setUsers] = useState(initial)
  const [showForm, setShowForm] = useState(false)
  const [editUser, setEditUser] = useState<V1User | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    username: '', full_name: '', password: '', role: 'viewer'
  })

  function openAdd() {
    setEditUser(null)
    setForm({ username: '', full_name: '', password: 'NebulaNet2024!', role: 'viewer' })
    setShowForm(true)
  }

  function openEdit(u: V1User) {
    setEditUser(u)
    setForm({ username: u.username, full_name: u.full_name || '', password: '', role: u.role })
    setShowForm(true)
  }

  async function save() {
    setSaving(true)
    try {
      if (editUser) {
        await fetch(`/api/v1/users/${editUser.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ full_name: form.full_name, role: form.role, password: form.password }),
        })
        setUsers(prev => prev.map(u => u.id === editUser.id
          ? { ...u, full_name: form.full_name, role: form.role }
          : u
        ))
        setShowForm(false)
      } else {
        const res = await fetch('/api/v1/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
        if (res.ok) window.location.reload()
      }
    } finally {
      setSaving(false)
    }
  }

  async function toggleStatus(u: V1User) {
    const res = await fetch(`/api/v1/users/${u.id}`, { method: 'PATCH' })
    if (res.ok) {
      setUsers(prev => prev.map(x => x.id === u.id ? { ...x, is_active: !x.is_active } : x))
    }
  }

  async function deleteUser(u: V1User) {
    if (!confirm(`Удалить пользователя "${u.username}"?`)) return
    await fetch(`/api/v1/users/${u.id}`, { method: 'DELETE' })
    setUsers(prev => prev.filter(x => x.id !== u.id))
  }

  return (
    <div>
      <div className="flex gap-3 mb-3">
        <button onClick={openAdd}
          className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-medium rounded-lg transition-all">
          + Добавить логин
        </button>
      </div>

      {showForm && (
        <div className="border border-[#1e2535] rounded-xl p-4 mb-4 bg-[#0d1018]">
          <h3 className="text-sm font-medium text-slate-200 mb-3">
            {editUser ? `Редактировать: ${editUser.username}` : 'Новый логин для мониторинга'}
          </h3>
          <div className="grid grid-cols-4 gap-3">
            {!editUser && (
              <div>
                <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Логин</label>
                <input value={form.username}
                  onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                  placeholder="ivan_admin"
                  className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500/50" />
              </div>
            )}
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Полное имя</label>
              <input value={form.full_name}
                onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
                placeholder="Иван Иванов"
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">
                Пароль {editUser && <span className="text-slate-600">(оставь пустым чтобы не менять)</span>}
              </label>
              <input type="password" value={form.password}
                onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                placeholder={editUser ? '••••••••' : 'NebulaNet2024!'}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Роль</label>
              <select value={form.role} onChange={e => setForm(p => ({ ...p, role: e.target.value }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50">
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 mt-3 justify-end">
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm text-slate-500 hover:text-slate-300">Отмена</button>
            <button onClick={save} disabled={saving}
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-all">
              {saving ? 'Сохраняем...' : editUser ? 'Сохранить' : 'Создать'}
            </button>
          </div>
        </div>
      )}

      <div className="border border-[#1e2535] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1e2535] bg-[#0d1018]">
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Логин</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Имя</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Роль</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Статус</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Последний вход</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2535]">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-white/[0.02]">
                <td className="px-4 py-3 text-sm font-mono text-white">{u.username}</td>
                <td className="px-4 py-3 text-sm text-slate-300">{u.full_name || '—'}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`inline-flex px-2 py-0.5 rounded border text-xs ${roleColors[u.role] || roleColors.viewer}`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => toggleStatus(u)}
                    className={`inline-flex px-2 py-0.5 rounded border text-xs cursor-pointer transition-all ${
                      u.is_active
                        ? 'bg-green-500/10 text-green-400 border-green-500/20 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20'
                        : 'bg-red-500/10 text-red-400 border-red-500/20 hover:bg-green-500/10 hover:text-green-400 hover:border-green-500/20'
                    }`}>
                    {u.is_active ? 'Активен' : 'Заблокирован'}
                  </button>
                </td>
                <td className="px-4 py-3 text-center text-xs text-slate-500">
                  {u.last_login ? new Date(u.last_login).toLocaleDateString('ru') : '—'}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button onClick={() => openEdit(u)}
                      className="text-xs text-slate-500 hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-blue-500/10">
                      Изменить
                    </button>
                    <button onClick={() => deleteUser(u)}
                      className="text-xs text-slate-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-500/10">
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
