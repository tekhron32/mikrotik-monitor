'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface Props {
  orgId: string
  orgName: string
  isActive: boolean
}

export function OrgToggleButton({ orgId, isActive }: Props) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(isActive)

  async function toggle() {
    if (loading) return
    setLoading(true)
    // Оптимистичное обновление — меняем UI сразу
    setActive(prev => !prev)
    try {
      const res = await fetch(`/api/organizations/${orgId}/toggle`, {
        method: 'PATCH',
      })
      if (res.ok) {
        const data = await res.json()
        setActive(data.isActive)
        router.refresh()
      } else {
        // Откатываем если ошибка
        setActive(prev => !prev)
      }
    } catch {
      setActive(prev => !prev)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={toggle}
      disabled={loading}
      title={active ? 'Выключить' : 'Включить'}
      className={`relative inline-flex w-10 h-5 rounded-full transition-all duration-200 focus:outline-none disabled:opacity-50 cursor-pointer ${
        active
          ? 'bg-green-500 hover:bg-green-400'
          : 'bg-[#1e2535] hover:bg-[#2a3548]'
      }`}
    >
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
        active ? 'translate-x-5' : 'translate-x-0.5'
      }`} />
    </button>
  )
}
