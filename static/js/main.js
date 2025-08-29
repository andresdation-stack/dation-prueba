async function load() {
  try {
    const r = await fetch('/api/latest');
    const j = await r.json();
    const elValue = document.getElementById('value');
    const elDevice = document.getElementById('device');
    const elTime = document.getElementById('time');
    if (elValue) elValue.textContent = (j.value ?? '');
    if (elDevice) elDevice.textContent = j.device_id ? ('Dispositivo: ' + j.device_id) : '';
    if (elTime) elTime.textContent = j.ts ? ('Actualizado: ' + new Date(j.ts * 1000).toLocaleString()) : '';
  } catch (e) {
    console.error(e);
  }
}

load();
setInterval(load, 2000);

// Normalize any <img> or <video> sources that accidentally use
// Windows-style backslashes or lack leading slash.
function fixAssetPaths() {
  const sel = 'img[src^="assets\\\\"], source[src^="assets\\\\"], video[src^="assets\\\\"], img[src^="assets/"], source[src^="assets/"], video[src^="assets/"]';
  document.querySelectorAll(sel).forEach(el => {
    const attr = el.tagName.toLowerCase() === 'source' ? 'src' : 'src';
    let val = el.getAttribute(attr);
    if (!val) return;
    // Replace backslashes with forward slashes
    val = val.replace(/\\\\/g, '/');
    // Ensure it starts with a leading slash
    if (!val.startsWith('/')) val = '/' + val;
    el.setAttribute(attr, val);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', fixAssetPaths);
} else {
  fixAssetPaths();
}
