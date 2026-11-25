// Chalk sketches for the unit headers on the contents page, one per unit, drawn in the unit's colour.
// Each entry is the inside of an SVG with viewBox 0 0 600 180; keep the left ~200 px light (the unit title sits there
// on narrow screens). Classes, styled in lib/units.css:
//   d  a stroke that draws itself in when the unit scrolls into view (--k orders the strokes)
//   t  text or a filled shape that fades in
//   a  a faint chalk white instead of the unit colour;  faint  even fainter
// A sketch may add one looping motion after it is drawn: give an element a class that lib/units.css animates (swap-a,
// hop, orbit, ride, spin, tilt, breathe, ...), or add your own .seen .unit-art .NAME rule and keyframes in a <style> in index.html.
'use strict';
(() => {
  let k = 0;
  const P = (d, cls = '', extra = '') => `<path class="d ${cls}" pathLength="1" style="--k:${k++}" d="${d}" ${extra}/>`;
  const Tx = (x, y, s, size = 24, cls = '', anchor = 'start') => `<text class="t ${cls}" style="--k:${k++}" x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}">${s}</text>`;
  const C = (cx, cy, r, cls = '') => `<circle class="d ${cls}" pathLength="1" style="--k:${k++}" cx="${cx}" cy="${cy}" r="${r}"/>`;
  const reset = s => { k = 0; return s; };

  window.UNIT_ART = [
    reset(P('M250 92H350V142H250Z') + P('M470 92H570V142H470Z') + P('M350 117H470') +
      P('M382 117H430', 'a') + P('M430 117H454', 'a') +
      `<circle class="t ride" r="9" fill="currentColor" stroke="none" style="--k:${k++};offset-path:path('M350 117H470')"/>` +
      Tx(260, 82, '发送', 20) + Tx(480, 82, '接收', 20) +
      Tx(410, 54, 't = L / R', 24, '', 'middle') + C(545, 54, 5, 'a')),
    reset(P('M220 92H290V142H220Z') + P('M370 92H440V142H370Z') + P('M520 92H590V142H520Z') +
      P('M290 117H370') + P('M440 117H520') +
      `<circle class="t ride" r="8" fill="currentColor" stroke="none" style="--k:${k++};offset-path:path('M290 117H520')"/>` +
      Tx(255, 82, '节点 1', 20, '', 'middle') + Tx(405, 82, '节点 2', 20, '', 'middle') + Tx(555, 82, '节点 3', 20, '', 'middle') +
      Tx(405, 166, '收到完整分组，再发往下一跳', 22, '', 'middle')),
    reset(P('M230 88H320V148H230Z') + P('M470 88H560V148H470Z') + P('M320 104H470') + P('M470 132H320') +
      P('M382 100L398 116 M398 100L382 116', 'a') +
      `<circle class="t orbit" r="8" fill="currentColor" stroke="none" style="--k:${k++};offset-path:path('M330 104H460')"/>` +
      Tx(275, 78, '发送方', 20, '', 'middle') + Tx(515, 78, '接收方', 20, '', 'middle') +
      Tx(395, 46, 'DATA', 20, '', 'middle') + Tx(395, 76, 'ACK', 20, 'a', 'middle') +
      Tx(410, 166, '超时重传，序列号去重', 22, '', 'end')),
  ];
})();
