import '@testing-library/jest-dom';
import { vi } from 'vitest';
import React from 'react';

// Mock ResizeObserver (required by recharts)
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock next/image
vi.mock('next/image', () => ({
  default: function MockImage(props: { src: string; alt: string; fill?: boolean; className?: string }) {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    return React.createElement('img', {
      src: props.src,
      alt: props.alt,
      className: props.className,
      'data-fill': props.fill,
    });
  },
}));

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
});

// Mock window.open
Object.assign(window, {
  open: vi.fn(),
});
