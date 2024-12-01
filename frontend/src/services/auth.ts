// src/services/auth.ts
import { api } from './api'

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
    return response.data!
  },

  async register(credentials: RegisterCredentials): Promise<AuthResponse> {
    const requestData = {
      username: credentials.username,
      email: credentials.email,
      password: credentials.password
    }

    const response = await api.post<AuthResponse>(
      '/api/auth/register',
      requestData
    )
    return response.data!
  },

  saveToken(token: string): void {
    localStorage.setItem('token', token)
  },

  removeToken(): void {
    localStorage.removeItem('token')
  },

  getToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('token')
  }
}
