'use client'

import { useState } from 'react'

export function ChangePasswordForm() {
  const [form, setForm] = useState({ current: '', newPass: '', confirm: '' })
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (form.newPass !== form.confirm) {
      setMessage({ type: 'error', text: 'Новые пароли не совпадают' })
      return
    }
    if (form.newPass.length < 8) {
      setMessage({ type: 'error', text: 'Пароль должен быть не менее 8 символов' })
      return
    }
    setLoading(true)
    setMessage(null)
    try {
      const res = await fetch('/api/admin/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current: form.current, newPassword: form.newPass }),
      })
      const data = await res.json()
      if (res.ok) {
        setMessage({ type: 'success', text: 'Пароль успешно изменён' })
        setForm({ current: '', newPass: '', confirm: '' })
      } else {
        setMessage({ type: 'error', text: data.error || 'Ошибка' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Ошибка соединения' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-xs text-slate-500 mb-1.5 uppercase tracking-wider">Текущий пароль</label>
        <input type="password" value={form.current} onChange={e => setForm(p => ({ ...p, current: e.target.value }))} required
          className="w-full px-3 py-2 bg-[#0d1018] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1.5 uppercase tracking-wider">Новый пароль</label>
        <input type="password" value={form.newPass} onChange={e => setForm(p => ({ ...p, newPass: e.target.value }))} required
          className="w-full px-3 py-2 bg-[#0d1018] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1.5 uppercase tracking-wider">Подтверждение</label>
        <input type="password" value={form.confirm} onChange={e => setForm(p => ({ ...p, confirm: e.target.value }))} required
          className="w-full px-3 py-2 bg-[#0d1018] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
      </div>
      {message && (
        <div className={`px-3 py-2 rounded-lg text-xs ${
          message.type === 'success'
            ? 'bg-green-500/10 border border-green-500/20 text-green-400'
            : 'bg-red-500/10 border border-red-500/20 text-red-400'
        }`}>
          {message.text}
        </div>
      )}
      <div className="flex justify-end pt-1">
        <button type="submit" disabled={loading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-all">
          {loading ? 'Сохраняем...' : 'Сменить пароль'}
        </button>
      </div>
    </form>
  )
}
