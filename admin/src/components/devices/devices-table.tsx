'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import type { MikrotikDevice, Organization } from '@prisma/client'

type DeviceWithOrg = MikrotikDevice & {
  org: { id: string; name: string; slug: string }
}

const statusColors = {
  ONLINE:  { dot: 'bg-green-400', text: 'text-green-400', label: 'Online' },
  OFFLINE: { dot: 'bg-red-400',   text: 'text-red-400',   label: 'Offline' },
  ERROR:   { dot: 'bg-amber-400', text: 'text-amber-400', label: 'Error' },
  UNKNOWN: { dot: 'bg-slate-500', text: 'text-slate-500', label: '—' },
}

interface Props {
  devices: DeviceWithOrg[]
  organizations: Pick<Organization, 'id' | 'name'>[]
}

export function DevicesTable({ devices: initial, organizations }: Props) {
  const router = useRouter()
  const [devices, setDevices] = useState(initial)
  const [pinging, setPinging] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editDevice, setEditDevice] = useState<DeviceWithOrg | null>(null)
  const [form, setForm] = useState({
    orgId: organizations[0]?.id || '',
    name: '', ip: '', apiPort: '8728',
    login: 'nebulanet', password: '', model: '',
  })
  const [saving, setSaving] = useState(false)

  async function ping(deviceId: string) {
    setPinging(deviceId)
    try {
      const res = await fetch(`/api/devices/${deviceId}/ping`)
      const data = await res.json()
      setDevices(prev => prev.map(d =>
        d.id === deviceId
          ? { ...d, status: data.online ? 'ONLINE' : 'OFFLINE', lastPingMs: data.ms }
          : d
      ))
    } finally {
      setPinging(null)
    }
  }

  async function pingAll() {
    for (const d of devices) await ping(d.id)
  }

  function openAdd() {
    setEditDevice(null)
    setForm({ orgId: organizations[0]?.id || '', name: '', ip: '', apiPort: '8728', login: 'nebulanet', password: '', model: '' })
    setShowForm(true)
  }

  function openEdit(d: DeviceWithOrg) {
    setEditDevice(d)
    setForm({ orgId: d.orgId, name: d.name, ip: d.ip, apiPort: String(d.apiPort), login: d.login, password: d.password, model: d.model || '' })
    setShowForm(true)
  }

  async function saveDevice() {
    setSaving(true)
    try {
      const url = editDevice ? `/api/devices/${editDevice.id}` : '/api/devices'
      const method = editDevice ? 'PUT' : 'POST'
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, apiPort: Number(form.apiPort) }),
      })
      if (res.ok) {
        setShowForm(false)
        router.refresh()
      }
    } finally {
      setSaving(false)
    }
  }

  async function deleteDevice(id: string) {
    if (!confirm('Удалить устройство?')) return
    await fetch(`/api/devices/${id}`, { method: 'DELETE' })
    setDevices(prev => prev.filter(d => d.id !== id))
    router.refresh()
  }

  return (
    <div>
      {/* Actions */}
      <div className="flex gap-3 mb-4">
        <button onClick={openAdd}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-all">
          + Добавить устройство
        </button>
        <button onClick={pingAll} disabled={pinging !== null}
          className="px-4 py-2 bg-[#1a1f2e] hover:bg-[#1e2535] border border-[#1e2535] text-slate-300 text-sm rounded-lg transition-all disabled:opacity-50">
          ⟳ Ping все
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="border border-[#1e2535] rounded-xl p-4 mb-4 bg-[#0d1018]">
          <h3 className="text-sm font-medium text-slate-200 mb-4">
            {editDevice ? `Редактировать: ${editDevice.name}` : 'Новое устройство'}
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Организация</label>
              <select value={form.orgId} onChange={e => setForm(p => ({ ...p, orgId: e.target.value }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50">
                {organizations.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Название</label>
              <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Главный офис CCR2004"
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">IP адрес</label>
              <input value={form.ip} onChange={e => setForm(p => ({ ...p, ip: e.target.value }))}
                placeholder="192.168.1.200"
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm font-mono text-slate-200 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">API Port</label>
              <input value={form.apiPort} onChange={e => setForm(p => ({ ...p, apiPort: e.target.value }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm font-mono text-slate-200 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Логин</label>
              <input value={form.login} onChange={e => setForm(p => ({ ...p, login: e.target.value }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Пароль</label>
              <input type="password" value={form.password} onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1 uppercase tracking-wider">Модель</label>
              <input value={form.model} onChange={e => setForm(p => ({ ...p, model: e.target.value }))}
                placeholder="CCR2004-16G-2S+"
                className="w-full px-3 py-2 bg-[#13171f] border border-[#1e2535] rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500/50" />
            </div>
          </div>
          <div className="flex gap-3 mt-4 justify-end">
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm text-slate-500 hover:text-slate-300 transition-colors">
              Отмена
            </button>
            <button onClick={saveDevice} disabled={saving}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-all">
              {saving ? 'Сохраняем...' : editDevice ? 'Сохранить' : 'Добавить'}
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="border border-[#1e2535] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1e2535] bg-[#0d1018]">
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Устройство</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Организация</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">IP / Port</th>
              <th className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">Модель</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Статус</th>
              <th className="px-4 py-3 text-center text-xs text-slate-500 uppercase tracking-wider">Ping</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2535]">
            {devices.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-600">
                  Устройств нет — добавьте первое
                </td>
              </tr>
            ) : devices.map(d => {
              const st = statusColors[d.status]
              return (
                <tr key={d.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-3">
                    <div className="text-sm text-white font-medium">{d.name}</div>
                    <div className="text-xs text-slate-500">{d.login}@{d.ip}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-slate-300">{d.org.name}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm font-mono text-slate-300">{d.ip}</span>
                    <span className="text-xs text-slate-600 ml-1">:{d.apiPort}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-500">{d.model || '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`}></span>
                      <span className={`text-xs ${st.text}`}>{st.label}</span>
                      {d.lastPingMs && d.status === 'ONLINE' && (
                        <span className="text-xs text-slate-600">{d.lastPingMs}ms</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => ping(d.id)} disabled={pinging === d.id}
                      className="text-xs px-2 py-1 rounded bg-[#1a1f2e] hover:bg-[#1e2535] text-slate-400 hover:text-slate-200 border border-[#1e2535] transition-all disabled:opacity-50">
                      {pinging === d.id ? '...' : 'Ping'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(d)}
                        className="text-xs text-slate-500 hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-blue-500/10">
                        Изменить
                      </button>
                      <button onClick={() => deleteDevice(d.id)}
                        className="text-xs text-slate-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-500/10">
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
