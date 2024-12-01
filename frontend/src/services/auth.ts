
// src/services/auth.ts
import { User } from '@/types'
import { api, getAuthHeaders } from './api'; // Import getAuthHeaders

interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

interface LoginData {
  username: string
  password: string
}

interface RegisterData extends LoginData {
  email: string
}

export const authService = {
  async login(data: LoginData): Promise<LoginResponse> {
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);

    const response = await api.post<LoginResponse>(
      '/api/token',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );
    return response.data!;
  },

  async register(data: RegisterData): Promise<User> {
    const response = await api.post<User>(
      '/api/register',
      { ...data } // Convert RegisterData to a plain object
    );
    return response.data!;
  },

  async getCurrentUser(token: string): Promise<User> {
    const response = await api.get<User>(
      '/api/users/me',
      { headers: getAuthHeaders(token) }
    );
    return response.data!;
  },

  async logout(token: string): Promise<void> {
    await api.post(
      '/api/logout',
      undefined,
      { headers: getAuthHeaders(token) }
    );
  }
}

