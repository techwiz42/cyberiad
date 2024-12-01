import './globals.css'
import { ClientLayout } from '@/components/layout/ClientLayout'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Cyberiad',
  description: 'Multi-user, multi-agent discussion platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <ClientLayout>
          {children}
        </ClientLayout>
      </body>
    </html>
  )
}
