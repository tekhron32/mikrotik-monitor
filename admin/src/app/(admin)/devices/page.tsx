import { prisma } from '@/lib/prisma'
import { DevicesTable } from '@/components/devices/devices-table'

async function getData() {
  const [devices, organizations] = await Promise.all([
    prisma.mikrotikDevice.findMany({
      include: { org: { select: { id: true, name: true, slug: true } } },
      orderBy: { createdAt: 'desc' },
    }),
    prisma.organization.findMany({
      select: { id: true, name: true },
      where: { isActive: true },
      orderBy: { name: 'asc' },
    }),
  ])
  return { devices, organizations }
}

export default async function DevicesPage() {
  const { devices, organizations } = await getData()

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-white">Устройства MikroTik</h1>
          <p className="text-sm text-slate-500 mt-1">{devices.length} устройств в системе</p>
        </div>
      </div>
      <DevicesTable devices={devices} organizations={organizations} />
    </div>
  )
}
