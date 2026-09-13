// Adapts the project's own src/shots/brand.json (written from strategic-brief.md) to the
// names the shot library expects. This plugin ships no brand palette: COLORS traces back to the
// client's brand.json. The only defaults here are neutral browser-chrome greys and a white mark on
// the accent, each overridable from brand.json.
import { Easing } from 'remotion';
import brand from '../shots/brand.json';

type BrandFile = typeof brand & {
  onAccent?: string;
  browserChrome?: Partial<Record<string, string>>;
};

export const COLORS = {
  paper: brand.background,
  ink: brand.ink,
  muted: brand.inkSoft,
  accent: brand.accent,
  signal: brand.accent,
  line: `${brand.inkSoft}55`,
  warn: brand.accent,
  cream: brand.background,
  // Mark drawn ON an accent fill (e.g. the check in ImageRevealShot's tag). White unless the
  // project's brand.json sets "onAccent" for an accent too light to carry white.
  onAccent: (brand as BrandFile).onAccent ?? '#ffffff',
};

// Colours of the imitation browser window itself (tab strip, URL bar, traffic lights, empty page).
// These are NOT the client's brand: a screencast has to look like a real browser, and a real
// browser is grey. They live here as named tokens rather than inline literals, and a project can
// override any of them with an optional "browserChrome" block in brand.json (e.g. a dark-mode
// browser for a dark product).
const CHROME_DEFAULTS = {
  chrome: '#dee1e6',
  tabActive: '#f7f8fa',
  urlBar: '#eff1f4',
  text: '#3c4043',
  dim: '#5f6368',
  disabled: '#b9bdc4',
  close: '#ff5f57',
  minimize: '#febc2e',
  zoom: '#28c840',
  page: '#ffffff',
  cursorFill: '#111318',
  cursorStroke: '#ffffff',
};
export const CHROME_COLORS = { ...CHROME_DEFAULTS, ...((brand as BrandFile).browserChrome ?? {}) };

export const FONT_DISPLAY = brand.displayFont;
export const FONT_BODY = brand.bodyFont;
export const FONT_MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';
export const EASINGS = {
  easeOut: Easing.bezier(0.16, 1, 0.3, 1),
  easeInOut: Easing.bezier(0.65, 0, 0.35, 1),
};
export const SHADOW = { card: '0 24px 60px rgba(0,0,0,0.28)' };
export const RADIUS = { card: 20, pill: 999 };
