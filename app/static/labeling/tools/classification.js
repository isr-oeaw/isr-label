window.LClassifyTool = {
  type: 'choices',
  fromSelected(labelId, selectedKeys) {
    return { type: 'choices', label_id: labelId, selected: selectedKeys || [] };
  }
};
