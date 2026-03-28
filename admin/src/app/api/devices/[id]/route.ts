import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const body = await req.json()
  const device = await prisma.mikrotikDevice.update({
    where: { id },
    data: {
      name:      body.name,
      ip:        body.ip,
      apiPort:   body.apiPort,
      login:     body.login,
      password:  body.password,
      model:     body.model || null,
      osVersion: body.osVersion || null,
    },
  })
  return NextResponse.json(device)
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  await prisma.mikrotikDevice.delete({ where: { id } })
  return NextResponse.json({ success: true })
}
