/* Default hotkeys: 1-9 class, V select, B rect, P poly, O point, Ctrl+Z undo */
(function (global) {
  const defaultKeys = { select: 'v', rect: 'b', poly: 'p', point: 'o', classPrefix: 'Digit' };
  function Hotkeys(opts) { this.o = Object.assign({}, defaultKeys, opts || {}); }
  Hotkeys.prototype.onKey = function (e, handlers) {
    const k = e.key.toLowerCase();
    if (e.ctrlKey && k === 'z') { e.preventDefault(); handlers.undo && handlers.undo(); return; }
    if (k === this.o.select) { handlers.select && handlers.select(); return; }
    if (k === this.o.rect) { handlers.rect && handlers.rect(); return; }
    if (k === this.o.poly) { handlers.poly && handlers.poly(); return; }
    if (k === this.o.point) { handlers.point && handlers.point(); return; }
    if (e.code && e.code.indexOf('Digit') === 0) {
      const n = parseInt(e.code.replace('Digit', ''), 10);
      if (n >= 1 && n <= 9) handlers.classIndex && handlers.classIndex(n);
    }
  };
  global.Hotkeys = Hotkeys;
})(window);
