// src/app/layout.tsx

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  console.log("Root layout rendering!");
  return (
    <html lang="en">
      <body>
        <div>LAYOUT TEST</div>
        {children}
      </body>
    </html>
  )
}

