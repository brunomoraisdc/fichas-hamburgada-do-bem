const MAX_DIMENSION = 1600;
const JPEG_QUALITY = 0.85;
const CONTRAST_FACTOR = 1.4;
const POLL_INTERVAL_MS = 1500;

const FIELDS = [
  { path: "crianca.nome", label: "Nome da criança", type: "text" },
  { path: "crianca.idade", label: "Idade", type: "number" },
  { path: "crianca.sala", label: "Sala", type: "text" },
  { path: "crianca.numero_ficha", label: "Número da ficha", type: "text" },
  { path: "responsavel.nome", label: "Nome do responsável", type: "text" },
  { path: "responsavel.rg", label: "RG", type: "text" },
  { path: "responsavel.telefone_principal", label: "Telefone principal", type: "text" },
  { path: "responsavel.telefone_secundario", label: "Telefone secundário", type: "text" },
  { path: "autorizacoes.pode_sair_sozinho", label: "Pode sair sozinho?", type: "bool" },
];

const screens = {
  capture: document.getElementById("screen-capture"),
  preview: document.getElementById("screen-preview"),
  processing: document.getElementById("screen-processing"),
  validation: document.getElementById("screen-validation"),
  success: document.getElementById("screen-success"),
  error: document.getElementById("screen-error"),
};

const state = {
  jobId: null,
  pollTimer: null,
  processedBlob: null,
  dados: null,
  camposIncertos: new Set(),
};

function showScreen(name) {
  for (const el of Object.values(screens)) el.hidden = true;
  screens[name].hidden = false;
}

function resetToCapture() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  state.jobId = null;
  state.processedBlob = null;
  state.dados = null;
  state.camposIncertos = new Set();
  document.getElementById("file-input").value = "";
  showScreen("capture");
}

function showError(message) {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  document.getElementById("error-message").textContent = message;
  showScreen("error");
}

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Não foi possível ler a imagem."));
    };
    img.src = url;
  });
}

async function preprocessImage(file) {
  const img = await loadImageFromFile(file);

  let { width, height } = img;
  if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
    const scale = MAX_DIMENSION / Math.max(width, height);
    width = Math.round(width * scale);
    height = Math.round(height * scale);
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, width, height);

  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;
  const intercept = 128 * (1 - CONTRAST_FACTOR);
  for (let i = 0; i < data.length; i += 4) {
    const gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    const adjusted = Math.min(255, Math.max(0, gray * CONTRAST_FACTOR + intercept));
    data[i] = data[i + 1] = data[i + 2] = adjusted;
  }
  ctx.putImageData(imageData, 0, 0);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Falha ao gerar imagem."))),
      "image/jpeg",
      JPEG_QUALITY
    );
  });
}

function getByPath(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

function setByPath(obj, path, value) {
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) cur = cur[keys[i]];
  cur[keys[keys.length - 1]] = value;
}

async function uploadImage(blob) {
  const formData = new FormData();
  formData.append("imagem", blob, "ficha.jpg");
  const res = await fetch("/api/upload", { method: "POST", body: formData });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Falha ao enviar a foto.");
  }
  const data = await res.json();
  return data.job_id;
}

function startPolling(jobId) {
  state.pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Job não encontrado.");
      }
      const job = await res.json();

      if (job.status === "concluido") {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        renderValidation(job);
      } else if (job.status === "erro") {
        showError(job.erro || "Erro ao processar a ficha com a IA.");
      }
    } catch (err) {
      showError(err.message);
    }
  }, POLL_INTERVAL_MS);
}

function renderValidation(job) {
  state.jobId = job.job_id;
  state.dados = JSON.parse(JSON.stringify(job.dados));
  state.camposIncertos = new Set(job.campos_incertos || []);

  const container = document.getElementById("validation-fields");
  container.innerHTML = "";

  for (const field of FIELDS) {
    const value = getByPath(state.dados, field.path);
    const isUncertain = state.camposIncertos.has(field.path);

    const wrapper = document.createElement("div");
    wrapper.className = "field" + (isUncertain ? " field-uncertain" : "");

    const label = document.createElement("label");
    label.htmlFor = "field-" + field.path;
    label.textContent = field.label + (isUncertain ? " ⚠️ revisar" : "");
    wrapper.appendChild(label);

    let input;
    if (field.type === "bool") {
      input = document.createElement("select");
      input.innerHTML = `
        <option value="">—</option>
        <option value="true">Sim</option>
        <option value="false">Não</option>
      `;
      input.value = value === null || value === undefined ? "" : String(value);
    } else {
      input = document.createElement("input");
      input.type = field.type === "number" ? "number" : "text";
      input.value = value === null || value === undefined ? "" : value;
    }
    input.id = "field-" + field.path;
    input.dataset.path = field.path;
    input.dataset.type = field.type;
    wrapper.appendChild(input);

    container.appendChild(wrapper);
  }

  showScreen("validation");
}

document.getElementById("file-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  try {
    state.processedBlob = await preprocessImage(file);
    document.getElementById("preview-image").src = URL.createObjectURL(state.processedBlob);
    showScreen("preview");
  } catch (err) {
    showError(err.message);
  }
});

document.getElementById("btn-retake").addEventListener("click", () => {
  document.getElementById("file-input").value = "";
  document.getElementById("file-input").click();
});

document.getElementById("btn-send").addEventListener("click", async (event) => {
  const btn = event.currentTarget;
  btn.disabled = true;
  try {
    const jobId = await uploadImage(state.processedBlob);
    showScreen("processing");
    startPolling(jobId);
  } catch (err) {
    showError(err.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("btn-cancel-validation").addEventListener("click", () => {
  resetToCapture();
});

document.getElementById("form-validation").addEventListener("submit", async (event) => {
  event.preventDefault();

  const inputs = document.querySelectorAll("#validation-fields [data-path]");
  for (const input of inputs) {
    const path = input.dataset.path;
    let value = input.value;
    if (input.dataset.type === "number") {
      value = value === "" ? null : Number(value);
    } else if (input.dataset.type === "bool") {
      value = value === "" ? null : value === "true";
    } else {
      value = value === "" ? null : value;
    }
    setByPath(state.dados, path, value);
  }

  const submitBtn = event.submitter;
  submitBtn.disabled = true;
  try {
    const res = await fetch("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: state.jobId, dados: state.dados }),
    });

    if (res.status === 409) {
      const body = await res.json().catch(() => ({}));
      showError(`Ficha duplicada: ${body.detail || "esta ficha já foi cadastrada."}`);
      return;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Falha ao salvar a ficha.");
    }

    showScreen("success");
  } catch (err) {
    showError(err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById("btn-new-after-success").addEventListener("click", resetToCapture);
document.getElementById("btn-new-after-error").addEventListener("click", resetToCapture);
