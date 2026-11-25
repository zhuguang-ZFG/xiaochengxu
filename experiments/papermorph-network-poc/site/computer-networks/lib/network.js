'use strict';

function networkLatency(parent, initialRate = 10, options = {}) {
  const PACKET_BITS = 12000;
  const PROPAGATION_MS = 10;
  const BAR_MAX_MS = 22;
  const RATE_MIN = 1;
  const RATE_MAX = 100;
  const BAR_X = 300;
  const BAR_Y = 470;
  const BAR_W = 1000;
  const BAR_H = 44;
  const TRACK_X = 420;
  const TRACK_W = 760;
  const TRACK_Y = 680;
  const ORANGE = '#d96c3f';
  const BLUE = '#247ba0';
  const INK = '#202b33';
  const DIM = '#667078';
  const PAPER = '#f7f3e8';
  const part = options.part || 'full';
  const showSlider = options.slider === true;
  const compact = options.compact === true;
  const v = { rate: Math.max(RATE_MIN, Math.min(RATE_MAX, Math.round(initialRate))) };
  const listeners = new Set();
  let live = false;
  let dragging = false;

  const root = G(parent, { y: compact ? -70 : 0 });
  root.classList.add('network-figure');
  root.setAttribute('role', 'group');
  root.setAttribute('aria-label', '链路速率与时延互动图');

  const title = T(root, options.title ?? '一条链路，两段时间', {
    x: 800, y: compact ? 110 : 82, size: 34, fill: DIM, anchor: 'middle', weight: 600,
  });

  mk('rect', { x: 110, y: 220, width: 230, height: 112, rx: 20, fill: PAPER, stroke: INK, 'stroke-width': 3 }, root);
  mk('rect', { x: 1260, y: 220, width: 230, height: 112, rx: 20, fill: PAPER, stroke: INK, 'stroke-width': 3 }, root);
  T(root, '发送器', { x: 225, y: 205, size: 30, fill: INK, anchor: 'middle', weight: 600 });
  T(root, '接收器', { x: 1375, y: 205, size: 30, fill: INK, anchor: 'middle', weight: 600 });
  mk('rect', { x: 160, y: 240, width: 130, height: 54, rx: 10, fill: INK }, root);
  T(root, '1500 B', { x: 225, y: 276, size: 25, fill: PAPER, anchor: 'middle', font: MATH, weight: 600 });

  mk('line', { x1: 340, y1: 276, x2: 1260, y2: 276, stroke: INK, 'stroke-width': 5, 'stroke-linecap': 'round' }, root);
  mk('line', { x1: 340, y1: 292, x2: 1260, y2: 292, stroke: DIM, 'stroke-width': 2, 'stroke-dasharray': '10 12' }, root);

  const bits = Array.from({ length: 12 }, (_, i) => {
    const bit = mk('rect', {
      x: 372 + i * 70, y: 258, width: 46, height: 34, rx: 7,
      fill: ORANGE, stroke: PAPER, 'stroke-width': 2,
    }, root);
    put(bit, { o: 0 });
    return bit;
  });
  const bitsNote = T(root, '示意：12 块，每块代表 1000 bit', { x: 800, y: 360, size: 22, fill: DIM, anchor: 'middle' });

  const pulse = G(root, { x: 340, y: 276, o: 0 });
  mk('circle', { cx: 0, cy: 0, r: 15, fill: BLUE, stroke: PAPER, 'stroke-width': 3 }, pulse);

  const txValue = T(root, '', { x: 500, y: 414, size: 42, fill: ORANGE, anchor: 'middle', font: MATH, weight: 600 });
  const txLabel = T(root, '传输时延', { x: 500, y: 452, size: 24, fill: DIM, anchor: 'middle' });
  const propValue = T(root, '10.0 ms', { x: 1100, y: 414, size: 42, fill: BLUE, anchor: 'middle', font: MATH, weight: 600 });
  const propLabel = T(root, '传播时延 · 固定', { x: 1100, y: 452, size: 24, fill: DIM, anchor: 'middle' });

  mk('rect', { x: BAR_X, y: BAR_Y, width: BAR_W, height: BAR_H, rx: 12, fill: '#e7dfcf' }, root);
  const txBar = mk('rect', { x: BAR_X, y: BAR_Y, width: 0, height: BAR_H, rx: 12, fill: ORANGE }, root);
  const propBar = mk('rect', { x: BAR_X, y: BAR_Y, width: 0, height: BAR_H, rx: 12, fill: BLUE }, root);
  const totalValue = T(root, '', { x: 800, y: 574, size: 48, fill: INK, anchor: 'middle', font: MATH, weight: 700 });
  const totalLabel = T(root, '简化总时延', { x: 800, y: 612, size: 24, fill: DIM, anchor: 'middle' });

  const slider = G(root);
  const rateValue = T(slider, '', { x: 800, y: 654, size: 36, fill: INK, anchor: 'middle', font: MATH, weight: 700 });
  T(slider, '链路速率', { x: 300, y: 690, size: 26, fill: DIM, anchor: 'start', weight: 600 });
  mk('line', { x1: TRACK_X, y1: TRACK_Y, x2: TRACK_X + TRACK_W, y2: TRACK_Y, stroke: '#d8cebb', 'stroke-width': 14, 'stroke-linecap': 'round' }, slider);
  mk('line', { x1: TRACK_X, y1: TRACK_Y, x2: TRACK_X + TRACK_W, y2: TRACK_Y, stroke: INK, 'stroke-width': 2, 'stroke-dasharray': '2 18' }, slider);
  T(slider, '1', { x: TRACK_X, y: 722, size: 22, fill: DIM, anchor: 'middle', font: MATH });
  T(slider, '50', { x: TRACK_X + TRACK_W / 2, y: 722, size: 22, fill: DIM, anchor: 'middle', font: MATH });
  T(slider, '100 Mbps', { x: TRACK_X + TRACK_W, y: 722, size: 22, fill: DIM, anchor: 'end', font: MATH });

  const knob = G(slider, { x: 0, y: TRACK_Y });
  knob.classList.add('rate-control');
  knob.setAttribute('role', 'slider');
  knob.setAttribute('aria-label', '链路速率，单位 Mbps');
  knob.setAttribute('aria-valuemin', String(RATE_MIN));
  knob.setAttribute('aria-valuemax', String(RATE_MAX));
  knob.setAttribute('tabindex', '-1');
  const knobCircle = mk('circle', { class: 'rate-knob', cx: 0, cy: 0, r: 19, fill: INK, stroke: PAPER, 'stroke-width': 4 }, knob);
  const hit = mk('circle', { class: 'rate-hit', cx: 0, cy: 0, r: 34, fill: 'transparent', 'pointer-events': 'none' }, knob);
  hit.style.touchAction = 'none';
  hit.style.userSelect = 'none';

  const txFor = rate => PACKET_BITS / (rate * 1000);
  const totalFor = rate => txFor(rate) + PROPAGATION_MS;
  const formatMs = value => value >= 10 ? value.toFixed(2).replace(/0$/, '') : value >= 1 ? value.toFixed(1) : value.toFixed(2);
  const rateX = rate => TRACK_X + (rate - RATE_MIN) / (RATE_MAX - RATE_MIN) * TRACK_W;

  function draw() {
    const tx = txFor(v.rate);
    const total = totalFor(v.rate);
    const txW = tx / BAR_MAX_MS * BAR_W;
    const propW = PROPAGATION_MS / BAR_MAX_MS * BAR_W;
    txValue.textContent = `${formatMs(tx)} ms`;
    totalValue.textContent = `${formatMs(total)} ms`;
    rateValue.textContent = `${v.rate} Mbps`;
    txBar.setAttribute('width', txW.toFixed(2));
    propBar.setAttribute('x', (BAR_X + txW).toFixed(2));
    propBar.setAttribute('width', propW.toFixed(2));
    put(knob, { x: rateX(v.rate) });
    knob.setAttribute('aria-valuenow', String(v.rate));
    knob.setAttribute('aria-valuetext', `${v.rate} Mbps，传输 ${formatMs(tx)} 毫秒，总时延 ${formatMs(total)} 毫秒`);
    for (const listener of listeners) listener(v.rate);
  }

  function set(values) {
    const rate = typeof values === 'number' ? values : values.rate;
    if (!Number.isFinite(rate)) return;
    v.rate = Math.max(RATE_MIN, Math.min(RATE_MAX, Math.round(rate)));
    draw();
  }

  function pointRate(event) {
    const matrix = root.getScreenCTM();
    if (!matrix) return v.rate;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return Math.round(RATE_MIN + (point.x - TRACK_X) / TRACK_W * (RATE_MAX - RATE_MIN));
  }

  hit.addEventListener('pointerdown', event => {
    if (!live) return;
    dragging = true;
    hit.setPointerCapture(event.pointerId);
    set(pointRate(event));
    knob.focus({ preventScroll: true });
    event.preventDefault();
    event.stopPropagation();
  });
  hit.addEventListener('pointermove', event => {
    if (!live || !dragging) return;
    set(pointRate(event));
    event.preventDefault();
    event.stopPropagation();
  });
  const endDrag = event => {
    if (!dragging) return;
    dragging = false;
    if (hit.hasPointerCapture(event.pointerId)) hit.releasePointerCapture(event.pointerId);
    event.preventDefault();
    event.stopPropagation();
  };
  hit.addEventListener('pointerup', endDrag);
  hit.addEventListener('pointercancel', endDrag);
  hit.addEventListener('click', event => event.stopPropagation());

  knob.addEventListener('keydown', event => {
    if (!live || event.shiftKey) return;
    const changes = {
      ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1,
      PageUp: 10, PageDown: -10,
    };
    if (event.key === 'Home') set(RATE_MIN);
    else if (event.key === 'End') set(RATE_MAX);
    else if (changes[event.key]) set(v.rate + changes[event.key]);
    else if (event.key === 'Enter' && typeof P.keys === 'function') {
      // The player leaves Enter to focused controls; forward it to the active question or playground.
      event.preventDefault();
      event.stopPropagation();
      P.keys(event);
      return;
    } else return;
    event.preventDefault();
    event.stopPropagation();
  });

  if (part === 'transmission') {
    for (const element of [propValue, propLabel, propBar, totalValue, totalLabel, slider]) element.style.display = 'none';
  } else if (part === 'propagation') {
    for (const element of [txValue, txLabel, txBar, totalValue, totalLabel, slider, bitsNote, ...bits]) element.style.display = 'none';
  }
  if (!showSlider) slider.style.display = 'none';

  draw();

  return {
    v,
    el: root,
    bits,
    bitsNote,
    pulse,
    txValue,
    txLabel,
    txBar,
    get txWidth() { return BAR_W * txFor(v.rate) / BAR_MAX_MS; },
    propValue,
    propLabel,
    propBar,
    totalValue,
    totalLabel,
    knob,
    get tx() { return txFor(v.rate); },
    get total() { return totalFor(v.rate); },
    set,
    to(values, at, dur, ease = io) {
      const from = v.rate;
      const target = Math.max(RATE_MIN, Math.min(RATE_MAX, values.rate));
      prog(q => set(from + (target - from) * q), at, dur, ease);
    },
    live(on) {
      live = !!on;
      root.classList.toggle('is-live', live);
      knob.setAttribute('tabindex', live ? '0' : '-1');
      knob.setAttribute('aria-disabled', live ? 'false' : 'true');
      hit.setAttribute('pointer-events', live ? 'all' : 'none');
      knobCircle.style.cursor = live ? 'ew-resize' : 'default';
    },
    nudge(delta) { set(v.rate + delta); },
    focus() { if (live) knob.focus({ preventScroll: true }); },
    onChange(listener) { listeners.add(listener); return () => listeners.delete(listener); },
  };
}
