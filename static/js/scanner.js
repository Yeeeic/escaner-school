(() => {
  const video = document.getElementById('camera-video');
  const canvas = document.getElementById('capture-canvas');
  const cameraSelect = document.getElementById('camera-select');
  const cameraStatus = document.getElementById('camera-status');
  const shell = document.getElementById('video-shell');
  const scanMessage = document.getElementById('scan-message');
  const flash = document.getElementById('result-flash');
  const placeholder = document.getElementById('credential-placeholder');
  const digitalId = document.getElementById('digital-id');
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let stream = null;
  let detector = null;
  let scanning = true;
  let processing = false;
  let lastFrameSent = 0;
  let resetTimer = null;

  const $ = id => document.getElementById(id);
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

  function updateClock() {
    const now = new Date();
    $('live-clock').textContent = now.toLocaleTimeString('es-MX', { hour12: false });
    $('live-date').textContent = now.toLocaleDateString('es-MX', { day: '2-digit', month: 'long', year: 'numeric' }).toUpperCase();
  }
  updateClock(); setInterval(updateClock, 1000);

  async function listCameras() {
    try {
      const devices = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === 'videoinput');
      cameraSelect.innerHTML = devices.map((device, index) => `<option value="${escapeHtml(device.deviceId)}">${escapeHtml(device.label || `Cámara ${index}`)}</option>`).join('');
      return devices;
    } catch (_) { return []; }
  }

  async function startCamera(deviceId = '') {
    if (!navigator.mediaDevices?.getUserMedia) return cameraFailed('CÁMARA NO DISPONIBLE');
    stream?.getTracks().forEach(track => track.stop());
    const preferredId = deviceId || localStorage.getItem('sauCameraId') || '';
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: preferredId ? { exact: preferredId } : undefined, facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      video.srcObject = stream;
      await video.play();
      const devices = await listCameras();
      const currentId = stream.getVideoTracks()[0]?.getSettings()?.deviceId;
      if (currentId) { cameraSelect.value = currentId; localStorage.setItem('sauCameraId', currentId); }
      cameraStatus.className = 'system-status online'; cameraStatus.innerHTML = '<i></i> CÁMARA CONECTADA';
      stream.getVideoTracks()[0]?.addEventListener('ended', () => { cameraFailed('CÁMARA DESCONECTADA'); setTimeout(() => startCamera(cameraSelect.value), 2500); });
      scanLoop();
    } catch (error) {
      if (preferredId && error.name === 'OverconstrainedError') { localStorage.removeItem('sauCameraId'); return startCamera(''); }
      cameraFailed(error.name === 'NotAllowedError' ? 'PERMISO DE CÁMARA DENEGADO' : 'CÁMARA DESCONECTADA');
      showToast('Permite el acceso a la cámara. En Windows verifica que ninguna otra aplicación la esté usando.');
      setTimeout(() => startCamera(deviceId), 5000);
    }
  }

  function cameraFailed(message) { cameraStatus.className = 'system-status offline'; cameraStatus.innerHTML = `<i></i> ${message}`; }
  cameraSelect.addEventListener('change', () => startCamera(cameraSelect.value));
  $('fullscreen-button').addEventListener('click', async () => { if (!document.fullscreenElement) await document.documentElement.requestFullscreen(); else await document.exitFullscreen(); });

  async function setupDetector() {
    if ('BarcodeDetector' in window) {
      try { const formats = await BarcodeDetector.getSupportedFormats(); if (formats.includes('qr_code')) detector = new BarcodeDetector({ formats: ['qr_code'] }); } catch (_) { detector = null; }
    }
  }

  async function scanLoop(timestamp = 0) {
    if (!scanning || video.readyState < 2) { requestAnimationFrame(scanLoop); return; }
    try {
      if (detector && !processing) {
        const codes = await detector.detect(video);
        if (codes[0]?.rawValue) await submitQr(codes[0].rawValue);
      } else if (!detector && !processing && timestamp - lastFrameSent > 550) {
        lastFrameSent = timestamp; await decodeOnServer();
      }
    } catch (_) { /* Un fotograma fallido no interrumpe la cámara. */ }
    requestAnimationFrame(scanLoop);
  }

  async function decodeOnServer() {
    if (!video.videoWidth) return;
    const maxWidth = 800, scale = Math.min(1, maxWidth / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .72));
    if (!blob) return;
    const form = new FormData(); form.append('frame', blob, 'frame.jpg');
    const response = await fetch('/api/access/decode-frame', { method: 'POST', headers: { 'X-CSRF-Token': csrf }, body: form });
    if (response.ok) { const result = await response.json(); if (result.detected) await submitQr(result.qr_data); }
  }

  async function submitQr(qrData) {
    if (processing) return;
    processing = true; setScanState('VERIFICANDO CREDENCIAL', 'VALIDANDO FIRMA DIGITAL'); shell.classList.add('verifying');
    try {
      const response = await fetch('/api/access/scan', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ qr_data: qrData }) });
      if (!response.ok) throw new Error('No fue posible validar la credencial');
      showResult(await response.json());
    } catch (error) { showToast(error.message); setScanState('ERROR DE CONEXIÓN', 'INTENTA NUEVAMENTE'); }
    finally { shell.classList.remove('verifying'); setTimeout(() => { processing = false; }, 1100); }
  }

  function setScanState(title, subtitle) { scanMessage.querySelector('strong').textContent = title; scanMessage.querySelector('small').textContent = subtitle; }
  function showResult(result) {
    const accepted = result.authorized;
    shell.classList.toggle('accepted', accepted); shell.classList.toggle('rejected', !accepted);
    flash.className = `result-flash show ${accepted ? 'success' : 'failure'}`;
    flash.querySelector('i').className = accepted ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark';
    flash.querySelector('strong').textContent = accepted ? 'ACCESO AUTORIZADO' : 'ACCESO DENEGADO'; flash.querySelector('span').textContent = result.reason;
    setScanState(accepted ? 'ACCESO AUTORIZADO' : 'ACCESO DENEGADO', result.reason);
    beep(accepted);
    if (result.student) fillCredential(result);
    if (!result.duplicate) { refreshStats(); refreshRecent(); }
    clearTimeout(resetTimer); resetTimer = setTimeout(resetInterface, 5000);
  }

  function fillCredential(result) {
    const student = result.student; placeholder.hidden = true; digitalId.hidden = false;
    digitalId.className = `digital-id visible ${result.authorized ? 'authorized' : 'denied'}`;
    $('id-photo').src = student.photo; $('id-name').textContent = student.name; $('id-matricula').textContent = student.matricula;
    $('id-person-type').textContent = student.type_label || 'ESTUDIANTE';
    $('id-career').textContent = student.career; $('id-campus').textContent = student.campus; $('id-shift').textContent = student.shift;
    $('id-expires').textContent = new Date(`${student.expires}T12:00:00`).toLocaleDateString('es-MX');
    $('id-state').textContent = student.active ? 'VIGENTE' : 'INACTIVA'; $('id-access-label').textContent = result.authorized ? 'ACCESO AUTORIZADO' : 'ACCESO DENEGADO';
    $('id-movement').textContent = result.movement ? `${result.movement} ${result.duplicate ? 'YA REGISTRADA' : 'REGISTRADA'}` : result.reason;
    $('id-date').textContent = result.date; $('id-time').textContent = result.time;
    $('id-result').querySelector('i').className = result.authorized ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark';
  }

  function resetInterface() { shell.classList.remove('accepted','rejected'); flash.className = 'result-flash'; digitalId.hidden = true; digitalId.className = 'digital-id'; placeholder.hidden = false; setScanState('ESPERANDO CREDENCIAL', 'COLOCA EL QR FRENTE A LA CÁMARA'); }
  function beep(success) { try { const audio = new (window.AudioContext || window.webkitAudioContext)(); const oscillator = audio.createOscillator(); const gain = audio.createGain(); oscillator.frequency.value = success ? 880 : 180; oscillator.type = success ? 'sine' : 'sawtooth'; gain.gain.setValueAtTime(.12, audio.currentTime); gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + (success ? .18 : .42)); oscillator.connect(gain).connect(audio.destination); oscillator.start(); oscillator.stop(audio.currentTime + (success ? .18 : .42)); } catch (_) {} }
  function showToast(message) { const toast = $('scanner-toast'); toast.textContent = message; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 4000); }

  async function refreshStats() { try { const r = await fetch('/api/stats/today'); if (!r.ok) return; const s = await r.json(); $('scanner-inside').textContent = s.inside; $('scanner-entries').textContent = s.entries; $('scanner-exits').textContent = s.exits; $('scanner-denied').textContent = s.denied; const dayStatus = $('day-operation-status'); const open = s.day_status === 'ABIERTA'; dayStatus.className = `system-status ${open ? 'online' : 'offline'}`; dayStatus.innerHTML = `<i></i> JORNADA ${s.day_status}`; if (!open && !processing) setScanState('JORNADA CERRADA', 'SOLICITA APERTURA AL ADMINISTRADOR'); } catch (_) {} }
  async function refreshRecent() { try { const r = await fetch('/api/access/recent?limit=5'); if (!r.ok) return; const rows = await r.json(); $('recent-list').innerHTML = rows.length ? rows.map(row => `<div class="recent-row"><span class="recent-dot ${row.result.toLowerCase()}"></span><div><strong>${escapeHtml(row.student)}</strong><small>${escapeHtml(row.movement || row.reason)}</small></div><time>${row.time}</time></div>`).join('') : '<div class="recent-empty">Sin movimientos recientes</div>'; } catch (_) {} }

  document.addEventListener('visibilitychange', () => { scanning = !document.hidden; if (scanning) scanLoop(); });
  setupDetector().then(() => startCamera()); refreshStats(); refreshRecent(); setInterval(refreshStats, 15000); setInterval(refreshRecent, 15000);
})();
