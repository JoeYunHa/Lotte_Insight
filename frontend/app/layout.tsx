import type { Metadata } from 'next'
import { Noto_Serif_KR, Noto_Sans_KR, Space_Mono } from 'next/font/google'
import './globals.css'

const notoSerifKr = Noto_Serif_KR({
  variable: '--font-serif-kr',
  weight: ['400', '700', '900'],
  preload: false,
})

const notoSansKr = Noto_Sans_KR({
  variable: '--font-sans-kr',
  weight: ['400', '500', '700'],
  preload: false,
})

const spaceMono = Space_Mono({
  variable: '--font-mono',
  weight: ['400', '700'],
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: '롯데 인사이트 | 2026 KBO',
  description: '2026 롯데 자이언츠 팬을 위한 시즌 이슈 분석 플랫폼',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ko"
      className={`${notoSerifKr.variable} ${notoSansKr.variable} ${spaceMono.variable}`}
    >
      <body className="min-h-dvh flex flex-col antialiased">
        {children}
      </body>
    </html>
  )
}
