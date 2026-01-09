const statusEl = document.getElementById('status');
const termEl = document.getElementById('terminal');
const cmdInput = document.getElementById('cmdInput');
const sendBtn = document.getElementById('sendBtn');
const cancelBtn = document.getElementById('cancelBtn');
const cmdForm = document.getElementById('cmdForm');

let currentJobId = null;
let pollInterval = null;

async function checkHealth() {
  try {
    const r = await fetch('/health');
    if (!r.ok) throw new Error('no ok');
    const j = await r.json();
    statusEl.textContent = `Estado: ${j.status} — ${j.system}`;
    statusEl.classList.remove('status-error');
    statusEl.classList.add('status-ok');
  } catch (e) {
    statusEl.textContent = 'Estado: desconectado';
    statusEl.classList.remove('status-ok');
    statusEl.classList.add('status-error');
  }
}

function appendLine(text, cls) {
  const el = document.createElement('div');
  el.textContent = text;
  if (cls) el.classList.add(cls);
  termEl.appendChild(el);
  termEl.scrollTop = termEl.scrollHeight;
}

async function stopJob() {
  if (!currentJobId) return;
  try {
    appendLine(`[Solicitando cancelación...]`, 'meta');
    await fetch(`/stop/${currentJobId}`, { method: 'POST' });
  } catch (e) {
    appendLine(`Error al cancelar: ${e.message}`, 'stderr');
  }
}

async function pollJob(jobId) {
  try {
    const res = await fetch(`/status/${jobId}`);
    const j = await res.json();
    
    // Limpiar terminal y re-pintar todo (simple pero efectivo para logs pequeños)
    // Para logs grandes, deberíamos llevar un cursor.
    // Aquí, para simplificar, borramos el contenido previo DEL COMANDO ACTUAL si quisiéramos ser perfectos,
    // pero como appendLine añade al final, vamos a hacer un truco:
    // NO borramos, sino que asumimos que el usuario quiere ver el progreso.
    // PERO: nuestra API devuelve TODO el stdout acumulado.
    // Así que tenemos que calcular el delta o simplemente reemplazar el último bloque.
    
    // MEJOR ESTRATEGIA SIMPLE:
    // Guardar la longitud del texto ya pintado y solo pintar lo nuevo.
    // Pero como el HTML es complejo, vamos a hacer algo más visual:
    // Solo actualizamos si hay cambios, y mostramos el bloque completo del comando actual?
    // No, mejor: llevamos un contador de caracteres leídos en el cliente.
    
    // Implementación simple v2:
    // Usamos una variable global `lastStdoutLen` y `lastStderrLen` para este job.
  } catch (e) {
    console.error(e);
  }
}

// Variables para el job actual
let lastStdoutLen = 0;
let lastStderrLen = 0;

async function startPolling(jobId) {
  currentJobId = jobId;
  lastStdoutLen = 0;
  lastStderrLen = 0;
  
  cancelBtn.style.display = 'inline-block';
  sendBtn.disabled = true;
  cmdInput.disabled = true;

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/status/${jobId}`);
      if (!res.ok) return; // Si falla la red, seguimos intentando
      
      const j = await res.json();
      
      // Procesar stdout nuevo
      if (j.stdout && j.stdout.length > lastStdoutLen) {
        const newPart = j.stdout.substring(lastStdoutLen);
        appendLine(newPart, 'stdout');
        lastStdoutLen = j.stdout.length;
      }
      
      // Procesar stderr nuevo
      if (j.stderr && j.stderr.length > lastStderrLen) {
        const newPart = j.stderr.substring(lastStderrLen);
        appendLine(newPart, 'stderr');
        lastStderrLen = j.stderr.length;
      }

      if (j.status !== 'running') {
        clearInterval(pollInterval);
        pollInterval = null;
        currentJobId = null;
        appendLine(`[Proceso finalizado. Return code: ${j.return_code}]`, 'meta');
        resetUI();
      }
      
    } catch (e) {
      console.error("Polling error", e);
    }
  }, 1000); // Poll cada 1 segundo
}

function resetUI() {
  cancelBtn.style.display = 'none';
  sendBtn.disabled = false;
  cmdInput.disabled = false;
  cmdInput.focus();
}

async function sendCommand(cmd) {
  appendLine(`$ ${cmd}`, 'cmd');
  
  try {
    const res = await fetch('/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd })
    });

    const j = await res.json();
    
    if (res.ok && (j.status === 'running' || j.status === 'finished')) {
      appendLine(`[Iniciado Job ID: ${j.job_id}]`, 'meta');
      startPolling(j.job_id);
    } else {
      appendLine(`ERROR: ${j.message || 'unknown'}`, 'stderr');
    }
  } catch (e) {
    appendLine(`Request failed: ${e.message}`, 'stderr');
  }
}

cancelBtn.addEventListener('click', stopJob);

cmdForm.addEventListener('submit', () => {
  const val = cmdInput.value.trim();
  if (!val) return false;
  if (currentJobId) return false; // No permitir nuevo comando si hay uno corriendo
  
  sendCommand(val);
  cmdInput.value = '';
  return false;
});

cmdInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!currentJobId) sendBtn.click();
  }
});

// Start
checkHealth();
setInterval(checkHealth, 10000);
cmdInput.focus();
