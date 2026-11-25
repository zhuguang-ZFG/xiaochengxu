'use strict';

function reliableTransport(parent, initialFault = 0, options = {}) {
  const ONE_WAY_MS = 20;
  const TIMEOUT_MS = 60;
  const TOTAL_MS = 100;
  const ORANGE = '#d96c3f';
  const BLUE = '#247ba0';
  const RED = '#b54a3a';
  const INK = '#202b33';
  const DIM = '#667078';
  const PAPER = '#f7f3e8';
  const TRACK = '#e7dfcf';
  const compact = options.compact === true;
  const showControls = options.controls === true;
  const hideTotal = options.hideTotal === true;
  const nodeY = compact ? 175 : 205;
  const readoutY = compact ? 340 : 365;
  const controlY = compact ? 505 : 585;
  const timelineY = compact ? 635 : 680;
  const centers = [240, 800, 1360];
  const nodeW = 210;
  const names = ['正常', '数据丢失', '确认丢失'];
  const v = { fault: Math.max(0, Math.min(2, Math.round(initialFault))) };
  const listeners = new Set();
  let isLive = false;
  let current = null;

  const root = G(parent, { x: options.x ?? 0, y: options.y ?? (compact ? -50 : 0), s: options.s ?? 1 });
  root.classList.add('reliable-transport-figure');
  root.setAttribute('role', 'group');
  root.setAttribute('aria-label', '停等协议互动图');

  if (options.title !== '') T(root, options.title ?? '停等协议：一次只等一个确认', {
    x: 800, y: 72, size: 34, fill: DIM, anchor: 'middle', weight: 600,
  });

  const nodes = centers.map((x, i) => {
    const g = G(root, { x, y: nodeY });
    g.classList.add('route-node');
    g.dataset.node = String(i);
    mk('rect', { x: -nodeW / 2, y: -50, width: nodeW, height: 100, rx: 18, fill: PAPER, stroke: INK, 'stroke-width': 3 }, g);
    if (i === 0) {
      mk('path', { d: 'M-45 15H35 M20-5L42 15L20 35', fill: 'none', stroke: INK, 'stroke-width': 5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
    } else if (i === 1) {
      mk('path', { d: 'M-42 0H42 M0-22V22 M-42-22H42 M-42 22H42', fill: 'none', stroke: INK, 'stroke-width': 3, 'stroke-linecap': 'round' }, g);
    } else {
      mk('path', { d: 'M-38-22H38V22H-38Z M-38-5H38 M-15 10H15', fill: 'none', stroke: INK, 'stroke-width': 3, 'stroke-linejoin': 'round' }, g);
    }
    T(g, ['发送方', '接收方', '应用'][i], {
      x: 0, y: -69, size: 27, fill: INK, anchor: 'middle', weight: 600,
    });
    return g;
  });

  const dataStart = centers[0] + nodeW / 2 + 15;
  const receiverX = centers[1] - nodeW / 2 - 15;
  mk('line', { x1: centers[0] + nodeW / 2, y1: nodeY, x2: centers[1] - nodeW / 2, y2: nodeY, stroke: INK, 'stroke-width': 6, 'stroke-linecap': 'round' }, root);
  mk('line', { x1: centers[0] + nodeW / 2, y1: nodeY + 62, x2: centers[1] - nodeW / 2, y2: nodeY + 62, stroke: DIM, 'stroke-width': 2, 'stroke-dasharray': '8 10' }, root);
  T(root, 'DATA →', { x: 800, y: nodeY - 48, size: 24, fill: ORANGE, anchor: 'middle', weight: 700 });
  T(root, '← ACK', { x: 800, y: nodeY + 104, size: 24, fill: BLUE, anchor: 'middle', weight: 700 });
  mk('line', { x1: centers[1] + nodeW / 2, y1: nodeY, x2: centers[2] - nodeW / 2, y2: nodeY, stroke: DIM, 'stroke-width': 3, 'stroke-dasharray': '7 9', 'stroke-linecap': 'round' }, root);
  T(root, '新数据才交给应用', { x: 1080, y: nodeY - 40, size: 23, fill: DIM, anchor: 'middle' });

  const data = G(root, { x: dataStart, y: nodeY, o: 0 });
  data.classList.add('data-packet');
  mk('rect', { x: -78, y: -25, width: 156, height: 50, rx: 12, fill: ORANGE, stroke: PAPER, 'stroke-width': 2 }, data);
  const dataLabel = T(data, 'DATA 0', { x: 0, y: 8, size: 23, fill: PAPER, anchor: 'middle', font: MATH, weight: 700 });

  const ack = G(root, { x: receiverX, y: nodeY + 62, o: 0 });
  ack.classList.add('ack-packet');
  mk('rect', { x: -68, y: -23, width: 136, height: 46, rx: 11, fill: BLUE, stroke: PAPER, 'stroke-width': 2 }, ack);
  const ackLabel = T(ack, 'ACK 0', { x: 0, y: 8, size: 23, fill: PAPER, anchor: 'middle', font: MATH, weight: 700 });

  const lossMark = G(root, { x: 520, y: nodeY, o: 0 });
  mk('path', { d: 'M-14-14L14 14 M14-14L-14 14', fill: 'none', stroke: RED, 'stroke-width': 6, 'stroke-linecap': 'round' }, lossMark);
  T(lossMark, '丢失', { x: 0, y: -30, size: 23, fill: RED, anchor: 'middle', weight: 700 });

  const discardMark = G(root, { x: receiverX + 140, y: nodeY, o: 0 });
  discardMark.classList.add('discard-mark');
  mk('path', { d: 'M-14-14L14 14 M14-14L-14 14', fill: 'none', stroke: RED, 'stroke-width': 6, 'stroke-linecap': 'round' }, discardMark);
  T(discardMark, '丢弃重复', { x: 0, y: 62, size: 23, fill: RED, anchor: 'middle', weight: 700 });

  const receiverPulse = mk('circle', { cx: receiverX, cy: nodeY, r: 24, fill: 'none', stroke: ORANGE, 'stroke-width': 5, opacity: 0 }, root);
  const appPulse = mk('circle', { cx: centers[2] - nodeW / 2 - 8, cy: nodeY, r: 20, fill: 'none', stroke: BLUE, 'stroke-width': 5, opacity: 0 }, root);

  const values = [320, 640, 960, 1280].map((x, i) => T(root, '', {
    x, y: readoutY, size: 42, fill: [ORANGE, RED, BLUE, INK][i], anchor: 'middle', font: MATH, weight: 700,
  }));
  const [sendValue, duplicateValue, deliveryValue, completionValue] = values;
  ['发送次数', '重复次数', '应用交付', '完成时间'].forEach((label, i) => T(root, label, {
    x: [320, 640, 960, 1280][i], y: readoutY + 38, size: 23, fill: DIM, anchor: 'middle',
  }));

  const controls = [];
  const hits = [];
  const controlGroup = G(root);
  controlGroup.setAttribute('role', 'radiogroup');
  controlGroup.setAttribute('aria-label', '选择链路故障');
  controlGroup.style.display = showControls ? '' : 'none';
  T(controlGroup, '选择链路故障', { x: 300, y: controlY - 32, size: 25, fill: DIM, anchor: 'start', weight: 600 });
  names.forEach((name, i) => {
    const x = 300 + i * 500;
    const option = G(controlGroup, { x, y: controlY });
    option.classList.add('fault-option');
    option.setAttribute('role', 'radio');
    option.setAttribute('aria-label', name);
    option.setAttribute('aria-checked', i === v.fault ? 'true' : 'false');
    option.setAttribute('tabindex', '-1');
    const box = mk('rect', { x: -190, y: -34, width: 380, height: 68, rx: 16, fill: PAPER, stroke: DIM, 'stroke-width': 3 }, option);
    const dot = mk('circle', { cx: -145, cy: 0, r: 14, fill: i === v.fault ? ORANGE : PAPER, stroke: INK, 'stroke-width': 3 }, option);
    T(option, name, { x: 18, y: 9, size: 29, fill: INK, anchor: 'middle', weight: 600 });
    const hit = mk('rect', { class: 'fault-hit', x: -200, y: -70, width: 400, height: 140, rx: 20, fill: 'transparent', 'pointer-events': 'none' }, option);
    hit.style.touchAction = 'auto';
    hit.style.userSelect = 'none';
    hit.addEventListener('pointerdown', event => {
      if (!isLive) return;
      set(i);
      focus();
      event.preventDefault();
      event.stopPropagation();
    });
    hit.addEventListener('click', event => event.stopPropagation());
    option.addEventListener('keydown', event => {
      if (!isLive || event.shiftKey) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nudge(1);
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nudge(-1);
      else if (event.key === 'Home') set(0);
      else if (event.key === 'End') set(2);
      else if (event.key === 'Enter' && typeof P.keys === 'function') {
        event.preventDefault();
        event.stopPropagation();
        P.keys(event);
        return;
      } else return;
      focus();
      event.preventDefault();
      event.stopPropagation();
    });
    controls.push({ option, box, dot });
    hits.push(hit);
  });

  const barX = 300;
  const barW = 1000;
  T(root, '协议时间轴 0–100 ms', { x: barX, y: timelineY - 24, size: 24, fill: DIM, anchor: 'start', weight: 600 });
  mk('rect', { x: barX, y: timelineY, width: barW, height: 12, rx: 6, fill: TRACK }, root);
  for (const t of [0, 20, 40, 60, 80, 100]) {
    const x = barX + t / TOTAL_MS * barW;
    mk('line', { x1: x, y1: timelineY + 12, x2: x, y2: timelineY + 22, stroke: DIM, 'stroke-width': 2 }, root);
    T(root, String(t), { x, y: timelineY + 45, size: 20, fill: DIM, anchor: 'middle', font: MATH });
  }
  const cursor = mk('line', { x1: barX, y1: timelineY - 7, x2: barX, y2: timelineY + 20, stroke: INK, 'stroke-width': 4, 'stroke-linecap': 'round' }, root);
  const timeoutTick = mk('line', { x1: barX + 600, y1: timelineY - 10, x2: barX + 600, y2: timelineY + 15, stroke: RED, 'stroke-width': 3 }, root);

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const lerp = (a, b, q) => a + (b - a) * q;

  function pose(ms) {
    const t = clamp(Number.isFinite(ms) ? ms : 0, 0, TOTAL_MS);
    const fault = v.fault;
    const retransmit = fault !== 0 && t >= TIMEOUT_MS;
    const sends = retransmit ? 2 : 1;
    const duplicates = fault === 2 && t >= 80 ? 1 : 0;
    const deliveries = fault === 1 ? (t >= 80 ? 1 : 0) : (t >= 20 ? 1 : 0);
    const completion = fault === 0 ? (t >= 40 ? 40 : null) : (t >= 100 ? 100 : null);
    let dataX = dataStart;
    let dataOpacity = 0;
    let dataText = 'DATA 0';
    let ackX = receiverX;
    let ackOpacity = 0;
    let lossOpacity = 0;
    let discardOpacity = 0;
    let receiverOpacity = 0;
    let appOpacity = 0;
    let phase = 'waiting';

    if (fault === 0) {
      if (t < 20) {
        dataX = lerp(dataStart, receiverX, t / 20);
        dataOpacity = 1;
        phase = 'data-in-flight';
      } else if (t < 40) {
        ackX = lerp(receiverX, dataStart, (t - 20) / 20);
        ackOpacity = 1;
        receiverOpacity = 1;
        appOpacity = 1;
        phase = t < 22 ? 'data-delivered' : 'ack-in-flight';
      } else {
        phase = 'complete';
      }
    } else if (fault === 1) {
      if (t < 12) {
        dataX = lerp(dataStart, 520, t / 12);
        dataOpacity = t < 8 ? 1 : 1 - (t - 8) / 4;
        lossOpacity = t >= 8 ? 1 : 0;
        phase = t < 8 ? 'first-data-in-flight' : 'data-lost';
      } else if (t < 60) {
        lossOpacity = .45;
        phase = 'waiting-timeout';
      } else if (t < 80) {
        dataX = lerp(dataStart, receiverX, (t - 60) / 20);
        dataOpacity = 1;
        phase = 'retransmit';
      } else if (t < 100) {
        ackX = lerp(receiverX, dataStart, (t - 80) / 20);
        ackOpacity = 1;
        receiverOpacity = 1;
        appOpacity = 1;
        phase = t < 82 ? 'retransmit-delivered' : 'ack-in-flight';
      } else {
        phase = 'complete';
      }
    } else {
      if (t < 20) {
        dataX = lerp(dataStart, receiverX, t / 20);
        dataOpacity = 1;
        phase = 'data-in-flight';
      } else if (t < 34) {
        ackX = lerp(receiverX, 520, (t - 20) / 14);
        ackOpacity = t < 30 ? 1 : 1 - (t - 30) / 4;
        lossOpacity = t >= 30 ? 1 : 0;
        receiverOpacity = 1;
        appOpacity = 1;
        phase = t < 30 ? 'ack-in-flight' : 'ack-lost';
      } else if (t < 60) {
        lossOpacity = .45;
        receiverOpacity = .6;
        appOpacity = .6;
        phase = 'waiting-timeout';
      } else if (t < 80) {
        dataX = lerp(dataStart, receiverX, (t - 60) / 20);
        dataOpacity = 1;
        dataText = '重复 DATA 0';
        receiverOpacity = .6;
        appOpacity = .6;
        phase = 'duplicate-in-flight';
      } else if (t < 100) {
        dataX = receiverX;
        dataOpacity = t < 82 ? 1 : 0;
        dataText = '重复 DATA 0';
        ackX = lerp(receiverX, dataStart, (t - 80) / 20);
        ackOpacity = 1;
        discardOpacity = t >= 82 ? 1 : 0;
        receiverOpacity = 1;
        appOpacity = 1;
        phase = t < 82 ? 'duplicate-received' : 'duplicate-discarded';
      } else {
        phase = 'complete';
      }
    }

    return { sends, duplicates, deliveries, completion, dataX, dataOpacity, dataText, ackX, ackOpacity, lossOpacity, discardOpacity, receiverOpacity, appOpacity, phase };
  }

  function render(p) {
    current = p;
    put(data, { x: p.dataX, o: p.dataOpacity });
    put(ack, { x: p.ackX, o: p.ackOpacity });
    put(lossMark, { o: p.lossOpacity });
    put(discardMark, { o: p.discardOpacity });
    setOpacity(receiverPulse, p.receiverOpacity);
    setOpacity(appPulse, p.appOpacity);
    dataLabel.textContent = p.dataText;
    sendValue.textContent = String(p.sends);
    duplicateValue.textContent = String(p.duplicates);
    deliveryValue.textContent = String(p.deliveries);
    completionValue.textContent = hideTotal ? '? ms' : p.completion == null ? '— ms' : `${p.completion} ms`;
    const totalDescription = hideTotal ? '完成时间待计算' : p.completion == null ? '尚未完成' : `完成时间 ${p.completion} 毫秒`;
    root.setAttribute('aria-label', `停等协议，${names[v.fault]}：${p.sends} 次发送，${p.duplicates} 次重复，${p.deliveries} 次应用交付，${totalDescription}`);
    root.dataset.phase = p.phase;
    setAttr(cursor, 'x1', barX + (currentTime / TOTAL_MS) * barW);
    setAttr(cursor, 'x2', barX + (currentTime / TOTAL_MS) * barW);
    setAttr(timeoutTick, 'opacity', v.fault === 0 ? '.25' : '1');
    controls.forEach(({ option, box, dot }, i) => {
      option.setAttribute('aria-checked', i === v.fault ? 'true' : 'false');
      box.setAttribute('stroke', i === v.fault ? ORANGE : DIM);
      box.setAttribute('stroke-width', i === v.fault ? '5' : '3');
      dot.setAttribute('fill', i === v.fault ? ORANGE : PAPER);
    });
  }

  let currentTime = 0;
  function at(ms) {
    currentTime = clamp(Number.isFinite(ms) ? ms : 0, 0, TOTAL_MS);
    render(pose(currentTime));
    return current;
  }

  function set(values) {
    const fault = typeof values === 'number' ? values : values?.fault;
    if (!Number.isFinite(fault)) return;
    v.fault = clamp(Math.round(fault), 0, 2);
    at(TOTAL_MS);
    for (const listener of listeners) listener(v.fault);
  }

  function live(on) {
    isLive = !!on;
    root.classList.toggle('is-live', isLive);
    document.getElementById('stage').setAttribute('role', isLive ? 'group' : 'img');
    controls.forEach(({ option }, i) => {
      option.setAttribute('tabindex', isLive && i === v.fault ? '0' : '-1');
      option.setAttribute('aria-disabled', isLive ? 'false' : 'true');
    });
    hits.forEach(hit => {
      hit.setAttribute('pointer-events', isLive ? 'all' : 'none');
      hit.style.touchAction = isLive ? 'none' : 'auto';
      hit.style.cursor = isLive ? 'pointer' : 'default';
    });
  }

  function focus() {
    if (isLive) controls[v.fault]?.option.focus({ preventScroll: true });
  }

  function nudge(delta) { set(clamp(v.fault + delta, 0, 2)); }
  function phase(value) { if (typeof value === 'string' && value) root.dataset.phase = value; }
  function onChange(listener) { listeners.add(listener); return () => listeners.delete(listener); }
  function setAttr(e, name, value) { const s = String(value); if (e.getAttribute(name) !== s) e.setAttribute(name, s); }
  function setOpacity(e, value) { const o = value.toFixed(2); if (e.getAttribute('opacity') !== o) e.setAttribute('opacity', o); }

  at(TOTAL_MS);
  live(false);

  return {
    v, el: root, data, ack, sendValue, duplicateValue, deliveryValue, completionValue,
    controls: controls.map(c => c.option), hits, pose, at, set, live, nudge, focus, onChange, phase,
    get completion() { return current?.completion ?? null; },
  };
}
