// src/services/auth.ts
import { api } from './api'
import Cookies from 'js-cookie'

export interface LoginCredentials {
  username: string
  password: string
}

export interface RegisterCredentials {
  username: string
  email: string
  password: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user_id: string
  username: string
}

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const formData = new URLSearchParams()
    formData.append('username', credentials.username)
    formData.append('password', credentials.password)

    const response = await api.post<AuthResponse>(
      '/api/auth/token',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    )
    this.saveToken(response.data!.access_token)
    return response.data!
  },

  async register(credentials: RegisterCredentials): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>(
      '/api/auth/register',
      credentials
    )
    this.saveToken(response.data!.access_token)
    return response.data!
  },

  saveToken(token: string): void {
    Cookies.set('token', token, {
      expires: 7, // 7 days
      path: '/',
      sameSite: 'strict',
      secure: process.env.NODE_ENV === 'production'
    })
  },

  removeToken(): void {
    Cookies.remove('token', { path: '/' })
  },

  getToken(): string | null {
    return Cookies.get('token') || null
  }
}
