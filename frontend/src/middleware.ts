// src/middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Add routes that should be protected
const protectedRoutes = ['/threads']
// Add routes that logged-in users shouldn't access
const authRoutes = ['/login', '/register']

export function middleware(request: NextRequest) {
  const token = request.cookies.get('token')?.value
  const { pathname } = request.nextUrl
  
  // Redirect logged-in users trying to access auth routes
  if (token && authRoutes.includes(pathname)) {
    return NextResponse.redirect(new URL('/threads', request.url))
  }
  
  // Redirect non-logged-in users trying to access protected routes
  if (!token && protectedRoutes.some(route => pathname.startsWith(route))) {
    const redirectUrl = new URL('/login', request.url)
    redirectUrl.searchParams.set('from', pathname)
    return NextResponse.redirect(redirectUrl)
  }

  // Handle root route
  if (pathname === '/') {
    if (token) {
      return NextResponse.redirect(new URL('/threads', request.url))
    }
    return NextResponse.redirect(new URL('/login', request.url))
  }
  
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)']
}
