window.LPointTool = {
  type: 'point',
  fromXY(nx, ny, labelId) {
    return { type: 'point', label_id: labelId, x: nx, y: ny };
  }
};
