/* Konva image + rectangles (normalized 0–1 relative to letterboxed image) */
function getCsrf() {
  const m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}
function setStatus(t) {
  const el = document.getElementById('label-status');
  if (el) el.textContent = t;
}

function _hexToRgb(hex) {
  const s = (hex || '').replace('#', '');
  if (s.length === 3) {
    return [
      parseInt(s[0] + s[0], 16),
      parseInt(s[1] + s[1], 16),
      parseInt(s[2] + s[2], 16),
    ];
  }
  if (s.length === 6) {
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
  }
  return [231, 76, 60];
}

function _styleRectFromLabel(rect, schema, labelId) {
  const labels = (schema && schema.labels) || [];
  let color = '#e74c3c';
  for (let i = 0; i < labels.length; i++) {
    if (String(labels[i].id) === String(labelId) && labels[i].color) {
      color = labels[i].color;
      break;
    }
  }
  const [r, g, b] = _hexToRgb(color);
  rect.stroke(color);
  rect.fill('rgba(' + r + ',' + g + ',' + b + ',0.2)');
}

function initAnnotator(imageUrl, schema, draft, taskId, apiBase) {
  if (!window.Konva) {
    setStatus('Konva not loaded');
    return;
  }
  const wrap = document.getElementById('label-stage-wrapper');
  if (!wrap || !document.getElementById('label-stage')) {
    setStatus('Stage missing');
    return;
  }

  const stage = new Konva.Stage({ container: 'label-stage', width: 1, height: 1 });
  const layer = new Konva.Layer();
  stage.add(layer);
  const img = new window.Image();
  img.crossOrigin = 'anonymous';
  const bg = new Konva.Image({ image: img });
  const tr = new Konva.Transformer({
    rotateEnabled: false,
    enabledAnchors: ['top-left', 'top-right', 'bottom-left', 'bottom-right'],
  });
  let rects = [];
  let imageReady = false;

  function getActiveLabelId() {
    const btn = document.querySelector('.labeling-sidebar-label.active');
    if (btn && btn.getAttribute('data-label-id')) return btn.getAttribute('data-label-id');
    const first = (schema.labels && schema.labels[0] && schema.labels[0].id) || 'obj';
    return String(first);
  }

  function bindLabelButtons() {
    document.querySelectorAll('.labeling-sidebar-label').forEach((b) => {
      b.addEventListener('click', function () {
        document.querySelectorAll('.labeling-sidebar-label').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        const sel = tr.nodes()[0];
        if (sel && sel.getClassName && sel.getClassName() === 'Rect') {
          sel.setAttr('labelId', getActiveLabelId());
          _styleRectFromLabel(sel, schema, getActiveLabelId());
          layer.batchDraw();
          saveDraft(snapshot());
        }
      });
    });
  }

  function normRect(node) {
    const bx = bg.x();
    const by = bg.y();
    const bw = bg.width() || 1;
    const bh = bg.height() || 1;
    const s = node.scaleX();
    return {
      type: 'rect',
      label_id: node.getAttr('labelId') || getActiveLabelId(),
      x: (node.x() - bx) / bw,
      y: (node.y() - by) / bh,
      width: (node.width() * s) / bw,
      height: (node.height() * node.scaleY()) / bh,
    };
  }

  function denormRect(node, n) {
    const bx = bg.x();
    const by = bg.y();
    const bw = bg.width() || 1;
    const bh = bg.height() || 1;
    node.x(bx + n.x * bw);
    node.y(by + n.y * bh);
    node.width(Math.max(4, n.width * bw));
    node.height(Math.max(4, n.height * bh));
    node.scaleX(1);
    node.scaleY(1);
    if (n.label_id) node.setAttr('labelId', n.label_id);
    _styleRectFromLabel(node, schema, node.getAttr('labelId'));
  }

  function snapshot() {
    return rects.map((r) => normRect(r));
  }

  const saveDraft = window.debounceDraft
    ? window.debounceDraft(function (result) {
        fetch(apiBase + '/api/v1/tasks/' + taskId + '/draft/', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
          credentials: 'same-origin',
          body: JSON.stringify({ result, lead_time: 0 }),
        }).then(() => setStatus('Draft saved'));
      }, 2000)
    : function () {};

  bindLabelButtons();

  function layoutImage() {
    const cw = wrap.clientWidth || 1;
    const ch = wrap.clientHeight || 1;
    stage.width(cw);
    stage.height(ch);

    const nw = img.naturalWidth || 0;
    const nh = img.naturalHeight || 0;
    if (!nw || !nh) {
      layer.batchDraw();
      return;
    }

    const prev = rects.map((r) => normRect(r));

    const scale = Math.min(cw / nw, ch / nh);
    const dw = nw * scale;
    const dh = nh * scale;
    const ox = (cw - dw) / 2;
    const oy = (ch - dh) / 2;
    bg.image(img);
    bg.x(ox);
    bg.y(oy);
    bg.width(dw);
    bg.height(dh);

    rects.forEach((r, i) => {
      if (prev[i]) denormRect(r, prev[i]);
    });

    bg.moveToBottom();
    tr.moveToTop();

    layer.batchDraw();
  }

  function requestLayout() {
    if (!imageReady) return;
    layoutImage();
  }

  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => requestLayout()) : null;
  if (ro) ro.observe(wrap);
  window.addEventListener('resize', requestLayout);

  function attachRectHandlers(r) {
    r.on('dragend transformend', () => saveDraft(snapshot()));
    r.on('click tap', () => {
      tr.nodes([r]);
      tr.moveToTop();
      layer.batchDraw();
    });
  }

  /** Stage/container pixels (handles letterboxing vs. canvas CSS size). */
  function clientToStage(clientX, clientY) {
    const rect = stage.container().getBoundingClientRect();
    const scaleX = stage.width() / rect.width;
    const scaleY = stage.height() / rect.height;
    return { x: (clientX - rect.left) * scaleX, y: (clientY - rect.top) * scaleY };
  }

  let drawingNewRect = null;
  let drawAnchor = null;

  function teardownDrawListeners() {
    window.removeEventListener('mousemove', onWindowDrawMove);
    window.removeEventListener('mouseup', onWindowDrawUp);
    window.removeEventListener('touchmove', onWindowDrawMove);
    window.removeEventListener('touchend', onWindowDrawUp);
    window.removeEventListener('touchcancel', onWindowDrawUp);
  }

  function onWindowDrawMove(e) {
    if (!drawingNewRect || !drawAnchor) return;
    let cx;
    let cy;
    if (e.touches && e.touches.length) {
      cx = e.touches[0].clientX;
      cy = e.touches[0].clientY;
      if (e.cancelable) e.preventDefault();
    } else {
      cx = e.clientX;
      cy = e.clientY;
    }
    const pos = clientToStage(cx, cy);
    const x = Math.min(drawAnchor.x, pos.x);
    const y = Math.min(drawAnchor.y, pos.y);
    const w = Math.abs(pos.x - drawAnchor.x);
    const h = Math.abs(pos.y - drawAnchor.y);
    drawingNewRect.setAttrs({ x, y, width: w, height: h });
    drawingNewRect.moveToTop();
    tr.moveToTop();
    layer.batchDraw();
  }

  function clampRectToImage(r) {
    const bx = bg.x();
    const by = bg.y();
    const bw = bg.width();
    const bh = bg.height();
    let x1 = r.x();
    let y1 = r.y();
    let x2 = x1 + r.width();
    let y2 = y1 + r.height();
    x1 = Math.max(bx, Math.min(x1, bx + bw));
    x2 = Math.max(bx, Math.min(x2, bx + bw));
    y1 = Math.max(by, Math.min(y1, by + bh));
    y2 = Math.max(by, Math.min(y2, by + bh));
    r.setAttrs({
      x: x1,
      y: y1,
      width: Math.max(1, x2 - x1),
      height: Math.max(1, y2 - y1),
    });
  }

  function finalizeDraw() {
    teardownDrawListeners();
    if (!drawingNewRect) {
      drawAnchor = null;
      return;
    }
    const r = drawingNewRect;
    drawingNewRect = null;
    drawAnchor = null;
    clampRectToImage(r);
    const w = r.width();
    const h = r.height();
    if (w < 4 || h < 4) {
      r.destroy();
      layer.batchDraw();
      return;
    }
    r.draggable(true);
    attachRectHandlers(r);
    rects.push(r);
    tr.nodes([r]);
    tr.moveToTop();
    saveDraft(snapshot());
    layer.batchDraw();
  }

  function onWindowDrawUp() {
    finalizeDraw();
  }

  function startDrawOnImage(e) {
    if (drawingNewRect) return;
    if (e.evt && typeof e.evt.button === 'number' && e.evt.button > 0) return;
    if (!imageReady || e.target !== bg) return;

    tr.nodes([]);
    layer.batchDraw();

    const pos = stage.getPointerPosition();
    if (!pos) return;

    const lid = getActiveLabelId();
    drawingNewRect = new Konva.Rect({
      x: pos.x,
      y: pos.y,
      width: 0,
      height: 0,
      strokeWidth: 2,
      draggable: false,
    });
    drawingNewRect.setAttr('labelId', lid);
    _styleRectFromLabel(drawingNewRect, schema, lid);
    layer.add(drawingNewRect);
    drawAnchor = { x: pos.x, y: pos.y };
    drawingNewRect.moveToTop();
    tr.moveToTop();

    window.addEventListener('mousemove', onWindowDrawMove);
    window.addEventListener('mouseup', onWindowDrawUp);
    window.addEventListener('touchmove', onWindowDrawMove, { passive: false });
    window.addEventListener('touchend', onWindowDrawUp);
    window.addEventListener('touchcancel', onWindowDrawUp);
    layer.batchDraw();
  }

  stage.on('mousedown touchstart', startDrawOnImage);

  function addRect() {
    if (!imageReady) return;
    const bx = bg.x();
    const by = bg.y();
    const bw = bg.width();
    const bh = bg.height();
    const lid = getActiveLabelId();
    const r = new Konva.Rect({
      x: bx + bw * 0.1,
      y: by + bh * 0.1,
      width: Math.max(32, bw * 0.15),
      height: Math.max(32, bh * 0.15),
      fill: 'rgba(231,76,60,0.2)',
      stroke: '#e74c3c',
      strokeWidth: 2,
      draggable: true,
    });
    r.setAttr('labelId', lid);
    _styleRectFromLabel(r, schema, lid);
    layer.add(r);
    rects.push(r);
    tr.nodes([r]);
    attachRectHandlers(r);
    saveDraft(snapshot());
    tr.moveToTop();
    layer.batchDraw();
  }

  const addBtn = document.getElementById('btn-add-rect');
  if (addBtn) addBtn.addEventListener('click', addRect);

  document.getElementById('btn-submit') &&
    document.getElementById('btn-submit').addEventListener('click', function () {
      fetch(apiBase + '/api/v1/tasks/' + taskId + '/annotations/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        credentials: 'same-origin',
        body: JSON.stringify({ result: snapshot() }),
      }).then((r) => {
        if (r.ok) window.location.href = document.getElementById('next-url').value;
      });
    });

  tr.on('transformend', () => {
    const n = tr.nodes()[0];
    if (n) saveDraft(snapshot());
  });

  let bgAdded = false;
  img.onload = function () {
    imageReady = true;
    if (!bgAdded) {
      layer.add(bg);
      layer.add(tr);
      bgAdded = true;
    }
    layoutImage();
    if (Array.isArray(draft) && draft.length) {
      draft.forEach((item) => {
        if (item && item.type === 'rect') {
          const r = new Konva.Rect({
            fill: 'rgba(231,76,60,0.2)',
            stroke: '#e74c3c',
            strokeWidth: 2,
            draggable: true,
          });
          r.setAttr('labelId', item.label_id || getActiveLabelId());
          denormRect(r, {
            x: item.x,
            y: item.y,
            width: item.width,
            height: item.height,
            label_id: item.label_id,
          });
          layer.add(r);
          rects.push(r);
          attachRectHandlers(r);
        }
      });
      layoutImage();
      tr.moveToTop();
      tr.nodes([]);
    }
    setStatus('Ready');
  };
  img.onerror = function () {
    setStatus('Image failed to load');
  };
  img.src = imageUrl;

  function selectLabelIndex(idx) {
    const buttons = Array.from(document.querySelectorAll('.labeling-sidebar-label'));
    if (idx < 0 || idx >= buttons.length) return;
    buttons.forEach((x) => x.classList.remove('active'));
    buttons[idx].classList.add('active');
    const sel = tr.nodes()[0];
    if (sel && sel.getClassName && sel.getClassName() === 'Rect') {
      sel.setAttr('labelId', getActiveLabelId());
      _styleRectFromLabel(sel, schema, getActiveLabelId());
      layer.batchDraw();
      saveDraft(snapshot());
    }
  }

  document.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable))
      return;
    const k = e.key;
    if (k === 'Delete' || k === 'Backspace') {
      if (drawingNewRect) {
        e.preventDefault();
        teardownDrawListeners();
        drawingNewRect.destroy();
        drawingNewRect = null;
        drawAnchor = null;
        layer.batchDraw();
        return;
      }
      const sel = tr.nodes()[0];
      if (sel && sel.getClassName && sel.getClassName() === 'Rect') {
        e.preventDefault();
        tr.nodes([]);
        const idx = rects.indexOf(sel);
        if (idx >= 0) rects.splice(idx, 1);
        sel.destroy();
        saveDraft(snapshot());
        layer.batchDraw();
      }
      return;
    }
    if (k >= '1' && k <= '9') {
      selectLabelIndex(parseInt(k, 10) - 1);
    }
  });

  return { addRect, snapshot };
}
