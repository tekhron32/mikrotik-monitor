import { NextResponse } from 'next/server'
import { Client } from 'pg'

export async function GET() {
  const client = new Client({
    host: '127.0.0.1',
    port: 5432,
    database: 'nebulanet',
    user: 'nebulanet',
    password: 'nebulanet_secret',
  })
  try {
    await client.connect()
    const { rows } = await client.query(
      'SELECT id, username, full_name, role, is_active, created_at, last_login FROM org_admins ORDER BY created_at DESC'
    )
    await client.end()
    return NextResponse.json(rows)
  } catch (err) {
    try { await client.end() } catch {}
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}

export async function POST(req: Request) {
  const { username, password, full_name, role } = await req.json()
  const client = new Client({
    host: '127.0.0.1', port: 5432,
    database: 'nebulanet', user: 'nebulanet', password: 'nebulanet_secret',
  })
  try {
    await client.connect()
    const bcrypt = await import('bcryptjs')
    const hash = await bcrypt.hash(password || 'NebulaNet2024!', 12)
    const { rows } = await client.query(
      'INSERT INTO org_admins (username, password, full_name, role) VALUES ($1, $2, $3, $4) RETURNING id, username, full_name, role',
      [username, hash, full_name, role || 'viewer']
    )
    await client.end()
    return NextResponse.json(rows[0], { status: 201 })
  } catch (err) {
    try { await client.end() } catch {}
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
