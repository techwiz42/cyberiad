'use client';

import { ReactNode } from 'react';
import { AuthProvider } from '@/context/AuthContext';

export function ClientLayout({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

