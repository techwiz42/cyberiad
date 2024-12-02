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
    console.log('Starting login with username:', credentials.username);
    
    const formData = new URLSearchParams()
    formData.append('username', credentials.username)
    formData.append('password', credentials.password)

    try {
      const response = await api.post<AuthResponse>(
        '/api/auth/token',
        formData,
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );
      console.log('Login successful:', response);
      this.saveToken(response.data!.access_token);
      return response.data!;
    } catch (error) {
      console.log('Login failed:', error);
      throw error;
    }
  },

  async register(credentials: RegisterCredentials): Promise<AuthResponse> {
    console.log('Starting registration with credentials:', {
      username: credentials.username,
      email: credentials.email
      // Don't log password
    });
    
    try {
      console.log('Making registration request to:', '/api/auth/register');
      
      const response = await api.post<AuthResponse>(
        '/api/auth/register',
        {
          username: credentials.username,
          email: credentials.email,
          password: credentials.password
        }
      );
      
      console.log('Registration successful:', response);
      this.saveToken(response.data!.access_token);
      return response.data!;
    } catch (error) {
      console.error('Registration failed:', error);
      throw new Error('Registration failed: ' + (error instanceof Error ? error.message : 'Unknown error'));
    }
  },

  saveToken(token: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token);
    }
  },

  removeToken(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
  },

  getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('token');
  }
}
