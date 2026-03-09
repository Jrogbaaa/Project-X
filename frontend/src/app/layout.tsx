import type { Metadata } from 'next';
import { Cormorant_Garamond, Outfit, DM_Mono } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

// Display / editorial serif — the visual signature of Meridian
const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  style: ['normal', 'italic'],
  variable: '--font-cormorant',
  display: 'swap',
});

// Clean geometric sans — warm, legible, modern
const outfit = Outfit({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-outfit',
  display: 'swap',
});

// Monospace for metrics, data, numbers
const dmMono = DM_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-dm-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Look After You — Influencer Discovery',
  description: 'Plataforma de descubrimiento de influencers con IA. Encuentra el influencer ideal para tu marca mediante búsqueda en lenguaje natural.',
  keywords: ['influencer', 'marketing', 'descubrimiento', 'brand partnerships', 'redes sociales'],
  openGraph: {
    title: 'Look After You — Influencer Discovery',
    description: 'Encuentra tu influencer ideal con búsqueda por IA',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="es"
      className={`${cormorant.variable} ${outfit.variable} ${dmMono.variable}`}
    >
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
