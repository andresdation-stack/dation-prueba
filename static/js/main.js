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

