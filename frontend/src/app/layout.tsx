// src/app/layout.tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { MainLayout } from '@/components/layout/MainLayout';
import { ClientLayout } from '@/components/layout/ClientLayout'; // Import the new client-side component

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Cyberiad',
  description: 'Multi-user, multi-agent discussion platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ClientLayout>
          <MainLayout>{children}</MainLayout>
        </ClientLayout>
      </body>
    </html>
  );
}

