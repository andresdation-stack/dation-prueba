async function load() {
  try {
    const r = await fetch('/api/latest');
    const j = await r.json();
    document.getElementById('value').textContent = (j.value ?? '—');
    document.getElementById('device').textContent = j.device_id ? ('Dispositivo: ' + j.device_id) : '—';
    document.getElementById('time').textContent = j.ts ? ('Actualizado: ' + new Date(j.ts * 1000).toLocaleString()) : '—';
  } catch (e) {
    console.error(e);
  }
}

load();
setInterval(load, 2000);

