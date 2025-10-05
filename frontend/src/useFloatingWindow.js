export async function openFloating(suggestions = []) {
  if (!('documentPictureInPicture' in window)) {
    alert('Document Picture-in-Picture is not supported in this browser.');
    return;
  }

  // Fenster öffnen
  const pipWin = await documentPictureInPicture.requestWindow({ width: 360, height: 240 });

  // Styles + HTML im Fenster
  const doc = pipWin.document;
  doc.body.style.margin = '0';
  doc.body.style.fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
  doc.body.style.background = '#f5f5f7';
  doc.body.innerHTML = `
    <style>
      .wrap{height:100vh;display:flex;align-items:center;justify-content:center;padding:12px;}
      .stack{display:flex;flex-direction:column;gap:10px;width:100%;}
      .chip{border:1px solid #d2d2d7;background:#fff;border-radius:14px;padding:12px 14px;
            text-align:center;cursor:pointer;font-size:14px}
      .chip:hover{border-color:#007aff;box-shadow:0 4px 10px rgba(0,0,0,.1)}
      h3{margin:0 0 8px 0;text-align:center;font-size:16px}
    </style>
    <div class="wrap">
      <div style="width:100%">
        <h3>Live Reply</h3>
        <div class="stack" id="stack"></div>
      </div>
    </div>
  `;

  // Vorschläge rendern
  const stack = doc.getElementById('stack');
  suggestions.forEach(t => {
    const b = doc.createElement('button');
    b.className = 'chip';
    b.textContent = t;
    b.onclick = () => console.log('Picked:', t); // später Clipboard/WS etc.
    stack.appendChild(b);
  });

  // Wenn Fenster geschlossen wird
  pipWin.addEventListener('unload', () => console.log('Floating window closed'));
}
