'use strict';

function storeForward(parent, initialRate = 10, options = {}) {
  const PACKET_BITS = 12000;
  const PROPAGATION_MS = 2;
  const BAR_MAX_MS = 42;
  const RATE_MIN = 1;
  const RATE_MAX = 100;
  const BAR_X = 300;
  const BAR_W = 1000;
  const TRACK_X = 420;
  const TRACK_W = 760;
  const ORANGE = '#d96c3f';
  const BLUE = '#247ba0';
  const INK = '#202b33';
  const DIM = '#667078';
  const PAPER = '#f7f3e8';
  const TRACK = '#e7dfcf';
  const compact = options.compact === true;
  const showSlider = options.slider === true;
  const hideTotal = options.hideTotal === true;
  const nodeY = compact ? 180 : 210;
  const readoutY = compact ? 310 : 360;
  const timelineTitleY = compact ? 380 : 430;
  const sliderLabelY = compact ? 650 : 735;
  const sliderY = compact ? 690 : 775;
  const sliderEndY = compact ? 725 : 810;
  const centers = [160, 600, 1040, 1480];
  const nodeW = 170;
  const linkWidth = centers[1] - centers[0] - nodeW;
  const v = { rate: Math.max(RATE_MIN, Math.min(RATE_MAX, Math.round(initialRate))) };
  const listeners = new Set();
  let live = false;
  let dragging = false;
  let phase = 'ready';
  let motion = null;

  const root = G(parent, { y: options.y ?? (compact ? -60 : 0) });
  root.classList.add('store-forward-figure');
  root.setAttribute('role', 'group');
  root.setAttribute('aria-label', '三跳存储转发互动图');

  const title = options.title === '' ? null : T(root, options.title ?? '一个数据包，三段存储转发', {
    x: 800, y: 70, size: 34, fill: DIM, anchor: 'middle', weight: 600,
  });

  const nodes = centers.map((x, i) => {
    const g = G(root, { x, y: nodeY });
    g.classList.add('route-node');
    g.dataset.node = String(i);
    mk('rect', { x: -nodeW / 2, y: -43, width: nodeW, height: 86, rx: 18, fill: PAPER, stroke: INK, 'stroke-width': 3 }, g);
    if (i === 0 || i === 3) {
      mk('circle', { cx: 0, cy: 0, r: 16, fill: INK }, g);
    } else {
      mk('path', { d: 'M-42 0H42 M0-22V22 M-42-22H42 M-42 22H42', fill: 'none', stroke: INK, 'stroke-width': 3, 'stroke-linecap': 'round' }, g);
    }
    T(g, ['发送', '路由器 1', '路由器 2', '目的端'][i], {
      x: 0, y: -61, size: 25, fill: INK, anchor: 'middle', weight: 600,
    });
    return g;
  });

  const linkLabels = [];
  const hopValues = [];
  const fills = [];
  for (let i = 0; i < 3; i++) {
    const x1 = centers[i] + nodeW / 2;
    const x2 = centers[i + 1] - nodeW / 2;
    const mid = (x1 + x2) / 2;
    mk('line', { x1, y1: nodeY, x2, y2: nodeY, stroke: INK, 'stroke-width': 6, 'stroke-linecap': 'round' }, root);
    mk('line', { x1, y1: nodeY + 17, x2, y2: nodeY + 17, stroke: DIM, 'stroke-width': 2, 'stroke-dasharray': '8 10' }, root);
    const linkLabel = T(root, '', { x: mid, y: nodeY - 48, size: 28, fill: BLUE, anchor: 'middle', font: MATH, weight: 700 });
    linkLabel.classList.add('link-rate');
    linkLabels.push(linkLabel);
    const hopValue = T(root, '', { x: mid, y: nodeY + 58, size: 27, fill: INK, anchor: 'middle', font: MATH, weight: 600 });
    hopValue.classList.add('hop-value');
    hopValues.push(hopValue);
    T(root, '每跳', { x: mid, y: nodeY + 86, size: 19, fill: DIM, anchor: 'middle' });
    fills.push(mk('rect', { x: x1, y: nodeY - 7, width: 0, height: 14, rx: 7, fill: ORANGE, 'pointer-events': 'none' }, root));
  }

  const routerFills = [1, 2].map(i => mk('rect', {
    x: centers[i] - 65, y: nodeY - 14, width: 0, height: 28, rx: 6, fill: ORANGE, 'pointer-events': 'none',
  }, root));

  const packet = G(root, { x: centers[0], y: nodeY, o: 1 });
  packet.classList.add('route-packet');
  mk('rect', { x: -52, y: -21, width: 104, height: 42, rx: 10, fill: INK, stroke: PAPER, 'stroke-width': 2 }, packet);
  T(packet, '1500 B', { x: 0, y: 8, size: 22, fill: PAPER, anchor: 'middle', font: MATH, weight: 700 });

  const pulse = G(root, { x: centers[0] + nodeW / 2, y: nodeY, o: 0 });
  mk('circle', { cx: 0, cy: 0, r: 13, fill: BLUE, stroke: PAPER, 'stroke-width': 3 }, pulse);

  const txValue = T(root, '', { x: 400, y: readoutY, size: 42, fill: ORANGE, anchor: 'middle', font: MATH, weight: 700 });
  T(root, '传输时延 / 每跳', { x: 400, y: readoutY + 38, size: 23, fill: DIM, anchor: 'middle' });
  const propValue = T(root, '2.0 ms', { x: 800, y: readoutY, size: 42, fill: BLUE, anchor: 'middle', font: MATH, weight: 700 });
  T(root, '传播时延 · 固定', { x: 800, y: readoutY + 38, size: 23, fill: DIM, anchor: 'middle' });
  const totalValue = T(root, '', { x: 1200, y: readoutY, size: 42, fill: INK, anchor: 'middle', font: MATH, weight: 700 });
  T(root, '三跳总时延', { x: 1200, y: readoutY + 38, size: 23, fill: DIM, anchor: 'middle' });

  T(root, '固定时间轴 0–42 ms', { x: BAR_X, y: timelineTitleY, size: 25, fill: DIM, anchor: 'start', weight: 600 });
  const axisY = timelineTitleY + 18;
  const axis = mk('rect', {
    class: 'time-axis', x: BAR_X, y: axisY, width: BAR_W, height: 8, rx: 4, fill: TRACK, 'data-max-ms': String(BAR_MAX_MS),
  }, root);
  for (let t = 0; t <= 40; t += 10) {
    const x = BAR_X + t / BAR_MAX_MS * BAR_W;
    mk('line', { x1: x, y1: axisY + 8, x2: x, y2: axisY + 17, stroke: DIM, 'stroke-width': 2 }, root);
    T(root, String(t), { x, y: axisY + 38, size: 18, fill: DIM, anchor: 'middle', font: MATH });
  }
  mk('line', { x1: BAR_X + BAR_W, y1: axisY + 8, x2: BAR_X + BAR_W, y2: axisY + 17, stroke: DIM, 'stroke-width': 2 }, root);
  T(root, '42', { x: BAR_X + BAR_W, y: axisY + 38, size: 18, fill: DIM, anchor: 'middle', font: MATH });

  const txBars = [];
  const propBars = [];
  for (let i = 0; i < 3; i++) {
    const y = timelineTitleY + 70 + i * 65;
    T(root, `第 ${i + 1} 跳`, { x: 250, y: y + 21, size: 23, fill: DIM, anchor: 'end', weight: 600 });
    mk('rect', { x: BAR_X, y, width: BAR_W, height: 28, rx: 6, fill: TRACK }, root);
    txBars.push(mk('rect', { class: 'timeline-segment tx', x: BAR_X, y, width: 0, height: 28, rx: 6, fill: ORANGE }, root));
    propBars.push(mk('rect', { class: 'timeline-segment prop', x: BAR_X, y, width: 0, height: 28, rx: 6, fill: BLUE }, root));
  }

  const slider = G(root);
  slider.classList.add('rate-slider');
  T(slider, '三条链路共用速率', { x: BAR_X, y: sliderLabelY, size: 25, fill: DIM, anchor: 'start', weight: 600 });
  const rateValue = T(slider, '', { x: 800, y: sliderLabelY, size: 34, fill: INK, anchor: 'middle', font: MATH, weight: 700 });
  mk('line', { class: 'rate-track', x1: TRACK_X, y1: sliderY, x2: TRACK_X + TRACK_W, y2: sliderY, stroke: TRACK, 'stroke-width': 14, 'stroke-linecap': 'round' }, slider);
  mk('line', { x1: TRACK_X, y1: sliderY, x2: TRACK_X + TRACK_W, y2: sliderY, stroke: DIM, 'stroke-width': 2, 'stroke-dasharray': '2 18' }, slider);
  T(slider, '1', { x: TRACK_X, y: sliderEndY, size: 21, fill: DIM, anchor: 'middle', font: MATH });
  T(slider, '50', { x: TRACK_X + TRACK_W / 2, y: sliderEndY, size: 21, fill: DIM, anchor: 'middle', font: MATH });
  T(slider, '100 Mbps', { x: TRACK_X + TRACK_W, y: sliderEndY, size: 21, fill: DIM, anchor: 'end', font: MATH });

  const knob = G(slider, { x: 0, y: sliderY });
  knob.classList.add('rate-control');
  knob.setAttribute('role', 'slider');
  knob.setAttribute('aria-label', '三条链路共用速率，单位 Mbps');
  knob.setAttribute('aria-valuemin', String(RATE_MIN));
  knob.setAttribute('aria-valuemax', String(RATE_MAX));
  knob.setAttribute('tabindex', '-1');
  const knobCircle = mk('circle', { class: 'rate-knob', cx: 0, cy: 0, r: 19, fill: INK, stroke: PAPER, 'stroke-width': 4 }, knob);
  const hit = mk('rect', { class: 'rate-hit', x: -80, y: -50, width: 160, height: 100, rx: 24, fill: 'transparent', 'pointer-events': 'none' }, knob);
  hit.style.touchAction = 'auto';
  hit.style.userSelect = 'none';

  const txFor = rate => PACKET_BITS / (rate * 1000);
  const totalFor = rate => 3 * (txFor(rate) + PROPAGATION_MS);
  const formatMs = value => Math.abs(value * 10 - Math.round(value * 10)) < 1e-9 ? value.toFixed(1) : value.toFixed(2);
  const rateX = rate => TRACK_X + (rate - RATE_MIN) / (RATE_MAX - RATE_MIN) * TRACK_W;
  const setText = (e, value) => { if (e.textContent !== value) e.textContent = value; };
  const setAttr = (e, name, value) => { const s = String(value); if (e.getAttribute(name) !== s) e.setAttribute(name, s); };
  const setPhase = value => {
    if (phase === value) return;
    phase = value;
    root.dataset.phase = value;
  };

  function draw() {
    const tx = txFor(v.rate);
    const hop = tx + PROPAGATION_MS;
    const total = totalFor(v.rate);
    const txW = tx / BAR_MAX_MS * BAR_W;
    const propW = PROPAGATION_MS / BAR_MAX_MS * BAR_W;
    const rateLabel = `${v.rate} Mbps`;
    const hopLabel = `${formatMs(hop)} ms`;
    for (const e of linkLabels) setText(e, rateLabel);
    for (const e of hopValues) setText(e, hopLabel);
    setText(txValue, `${formatMs(tx)} ms`);
    setText(totalValue, hideTotal ? '? ms' : `${formatMs(total)} ms`);
    setText(rateValue, rateLabel);
    for (let i = 0; i < 3; i++) {
      setAttr(txBars[i], 'width', txW.toFixed(2));
      setAttr(propBars[i], 'x', (BAR_X + i * hop / BAR_MAX_MS * BAR_W + txW).toFixed(2));
      setAttr(propBars[i], 'width', propW.toFixed(2));
    }
    const totalDescription = hideTotal ? '总时延待计算' : `总时延 ${formatMs(total)} 毫秒`;
    put(knob, { x: rateX(v.rate) });
    setAttr(knob, 'aria-valuenow', String(v.rate));
    setAttr(knob, 'aria-valuetext', `${v.rate} Mbps，传输 ${formatMs(tx)} 毫秒，每跳 ${formatMs(hop)} 毫秒，${totalDescription}`);
    setAttr(root, 'aria-label', `三跳存储转发，共用速率 ${v.rate} Mbps，传输 ${formatMs(tx)} 毫秒，每跳 ${formatMs(hop)} 毫秒，${totalDescription}`);
    for (const listener of listeners) listener(v.rate);
  }

  function apply(rate) {
    const next = Math.max(RATE_MIN, Math.min(RATE_MAX, Math.round(rate)));
    if (next === v.rate) return;
    v.rate = next;
    draw();
  }

  function set(values) {
    const rate = typeof values === 'number' ? values : values.rate;
    if (!Number.isFinite(rate)) return;
    motion = null;
    apply(rate);
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
    const changes = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 };
    if (event.key === 'Home') set(RATE_MIN);
    else if (event.key === 'End') set(RATE_MAX);
    else if (changes[event.key]) set(v.rate + changes[event.key]);
    else if (event.key === 'Enter' && typeof P.keys === 'function') {
      event.preventDefault();
      event.stopPropagation();
      P.keys(event);
      return;
    } else return;
    knob.focus({ preventScroll: true });
    event.preventDefault();
    event.stopPropagation();
  });

  if (!showSlider) slider.style.display = 'none';
  setPhase('ready');
  draw();

  return {
    v,
    el: root,
    title,
    nodes,
    linkLabels,
    hopValues,
    fills,
    routerFills,
    packet,
    pulse,
    txValue,
    propValue,
    totalValue,
    txBars,
    propBars,
    rateValue,
    knob,
    hit,
    centers,
    linkWidth,
    get tx() { return txFor(v.rate); },
    get hop() { return txFor(v.rate) + PROPAGATION_MS; },
    get total() { return totalFor(v.rate); },
    set,
    to(values, at, dur, ease = io) {
      const from = v.rate;
      const target = Math.max(RATE_MIN, Math.min(RATE_MAX, values.rate));
      const token = {};
      motion = token;
      prog(q => {
        if (motion !== token) return;
        apply(from + (target - from) * q);
        if (q >= 1) motion = null;
      }, at, dur, ease);
    },
    live(on) {
      live = !!on;
      document.getElementById('stage').setAttribute('role', live ? 'group' : 'img');
      root.classList.toggle('is-live', live);
      setAttr(knob, 'tabindex', live ? '0' : '-1');
      setAttr(knob, 'aria-disabled', live ? 'false' : 'true');
      hit.style.pointerEvents = live ? 'all' : 'none';
      hit.style.touchAction = live ? 'none' : 'auto';
      knobCircle.style.cursor = live ? 'ew-resize' : 'default';
    },
    nudge(delta) { set(v.rate + delta); },
    focus() { if (live) knob.focus({ preventScroll: true }); },
    onChange(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    phase: setPhase,
  };
}
