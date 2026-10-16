export function chatMenuPosition(rect,viewport,desiredHeight=250) {
  const margin=8;
  const width=Math.max(0,Math.min(145,viewport.width-2*margin));
  const above=Math.max(0,rect.top-2*margin);
  const below=Math.max(0,viewport.height-rect.bottom-2*margin);
  const down=below>=Math.min(desiredHeight,above);
  const height=Math.max(0,Math.min(desiredHeight,down?below:above,viewport.height-2*margin));
  return {position:'fixed',width,maxHeight:height,
    left:Math.max(margin,Math.min(rect.right-width,viewport.width-width-margin)),
    top:Math.max(margin,Math.min(down?rect.bottom+margin:rect.top-margin-height,viewport.height-height-margin))};
}
