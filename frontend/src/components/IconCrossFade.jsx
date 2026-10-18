import React from 'react';

/**
 * Better-UI: Exact Contextual Icon Cross-Fade (CSS recipe)
 * Keeps both icons mounted in a single grid cell.
 * Transitions scale (0.25 -> 1), opacity (0 -> 1), and blur (4px -> 0px)
 * over 300ms with cubic-bezier(0.2, 0, 0, 1).
 * Motion is gated behind prefers-reduced-motion.
 */
export default function IconCrossFade({
  isActive,
  ActiveIcon,
  InactiveIcon,
  size = 14,
  className = '',
  style = {}
}) {
  return (
    <span
      className={`icon-crossfade-box ${className}`}
      style={{
        display: 'inline-grid',
        placeItems: 'center',
        verticalAlign: 'middle',
        ...style
      }}
      aria-hidden="true"
    >
      <span
        className={`icon-crossfade-layer ${isActive ? 'visible' : 'hidden'}`}
        style={{ gridArea: '1 / 1' }}
      >
        <ActiveIcon size={size} />
      </span>
      <span
        className={`icon-crossfade-layer ${isActive ? 'hidden' : 'visible'}`}
        style={{ gridArea: '1 / 1' }}
      >
        <InactiveIcon size={size} />
      </span>
    </span>
  );
}
