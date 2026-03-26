import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Sidebar from '../components/Sidebar'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Bruno — Multi-Agent Trading Intelligence',
  description: 'Krypto Trading Bot mit 5 KI-Agenten, Echtzeit-Charts und Risk Management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="de">
      <body className={`${inter.className} bg-[#06060f] text-slate-200 overflow-x-hidden`}>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 md:ml-64 min-h-screen">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
