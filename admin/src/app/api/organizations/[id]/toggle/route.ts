import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function PATCH(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const org = await prisma.organization.findUnique({
    where: { id },
    select: { isActive: true, name: true },
  })
  if (!org) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  const updated = await prisma.organization.update({
    where: { id },
    data: { isActive: !org.isActive },
    select: { id: true, isActive: true, name: true },
  })
  return NextResponse.json(updated)
}
