// src/context/AuthContext.tsx
'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { authService, LoginCredentials, RegisterCredentials } from '@/services/auth';

interface User {
  id: string;
  username: string;
}

interface AuthContextValue {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const initializeAuth = () => {
      const savedToken = authService.getToken();
      if (savedToken) {
        setToken(savedToken);
        // Could add token validation here if needed
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    try {
      setError(null);
      setIsLoading(true);
      const response = await authService.login(credentials);
      authService.saveToken(response.access_token);
      setToken(response.access_token);
      setUser({
        id: response.user_id,
        username: response.username
      });
      router.push('/threads');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to login');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (credentials: RegisterCredentials) => {
  try {
    console.log('AuthContext: Starting registration process');
    setError(null);
    setIsLoading(true);
    console.log('Calling authService.register');
    const response = await authService.register(credentials);
    console.log('Registration response received:', response);
    setToken(response.access_token);
    setUser({
      id: response.user_id,
      username: response.username
    });
    router.push('/threads');
  } catch (err) {
    console.error('AuthContext registration error:', err);
    setError(err instanceof Error ? err.message : 'Failed to register');
    throw err;
  } finally {
    setIsLoading(false);
  }
};

  const logout = () => {
    authService.removeToken();
    setToken(null);
    setUser(null);
    router.push('/login');
  };

  return (
    <AuthContext.Provider 
      value={{ 
        token, 
        user, 
        isLoading, 
        error, 
        login, 
        register, 
        logout 
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
