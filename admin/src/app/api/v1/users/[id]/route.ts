import { NextRequest, NextResponse } from 'next/server'
import { Client } from 'pg'

async function getClient() {
  const client = new Client({
    host: '127.0.0.1', port: 5432,
    database: 'nebulanet', user: 'nebulanet', password: 'nebulanet_secret',
  })
  await client.connect()
  return client
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const { full_name, role, password } = await req.json()
  const client = await getClient()
  try {
    if (password && password.trim()) {
      const bcrypt = await import('bcryptjs')
      const hash = await bcrypt.hash(password, 12)
      await client.query(
        'UPDATE org_admins SET full_name=$1, role=$2, password=$3 WHERE id=$4',
        [full_name, role, hash, id]
      )
    } else {
      await client.query(
        'UPDATE org_admins SET full_name=$1, role=$2 WHERE id=$3',
        [full_name, role, id]
      )
    }
    await client.end()
    return NextResponse.json({ success: true })
  } catch (err) {
    await client.end()
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const client = await getClient()
  try {
    await client.query('DELETE FROM org_admins WHERE id=$1', [id])
    await client.end()
    return NextResponse.json({ success: true })
  } catch (err) {
    await client.end()
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}

export async function PATCH(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const client = await getClient()
  try {
    const { rows } = await client.query('SELECT is_active FROM org_admins WHERE id=$1', [id])
    if (!rows[0]) { await client.end(); return NextResponse.json({ error: 'Not found' }, { status: 404 }) }
    const newStatus = !rows[0].is_active
    await client.query('UPDATE org_admins SET is_active=$1 WHERE id=$2', [newStatus, id])
    await client.end()
    return NextResponse.json({ success: true, is_active: newStatus })
  } catch (err) {
    await client.end()
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
