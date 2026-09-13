// WebBrowserFrame — reusable TSX browser window: traffic lights + tab + URL bar
// + a scrollable page region, with animated highlight helpers. Used for real
// service pages / real results shown in a browser. Frame-based only.
import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { COLORS, EASINGS, FONT_BODY, FONT_MONO, SHADOW } from './brand';
import { CLAMP } from './kit';

const BR = {
  chrome: '#dee1e6', chromeDark: '#202124', tabActive: '#f7f8fa', urlBar: '#eff1f4',
  text: '#3c4043', dim: '#5f6368',
} as const;

// ---- inline icon set (24x24 viewBox, stroke-based) — no icon package needed --
type IconProps = { size?: number; color?: string; strokeWidth?: number; style?: React.CSSProperties };

const makeIcon = (children: React.ReactNode): React.FC<IconProps> => ({
  size = 24, color = 'currentColor', strokeWidth = 2, style,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" style={style}>
    {children}
  </svg>
);

const ArrowLeft = makeIcon(<><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></>);
const ArrowRight = makeIcon(<><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></>);
const RotateCw = makeIcon(<><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>);
const Lock = makeIcon(<><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></>);
const Star = makeIcon(<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />);
const MoreVertical = makeIcon(<><circle cx="12" cy="12" r="1" /><circle cx="12" cy="5" r="1" /><circle cx="12" cy="19" r="1" /></>);
const Plus = makeIcon(<><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>);
const X = makeIcon(<><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>);

// Chrome heights at a given uiScale — exported so callers can place things relative to the
// page region without duplicating the constants.
export const CHROME = { tab: 46, nav: 56 } as const;
export const chromeH = (uiScale = 1) => (CHROME.tab + CHROME.nav) * uiScale;

export const WebBrowserFrame: React.FC<{
  // A plain string renders as the usual single-line, ellipsised URL. Pass a node instead when
  // the URL itself is the subject of the shot (per-segment highlights, strikes, labels) — the
  // node is rendered UNCLIPPED so absolutely-positioned annotation children can escape the pill.
  url: React.ReactNode;
  tabTitle: string;
  favicon?: React.ReactNode;
  box?: { x: number; y: number; w: number; h: number };
  appearAt?: number;
  scrollY?: number;
  pageBg?: string;
  // Scales the chrome (tab strip, nav bar, fonts, icons). Desktop 16:9 shots want 1; a vertical
  // 1080-wide short needs ~1.9 for the URL to be legible on a phone.
  uiScale?: number;
  children?: React.ReactNode;
}> = ({ url, tabTitle, favicon, box = { x: 80, y: 44, w: 1760, h: 992 }, appearAt = 0, scrollY = 0, pageBg = '#ffffff', uiScale = 1, children }) => {
  const frame = useCurrentFrame();
  const op = interpolate(frame, [appearAt, appearAt + 14], [0, 1], { ...CLAMP, easing: EASINGS.easeOut });
  const y = interpolate(frame, [appearAt, appearAt + 16], [28, 0], { ...CLAMP, easing: EASINGS.easeOut });
  const s = (n: number) => n * uiScale;
  const TAB_H = s(CHROME.tab), NAV_H = s(CHROME.nav);
  return (
    <div style={{
      position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h,
      borderRadius: s(14), overflow: 'hidden', border: `1px solid ${COLORS.line}`,
      boxShadow: SHADOW.card, opacity: op, transform: `translateY(${y}px)`,
      fontFamily: FONT_BODY, background: pageBg,
    }}>
      {/* tab strip — chrome sits ABOVE the page region, as it does in a real browser, so a URL
          annotation that hangs below the bar isn't painted over by the page. */}
      <div style={{ position: 'relative', zIndex: 2, height: TAB_H, background: BR.chrome, display: 'flex', alignItems: 'flex-end', paddingLeft: s(14) }}>
        <div style={{ display: 'flex', gap: s(9), alignItems: 'center', paddingBottom: s(15), paddingRight: s(16) }}>
          <span style={{ width: s(13), height: s(13), borderRadius: '50%', background: '#ff5f57' }} />
          <span style={{ width: s(13), height: s(13), borderRadius: '50%', background: '#febc2e' }} />
          <span style={{ width: s(13), height: s(13), borderRadius: '50%', background: '#28c840' }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: s(10), background: BR.tabActive, borderRadius: `${s(10)}px ${s(10)}px 0 0`, padding: `${s(9)}px ${s(16)}px`, minWidth: s(260), maxWidth: s(420) }}>
          {favicon ?? <span style={{ width: s(17), height: s(17), borderRadius: s(4), background: COLORS.accent }} />}
          <span style={{ fontSize: s(17), color: BR.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{tabTitle}</span>
          <X size={s(15)} color={BR.dim} />
        </div>
        <Plus size={s(18)} color={BR.dim} style={{ margin: `0 0 ${s(14)}px ${s(12)}px` }} />
      </div>
      {/* nav / URL bar */}
      <div style={{ position: 'relative', zIndex: 2, height: NAV_H, background: BR.tabActive, display: 'flex', alignItems: 'center', gap: s(14), padding: `0 ${s(18)}px`, borderBottom: `1px solid ${BR.chrome}` }}>
        <ArrowLeft size={s(20)} color={BR.text} strokeWidth={2.2} />
        <ArrowRight size={s(20)} color="#b9bdc4" strokeWidth={2.2} />
        <RotateCw size={s(18)} color={BR.text} strokeWidth={2.2} />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: s(10), background: BR.urlBar, borderRadius: 999, padding: `${s(8)}px ${s(18)}px` }}>
          <Lock size={s(15)} color={BR.dim} />
          {typeof url === 'string' ? (
            <span style={{ fontFamily: FONT_MONO, fontSize: s(17), color: BR.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{url}</span>
          ) : (
            url
          )}
        </div>
        <Star size={s(18)} color={BR.dim} />
        <MoreVertical size={s(18)} color={BR.dim} />
      </div>
      {/* page (scrollable) */}
      <div style={{ position: 'absolute', top: TAB_H + NAV_H, left: 0, right: 0, bottom: 0, overflow: 'hidden', background: pageBg }}>
        <div style={{ transform: `translateY(${-scrollY}px)` }}>{children}</div>
      </div>
    </div>
  );
};

// Animated marker highlight behind inline text (sweeps left -> right at `start`).
export const Marker: React.FC<{ start: number; color?: string; children: React.ReactNode; pad?: number; radius?: number }> =
  ({ start, color = `${COLORS.warn}99`, children, pad = 4, radius = 5 }) => {
    const frame = useCurrentFrame();
    const sweep = interpolate(frame, [start, start + 16], [0, 1], { ...CLAMP, easing: EASINGS.easeInOut });
    // atomic inline box (no line fragmentation) so the sweep spans the phrase
    return (
      <span style={{ position: 'relative', display: 'inline-block', whiteSpace: 'nowrap' }}>
        <span style={{ position: 'absolute', left: -pad, right: -pad, top: -2, bottom: -2, background: color, borderRadius: radius, transform: `scaleX(${sweep})`, transformOrigin: 'left', zIndex: 0 }} />
        <span style={{ position: 'relative', zIndex: 1 }}>{children}</span>
      </span>
    );
  };

// Animated rounded ring that draws attention to a block (fades + settles).
export const Ring: React.FC<{ start: number; color?: string; style?: React.CSSProperties }> = ({ start, color = COLORS.accent, style }) => {
  const frame = useCurrentFrame();
  const op = interpolate(frame, [start, start + 12], [0, 1], { ...CLAMP, easing: EASINGS.easeOut });
  const sc = interpolate(frame, [start, start + 16], [1.06, 1], { ...CLAMP, easing: EASINGS.easeOut });
  return (
    <div style={{
      position: 'absolute', inset: -8, border: `3px solid ${color}`, borderRadius: 12,
      opacity: op, transform: `scale(${sc})`, pointerEvents: 'none', ...style,
    }} />
  );
};
