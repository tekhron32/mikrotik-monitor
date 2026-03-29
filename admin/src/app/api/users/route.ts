import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import bcrypt from 'bcryptjs'

export async function GET(req: NextRequest) {
  const orgId = req.nextUrl.searchParams.get('orgId')
  const users = await prisma.user.findMany({
    where: orgId ? { organizations: { some: { orgId } } } : undefined,
    include: {
      organizations: {
        include: { org: { select: { id: true, name: true, slug: true } } },
      },
    },
    orderBy: { createdAt: 'desc' },
  })
  return NextResponse.json(users)
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const existing = await prisma.user.findUnique({ where: { email: body.email } })
  if (existing) return NextResponse.json({ error: 'Email уже занят' }, { status: 400 })

  const hash = await bcrypt.hash(body.password || 'NebulaNet2024!', 12)
  const user = await prisma.user.create({
    data: {
      email:      body.email,
      password:   hash,
      firstName:  body.firstName,
      lastName:   body.lastName,
      phone:      body.phone || null,
      position:   body.position || null,
      department: body.department || null,
    },
  })

  // Привязываем к организации если указана
  if (body.orgId && body.role) {
    await prisma.userOrganization.create({
      data: { userId: user.id, orgId: body.orgId, role: body.role },
    })
  }

  return NextResponse.json(user, { status: 201 })
}
