/* Minimal Konva image + rectangles (normalized 0-1) */
function getCsrf() {
  const m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}
function setStatus(t) {
  const el = document.getElementById('label-status');
  if (el) el.textContent = t;
}
function initAnnotator(imageUrl, schema, draft, taskId, apiBase) {
  if (!window.Konva) { setStatus('Konva not loaded'); return; }
  const stage = new Konva.Stage({ container: 'label-stage', width: 800, height: 600 });
  const layer = new Konva.Layer();
  stage.add(layer);
  const img = new window.Image();
  img.crossOrigin = 'anonymous';
  const bg = new Konva.Image({ image: img });
  const tr = new Konva.Transformer();
  let rects = [];
  function normRect(node) {
    const iw = img.naturalWidth || 1, ih = img.naturalHeight || 1;
    const s = node.scaleX();
    return {
      type: 'rect',
      label_id: (schema.labels && schema.labels[0] && schema.labels[0].id) || 'obj',
      x: node.x() / iw, y: node.y() / ih,
      width: (node.width() * s) / iw, height: (node.height() * s) / ih,
    };
  }
  function snapshot() { return rects.map((r) => normRect(r)); }
  const saveDraft = window.debounceDraft(function (result) {
    fetch(apiBase + '/api/v1/tasks/' + taskId + '/draft/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      credentials: 'same-origin',
      body: JSON.stringify({ result, lead_time: 0 })
    }).then(() => setStatus('Draft saved'));
  }, 2000);
  img.onload = function () {
    const w = 800, h = Math.min(600, 800 * img.naturalHeight / img.naturalWidth);
    stage.width(w); stage.height(h);
    bg.width(w); bg.height(h);
    bg.image(img);
    layer.add(bg);
    layer.add(tr);
    layer.draw();
  };
  img.src = imageUrl;
  function addRect() {
    const r = new Konva.Rect({ x: 20, y: 20, width: 120, height: 100, fill: 'rgba(231,76,60,0.2)', stroke: '#e74c3c' });
    layer.add(r);
    rects.push(r);
    tr.nodes([r]);
    saveDraft(snapshot());
  }
  document.getElementById('btn-add-rect') && document.getElementById('btn-add-rect').addEventListener('click', addRect);
  document.getElementById('btn-submit') && document.getElementById('btn-submit').addEventListener('click', function () {
    fetch(apiBase + '/api/v1/tasks/' + taskId + '/annotations/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      credentials: 'same-origin',
      body: JSON.stringify({ result: snapshot() })
    }).then((r) => { if (r.ok) { window.location.href = document.getElementById('next-url').value; } });
  });
  if (Array.isArray(draft) && draft.length) { /* restore simplified */ }
  setStatus('Ready');
  return { addRect, snapshot };
}
