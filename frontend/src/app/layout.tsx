import type { Metadata } from 'next';
import { DM_Sans, JetBrains_Mono, Instrument_Serif } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

// Primary body font - Modern geometric sans with warmth
const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-dm-sans',
  display: 'swap',
});

// Monospace for metrics and data display
const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});

// Editorial serif for headlines - distinctive and sophisticated
const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: ['400'],
  style: ['normal', 'italic'],
  variable: '--font-instrument-serif',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Influencer Discovery | Find Your Perfect Match',
  description: 'Advanced AI-powered influencer discovery platform. Find ideal influencer matches for brand partnerships using natural language search.',
  keywords: ['influencer', 'marketing', 'discovery', 'brand partnerships', 'social media'],
  openGraph: {
    title: 'Influencer Discovery',
    description: 'Find your perfect influencer match with AI-powered search',
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
      lang="en"
      className={`${dmSans.variable} ${jetbrainsMono.variable} ${instrumentSerif.variable}`}
    >
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
