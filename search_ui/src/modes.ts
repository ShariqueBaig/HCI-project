import type { HciState, ThemeId, ViewPolicyName } from './types';

export interface ThemeMeta {
  id: ThemeId;
  name: string;
  desc: string;
  isLight: boolean;
  badge: 'AA' | 'AAA';
  swatches: [string, string, string]; // [bg, surface, accent]
}

export const THEMES: ThemeMeta[] = [
  {
    id: 'dark',
    name: 'Calm Obsidian',
    desc: 'Deep dark · low-light focus',
    isLight: false,
    badge: 'AA',
    swatches: ['#0c0b12', '#161420', '#7fb8a4'],
  },
  {
    id: 'slate',
    name: 'Nordic Dusk',
    desc: 'Soft twilight · reduced glare',
    isLight: false,
    badge: 'AA',
    swatches: ['#181d26', '#212834', '#7dc7b4'],
  },
  {
    id: 'light',
    name: 'Warm Paper',
    desc: 'Crisp off-white · best for dense reading',
    isLight: true,
    badge: 'AA',
    swatches: ['#f8f6f1', '#ffffff', '#2a6b55'],
  },
  {
    id: 'sepia',
    name: 'Book Sepia',
    desc: 'Warm parchment · gentle on tired eyes',
    isLight: true,
    badge: 'AA',
    swatches: ['#f3ead8', '#fbf5e9', '#24634e'],
  },
  {
    id: 'contrast',
    name: 'High Contrast',
    desc: 'Pure black & white · WCAG AAA ≥ 7:1',
    isLight: false,
    badge: 'AAA',
    swatches: ['#000000', '#0a0a0a', '#5ce6b8'],
  },
];

export function isLightTheme(theme: ThemeId): boolean {
  return theme === 'light' || theme === 'sepia';
}

export interface ViewModeMeta {
  id: ViewPolicyName;
  name: string;
  moodHint: string;
  shortDesc: string;
  calmChrome: boolean;
  swatchDark: string;
  swatchLight: string;
}

/** User-facing presentation modes with distinct atmospheric accents & researcher mood hints. */
export const VIEW_MODES: Record<ViewPolicyName, ViewModeMeta> = {
  overwhelmed: {
    id: 'overwhelmed',
    name: 'Simple View',
    moodHint: 'Overwhelmed',
    shortDesc: 'Eucalyptus calm · 1 clear answer & next step',
    calmChrome: true,
    swatchDark: '#73c4a8',
    swatchLight: '#256654',
  },
  fatigued: {
    id: 'fatigued',
    name: 'Easy-Read View',
    moodHint: 'Fatigued',
    shortDesc: 'Warm amber · larger type & read-aloud',
    calmChrome: true,
    swatchDark: '#ebae5c',
    swatchLight: '#9a4a06',
  },
  disoriented: {
    id: 'disoriented',
    name: 'Guided View',
    moodHint: 'Disoriented',
    shortDesc: 'Sky compass · search trail & narrowing options',
    calmChrome: false,
    swatchDark: '#63c3eb',
    swatchLight: '#036196',
  },
  focused: {
    id: 'focused',
    name: 'Focused View',
    moodHint: 'Focused',
    shortDesc: 'Cobalt studio · full detail & side sources',
    calmChrome: false,
    swatchDark: '#6aa6ff',
    swatchLight: '#1d4ed8',
  },
  energized: {
    id: 'energized',
    name: 'Explore View',
    moodHint: 'Energized / Happy',
    shortDesc: 'Violet studio · comparisons, facets & interactive view',
    calmChrome: false,
    swatchDark: '#b794ff',
    swatchLight: '#6324c7',
  },
  neutral: {
    id: 'neutral',
    name: 'Standard View',
    moodHint: 'Neutral',
    shortDesc: 'Balanced layout, consistent across sessions',
    calmChrome: false,
    swatchDark: '#7fb8a4',
    swatchLight: '#2a6b55',
  },
};

export const MODE_ORDER: ViewPolicyName[] = [
  'focused',
  'overwhelmed',
  'fatigued',
  'disoriented',
  'energized',
  'neutral',
];

/** Internal researcher state labels (used ONLY in Researcher Lab / XAI Inspector). */
export const LAB_STATE_LABEL: Record<HciState, string> = {
  focused: 'Focused',
  overwhelmed: 'Overwhelmed',
  fatigued: 'Fatigued',
  energized: 'Energized / Happy',
  disoriented: 'Disoriented',
};
