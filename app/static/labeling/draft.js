(function (global) {
  function createDebouncedDraft(saveFn, delayMs) {
    let t = null;
    return function (payload) {
      clearTimeout(t);
      t = setTimeout(function () { saveFn(payload); }, delayMs || 2000);
    };
  }
  global.debounceDraft = createDebouncedDraft;
})(window);
