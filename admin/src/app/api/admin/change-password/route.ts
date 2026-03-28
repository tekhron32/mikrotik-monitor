import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import bcrypt from 'bcryptjs'
import { cookies } from 'next/headers'

export async function POST(req: NextRequest) {
  const cookieStore = await cookies()
  const session = cookieStore.get('nebulanet_session')
  if (!session) return NextResponse.json({ error: 'Не авторизован' }, { status: 401 })

  const { current, newPassword } = await req.json()

  const admin = await prisma.superAdmin.findUnique({
    where: { id: session.value },
  })
  if (!admin) return NextResponse.json({ error: 'Аккаунт не найден' }, { status: 404 })

  const valid = await bcrypt.compare(current, admin.password)
  if (!valid) return NextResponse.json({ error: 'Неверный текущий пароль' }, { status: 400 })

  const hash = await bcrypt.hash(newPassword, 12)
  await prisma.superAdmin.update({
    where: { id: admin.id },
    data: { password: hash },
  })

  return NextResponse.json({ success: true })
}
