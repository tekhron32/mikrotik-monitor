import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const device = await prisma.mikrotikDevice.findUnique({
    where: { id },
    select: { id: true, ip: true, name: true },
  })
  if (!device) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const start = Date.now()
  try {
    const res = await fetch(`http://${device.ip}:80`, {
      signal: AbortSignal.timeout(3000),
    }).catch(() => null)
    const ms = Date.now() - start
    const online = ms < 3000

    await prisma.mikrotikDevice.update({
      where: { id },
      data: {
        status:    online ? 'ONLINE' : 'OFFLINE',
        lastSeen:  online ? new Date() : undefined,
        lastPingMs: ms,
      },
    })
    return NextResponse.json({ online, ms, ip: device.ip })
  } catch {
    await prisma.mikrotikDevice.update({
      where: { id },
      data: { status: 'OFFLINE' },
    })
    return NextResponse.json({ online: false, ms: null, ip: device.ip })
  }
}
