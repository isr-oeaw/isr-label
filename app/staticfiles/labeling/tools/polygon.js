/* Polygon tool — list of [x,y] in 0-1 */
window.LPolyTool = {
  type: 'polygon',
  fromPoints(pts, labelId) {
    return { type: 'polygon', label_id: labelId, points: pts };
  }
};
