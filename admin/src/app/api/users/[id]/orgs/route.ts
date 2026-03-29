import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const { orgId, role } = await req.json()
  const rel = await prisma.userOrganization.upsert({
    where:  { userId_orgId: { userId: id, orgId } },
    update: { role },
    create: { userId: id, orgId, role },
  })
  return NextResponse.json(rel)
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const { orgId } = await req.json()
  await prisma.userOrganization.delete({
    where: { userId_orgId: { userId: id, orgId } },
  })
  return NextResponse.json({ success: true })
}
