import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Autonomous AI System',
  description:
    'Production-grade multi-agent AI system with RAG — powered by LLM orchestration and semantic document search.',
  keywords: ['AI', 'agents', 'RAG', 'LLM', 'autonomous'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-[#0b0d14] text-white antialiased">
        {children}
      </body>
    </html>
  );
}
