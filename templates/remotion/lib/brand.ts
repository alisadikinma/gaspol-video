// Adapts the project's own src/shots/brand.json (written from strategic-brief.md) to the
// names the shot library expects. This plugin ships no palette — every value here traces
// back to the client's brand.json, never a hardcoded default.
import { Easing } from 'remotion';
import brand from '../shots/brand.json';

export const COLORS = {
  paper: brand.background,
  ink: brand.ink,
  muted: brand.inkSoft,
  accent: brand.accent,
  signal: brand.accent,
  line: `${brand.inkSoft}55`,
  warn: brand.accent,
  cream: brand.background,
};
export const FONT_DISPLAY = brand.displayFont;
export const FONT_BODY = brand.bodyFont;
export const FONT_MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';
export const EASINGS = {
  easeOut: Easing.bezier(0.16, 1, 0.3, 1),
  easeInOut: Easing.bezier(0.65, 0, 0.35, 1),
};
export const SHADOW = { card: '0 24px 60px rgba(0,0,0,0.28)' };
export const RADIUS = { card: 20, pill: 999 };
