// src/middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('token')

  // If trying to access /login or /register while already logged in
  if (token && (request.nextUrl.pathname === '/login' || request.nextUrl.pathname === '/register')) {
    return NextResponse.redirect(new URL('/threads', request.url))
  }

  // If trying to access protected routes without being logged in
  if (!token && request.nextUrl.pathname.startsWith('/threads')) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/threads/:path*', '/login', '/register']
}
