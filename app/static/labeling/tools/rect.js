/* Rectangle tool — normalized coords, Konva layer integration hooks */
window.LRectTool = {
  type: 'rect',
  fromKonvaNode(node, imageWidth, imageHeight, labelId) {
    const s = node.scaleX();
    const w = (node.width() * s) / imageWidth, h = (node.height() * s) / imageHeight;
    return { type: 'rect', label_id: labelId, x: node.x() / imageWidth, y: node.y() / imageHeight, width: w, height: h };
  }
};
