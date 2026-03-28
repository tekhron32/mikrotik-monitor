import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function GET(req: NextRequest) {
  const orgId = req.nextUrl.searchParams.get('orgId')
  const devices = await prisma.mikrotikDevice.findMany({
    where: orgId ? { orgId } : undefined,
    include: { org: { select: { id: true, name: true, slug: true } } },
    orderBy: { createdAt: 'desc' },
  })
  return NextResponse.json(devices)
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const device = await prisma.mikrotikDevice.create({
    data: {
      orgId:     body.orgId,
      name:      body.name,
      ip:        body.ip,
      apiPort:   body.apiPort || 8728,
      login:     body.login,
      password:  body.password,
      model:     body.model || null,
      osVersion: body.osVersion || null,
    },
  })
  return NextResponse.json(device, { status: 201 })
}
