const state = {
  user: null,
  data: null,
  validation: null,
  availableFields: { latin: [], braces: [] },
  selected: new Set(),
  filtered: [],
  emailSelected: new Set(),
  emailFiltered: [],
  downloadSelectedStudents: new Set(),
  editingId: null,
};

const views = {
  dashboard: ['Inicio', 'Resumen general'],
  excel: ['Excel', 'Subida y validación'],
  students: ['Alumnos', 'Tabla editable'],
  template: ['Plantilla', 'Campos del certificado'],
  generate: ['Generar', 'Crear certificados'],
  downloads: ['Descargas', 'Archivos generados'],
  email: ['Email', 'Enviar certificados PDF'],
  history: ['Historial', 'Generaciones anteriores'],
  settings: ['Ajustes', 'Privacidad y limpieza'],
};

const columns = ['UBICACIÓN', 'NOMBRE', 'APELLIDOS', 'DNI', 'FECHA', 'ACTIVIDAD', 'CONTENIDO', 'ESPECIALIDAD', 'HORAS', 'EMAIL', 'ENVIADO'];
const requiredColumns = ['NOMBRE', 'APELLIDOS', 'DNI', 'FECHA', 'ACTIVIDAD', 'CONTENIDO', 'ESPECIALIDAD', 'HORAS'];

document.addEventListener('DOMContentLoaded', init);

async function init() {
  bindEvents();
  const session = await api('/api/session');
  if (session.user) {
    state.user = session.user;
    showApp();
    await refreshState();
  } else {
    showLogin();
  }
}

function bindEvents() {
  document.querySelectorAll('nav button').forEach(button => {
    button.addEventListener('click', () => switchView(button.dataset.view));
  });
  document.getElementById('newRunBtn').addEventListener('click', () => switchView('excel'));
  document.getElementById('loginForm').addEventListener('submit', login);
  document.getElementById('logoutBtn').addEventListener('click', logout);
  document.getElementById('excelForm').addEventListener('submit', event => uploadForm(event, '/api/upload-excel'));
  document.getElementById('templateForm').addEventListener('submit', event => uploadForm(event, '/api/upload-template'));
  ['searchInput', 'statusFilter', 'activityFilter', 'specialtyFilter', 'locationFilter', 'dateFilter'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderStudents);
  });
  document.getElementById('selectAll').addEventListener('change', event => {
    state.filtered.forEach(student => event.target.checked ? state.selected.add(student.id) : state.selected.delete(student.id));
    renderStudents();
  });
  document.getElementById('selectVisibleBtn').addEventListener('click', () => {
    state.filtered.forEach(student => state.selected.add(student.id));
    renderStudents();
  });
  document.getElementById('clearSelectionBtn').addEventListener('click', () => {
    state.selected.clear();
    renderStudents();
  });
  document.getElementById('generateSelectedStudentsBtn').addEventListener('click', () => {
    generateCertificates([...state.selected], document.getElementById('studentsFormatSelect').value);
  });
  document.getElementById('generateVisibleStudentsBtn').addEventListener('click', () => {
    generateCertificates(state.filtered.map(student => student.id), document.getElementById('studentsFormatSelect').value);
  });
  document.getElementById('generateBtn').addEventListener('click', generateCertificates);
  document.getElementById('previewStudent').addEventListener('change', renderPreview);
  document.querySelectorAll('[data-zip], [data-kind]').forEach(button => button.addEventListener('click', downloadZip));
  document.getElementById('convertPdfsBtn').addEventListener('click', convertGeneratedPdfs);
  document.getElementById('clearDownloadsBtn').addEventListener('click', () => clearData('generated'));
  document.querySelectorAll('[data-clear]').forEach(button => button.addEventListener('click', () => clearData(button.dataset.clear)));
  document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
  document.getElementById('saveEmailSettingsBtn').addEventListener('click', saveEmailSettings);
  document.getElementById('sendEmailBtn').addEventListener('click', sendEmails);
  document.getElementById('sendManualEmailBtn').addEventListener('click', sendManualEmails);
  document.getElementById('manualAttachmentForm').addEventListener('submit', uploadManualEmailAttachment);
  document.getElementById('emailAttachmentForm').addEventListener('submit', uploadEmailAttachment);
  ['emailSearchInput', 'emailActivityFilter', 'emailSpecialtyFilter', 'emailLocationFilter', 'emailDateFilter', 'emailStatusFilter', 'emailPdfFilter'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderEmailStudents);
  });
  document.getElementById('selectVisibleEmailBtn').addEventListener('click', () => {
    state.emailFiltered.forEach(student => state.emailSelected.add(student.id));
    renderEmailStudents();
  });
  document.getElementById('clearEmailSelectionBtn').addEventListener('click', () => {
    state.emailSelected.clear();
    renderEmailStudents();
  });
  document.getElementById('selectAllEmail').addEventListener('change', event => {
    state.emailFiltered.forEach(student => event.target.checked ? state.emailSelected.add(student.id) : state.emailSelected.delete(student.id));
    renderEmailStudents();
  });
  document.getElementById('saveStudentBtn').addEventListener('click', saveStudentFromDialog);
}

async function login(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const result = await api('/api/login', {
    method: 'POST',
    body: JSON.stringify({ username: form.get('username'), password: form.get('password') }),
  });
  if (!result.ok) {
    document.getElementById('loginError').textContent = result.error || 'No se pudo iniciar sesión.';
    return;
  }
  state.user = result.user;
  showApp();
  await refreshState();
}

async function logout() {
  await api('/api/logout', { method: 'POST', body: '{}' });
  state.user = null;
  showLogin();
}

function showLogin() {
  document.getElementById('login').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}

function showApp() {
  document.getElementById('login').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  document.getElementById('userRole').textContent = `${state.user.name} · ${state.user.role}`;
}

async function refreshState() {
  const result = await api('/api/state');
  if (!result.ok) return toast(result.error || 'No se pudo cargar el estado.');
  state.data = result.state;
  state.validation = result.validation;
  state.availableFields = result.available_fields;
  renderAll();
}

async function uploadForm(event, endpoint) {
  event.preventDefault();
  const bar = document.getElementById('progressBar');
  bar.style.width = '25%';
  const result = await api(endpoint, { method: 'POST', body: new FormData(event.target), raw: true });
  bar.style.width = '100%';
  setTimeout(() => bar.style.width = '0', 500);
  if (!result.ok) return toast(result.error || 'No se pudo subir el archivo.');
  state.data = result.state;
  state.validation = result.validation || state.validation;
  state.availableFields = result.available_fields || state.availableFields;
  state.selected.clear();
  renderAll();
  toast('Archivo cargado correctamente.');
}

function switchView(view) {
  document.querySelectorAll('.view').forEach(node => node.classList.toggle('active', node.id === view));
  document.querySelectorAll('nav button').forEach(node => node.classList.toggle('active', node.dataset.view === view));
  document.getElementById('sectionEyebrow').textContent = views[view][0];
  document.getElementById('sectionTitle').textContent = views[view][1];
}

function renderAll() {
  renderDashboard();
  renderValidation();
  renderFields();
  renderFilters();
  renderStudents();
  renderTemplate();
  renderPreviewOptions();
  renderDownloads();
  renderEmail();
  renderHistory();
  renderSettings();
}

function renderDashboard() {
  const students = state.data.students || [];
  const generated = students.filter(s => s.cert_status === 'generado').length;
  const errors = students.filter(s => s.cert_status === 'error').length;
  const pending = students.length - generated - errors;
  const cards = [
    ['Total de alumnos cargados', students.length],
    ['Certificados pendientes', pending],
    ['Certificados generados', generated],
    ['Registros con errores', errors],
    ['Última carga de Excel', state.data.excel?.filename || 'Sin Excel'],
    ['Última plantilla utilizada', state.data.template?.filename || 'Sin plantilla'],
  ];
  document.getElementById('summaryCards').innerHTML = cards.map(([label, value]) => metric(label, value)).join('');
}

function renderValidation() {
  const v = state.validation || {};
  const cards = [
    ['Total de alumnos', v.total ?? 0],
    ['Alumnos correctos', v.correct ?? 0],
    ['Con errores', v.with_errors ?? 0],
    ['Duplicados', v.duplicates ?? 0],
    ['Filas incompletas', v.incomplete ?? 0],
  ];
  document.getElementById('validationCards').innerHTML = cards.map(([label, value]) => metric(label, value)).join('');
}

function metric(label, value) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></article>`;
}

function renderFields() {
  const chips = [...(state.availableFields.latin || []), ...(state.availableFields.braces || [])].map(chip).join('');
  document.getElementById('availableFields').innerHTML = chips || '<p class="muted">Sube un Excel para ver los campos.</p>';
  document.getElementById('templateAvailableFields').innerHTML = chips || '<p class="muted">Sin campos disponibles.</p>';
}

function renderFilters() {
  fillSelect('activityFilter', unique('ACTIVIDAD'), 'Todas las actividades');
  fillSelect('specialtyFilter', unique('ESPECIALIDAD'), 'Todas las especialidades');
  fillSelect('locationFilter', unique('UBICACIÓN'), 'Todas las ubicaciones');
  fillSelect('dateFilter', unique('FECHA'), 'Todas las fechas');
}

function fillSelect(id, values, label) {
  const select = document.getElementById(id);
  const current = select.value;
  select.innerHTML = `<option value="all">${label}</option>` + values.map(value => `<option value="${escapeAttr(value)}">${escapeHtml(value)}</option>`).join('');
  select.value = [...values, 'all'].includes(current) ? current : 'all';
}

function unique(column) {
  return [...new Set((state.data.students || []).map(s => s[column]).filter(Boolean))].sort();
}

function renderStudents() {
  const search = document.getElementById('searchInput').value.trim().toLowerCase();
  const status = document.getElementById('statusFilter').value;
  const activity = document.getElementById('activityFilter').value;
  const specialty = document.getElementById('specialtyFilter').value;
  const location = document.getElementById('locationFilter').value;
  const date = document.getElementById('dateFilter').value;
  state.filtered = (state.data.students || []).filter(student => {
    const haystack = ['NOMBRE', 'APELLIDOS', 'DNI', 'ACTIVIDAD', 'ESPECIALIDAD', 'UBICACIÓN', 'FECHA'].map(key => student[key] || '').join(' ').toLowerCase();
    return (!search || haystack.includes(search))
      && (status === 'all' || student.cert_status === status)
      && (activity === 'all' || student.ACTIVIDAD === activity)
      && (specialty === 'all' || student.ESPECIALIDAD === specialty)
      && (location === 'all' || student.UBICACIÓN === location)
      && (date === 'all' || student.FECHA === date);
  });
  document.getElementById('studentsBody').innerHTML = state.filtered.map(studentRow).join('');
  document.querySelectorAll('[data-select-student]').forEach(input => {
    input.addEventListener('change', () => {
      input.checked ? state.selected.add(input.dataset.selectStudent) : state.selected.delete(input.dataset.selectStudent);
      renderSelectionInfo();
    });
  });
  document.querySelectorAll('[data-edit-student]').forEach(button => button.addEventListener('click', () => openStudentDialog(button.dataset.editStudent)));
  document.querySelectorAll('[data-generate-one]').forEach(button => button.addEventListener('click', () => {
    generateCertificates([button.dataset.generateOne], document.getElementById('studentsFormatSelect').value);
  }));
  document.getElementById('selectAll').checked = state.filtered.length > 0 && state.filtered.every(student => state.selected.has(student.id));
  renderSelectionInfo();
}

function studentRow(student) {
  return `<tr>
    <td><input type="checkbox" data-select-student="${escapeAttr(student.id)}" ${state.selected.has(student.id) ? 'checked' : ''}></td>
    ${['UBICACIÓN', 'NOMBRE', 'APELLIDOS', 'DNI', 'FECHA', 'ACTIVIDAD'].map(key => `<td>${escapeHtml(student[key] || '')}</td>`).join('')}
    <td class="truncate" title="${escapeAttr(student.CONTENIDO || '')}">${escapeHtml(student.CONTENIDO || '')}</td>
    <td>${escapeHtml(student.ESPECIALIDAD || '')}</td>
    <td>${escapeHtml(student.HORAS || '')}</td>
    <td>
      <span class="status ${student.cert_status}">${labelStatus(student)}</span>
      ${studentErrorText(student) ? `<div class="error-detail">${escapeHtml(studentErrorText(student))}</div>` : ''}
    </td>
    <td class="download-actions"><button class="secondary" data-edit-student="${escapeAttr(student.id)}">Ver/editar</button><button class="secondary" data-generate-one="${escapeAttr(student.id)}">Generar</button></td>
  </tr>`;
}

function labelStatus(student) {
  if (student.cert_status === 'error') return student.errors?.length ? 'Error' : 'Error generación';
  if (student.cert_status === 'generado') return 'Generado';
  return 'Pendiente';
}

function studentErrorText(student) {
  const errors = [...(student.errors || [])];
  if (student.cert_status === 'error' && student.last_error) errors.push(student.last_error);
  return [...new Set(errors.filter(Boolean))].join(' · ');
}

function renderSelectionInfo() {
  document.getElementById('selectionInfo').textContent = `${state.selected.size} seleccionado(s), ${state.filtered.length} visibles`;
  const hint = document.getElementById('generationScopeHint');
  if (hint) hint.textContent = `Seleccionados ahora: ${state.selected.size}. Visibles con los filtros actuales: ${state.filtered.length}.`;
}

function renderTemplate() {
  const detected = state.data.template?.detected_fields || [];
  document.getElementById('detectedFields').innerHTML = detected.map(field => chip(`«${field}»`)).join('') || '<p class="muted">Sube una plantilla para detectar campos.</p>';
}

function renderPreviewOptions() {
  const select = document.getElementById('previewStudent');
  select.innerHTML = (state.data.students || []).map(student => `<option value="${escapeAttr(student.id)}">${escapeHtml(student.NOMBRE || '')} ${escapeHtml(student.APELLIDOS || '')} · ${escapeHtml(student.DNI || '')}</option>`).join('');
  renderPreview();
}

function renderPreview() {
  const id = document.getElementById('previewStudent').value;
  const student = (state.data.students || []).find(item => item.id === id) || state.data.students?.[0];
  if (!student) {
    document.getElementById('previewBox').textContent = 'No hay alumnos para previsualizar.';
    return;
  }
  document.getElementById('previewBox').textContent =
`DIPLOMA DE APROVECHAMIENTO

Que D./Dña. ${student.NOMBRE || ''} ${student.APELLIDOS || ''} con N.I.F./N.I.E. ${student.DNI || ''}, ha realizado con aprovechamiento la actividad denominada "${student.ACTIVIDAD || ''}" que contiene ${student.HORAS || ''} horas de formación, en modalidad presencial, durante la jornada del día ${student.FECHA || ''}.

ITINERARIO O ESPECIALIDAD "${student.ESPECIALIDAD || ''}"

Contenido

${student.CONTENIDO || ''}`;
}

async function generateCertificates(oneId = null, forcedFormat = null) {
  const explicitIds = Array.isArray(oneId) ? oneId : null;
  const scope = document.getElementById('generationScope').value;
  let ids = explicitIds || [];
  if (!explicitIds) {
    if (scope === 'selected') ids = [...state.selected];
    if (scope === 'visible') ids = state.filtered.map(s => s.id);
    if (scope === 'valid') ids = state.data.students.filter(s => !s.errors?.length).map(s => s.id);
  }
  if (!ids.length) return toast('Selecciona al menos un alumno.');
  const format = String(forcedFormat || document.getElementById('formatSelect').value || 'docx').trim().toLowerCase();
  document.getElementById('generationResult').textContent = 'Generando certificados...';
  document.getElementById('progressBar').style.width = '45%';
  const result = await api('/api/generate', {
    method: 'POST',
    body: JSON.stringify({ student_ids: ids, format }),
  });
  document.getElementById('progressBar').style.width = '100%';
  setTimeout(() => document.getElementById('progressBar').style.width = '0', 600);
  if (!result.ok) {
    document.getElementById('generationResult').textContent = result.error || 'No se pudo generar.';
    return toast(result.error || 'No se pudo generar.');
  }
  await refreshState();
  const errorText = result.errors?.length ? ` ${result.errors.length} aviso(s) o error(es).` : '';
  document.getElementById('generationResult').textContent = `Generados ${result.generated.length} certificado(s).${errorText}`;
  toast('Generación finalizada.');
}

function renderDownloads() {
  const files = [];
  (state.data.students || []).forEach(student => {
    (student.files || []).forEach(file => files.push({ student, file }));
  });
  document.getElementById('downloadList').innerHTML = files.map(({ student, file }) => `
    <div class="file-item">
      <label class="file-check">
        <input type="checkbox" data-download-student="${escapeAttr(student.id)}" ${state.downloadSelectedStudents.has(student.id) ? 'checked' : ''}>
        <span>${escapeHtml(student.NOMBRE || '')} ${escapeHtml(student.APELLIDOS || '')} · ${escapeHtml(displayCertificateName(student, file))}</span>
      </label>
      <a class="secondary link-button" href="/download/file?path=${encodeURIComponent(file.path)}">Descargar</a>
    </div>`).join('') || '<p class="muted">Todavía no hay certificados generados.</p>';
  document.querySelectorAll('[data-download-student]').forEach(input => {
    input.addEventListener('change', () => {
      input.checked ? state.downloadSelectedStudents.add(input.dataset.downloadStudent) : state.downloadSelectedStudents.delete(input.dataset.downloadStudent);
    });
  });
}

function displayCertificateName(student, file) {
  const extension = file?.type === 'pdf' ? 'pdf' : file?.type === 'docx' ? 'docx' : String(file?.name || '').split('.').pop() || 'pdf';
  const parts = [
    'Diploma de aprovechamiento',
    `${student.NOMBRE || ''} ${student.APELLIDOS || ''}`.trim(),
    student.ACTIVIDAD || '',
    student.FECHA || '',
  ].filter(Boolean);
  return `${parts.join(' - ')}.${extension}`;
}

async function convertGeneratedPdfs() {
  const box = document.getElementById('pdfHelpBox');
  box.classList.add('hidden');
  box.textContent = '';
  const ids = state.downloadSelectedStudents.size ? [...state.downloadSelectedStudents] : [];
  toast(ids.length ? 'Convirtiendo certificados marcados a PDF...' : 'Convirtiendo todos los Word generados a PDF...');
  const result = await api('/api/convert-pdfs', {
    method: 'POST',
    body: JSON.stringify({ student_ids: ids }),
  });
  if (!result.ok) return toast(result.error || 'No se pudo convertir a PDF.');
  state.data = result.state;
  renderAll();
  if (result.help) {
    box.textContent = result.help;
    box.classList.remove('hidden');
  }
  toast(`PDF creados: ${result.converted.length}. Errores: ${result.errors.length}.`);
}

function downloadZip(event) {
  const mode = event.currentTarget.dataset.zip;
  const kind = event.currentTarget.dataset.kind || 'all';
  const ids = mode === 'selected' ? [...state.selected] : [];
  if (mode === 'selected' && !ids.length) return toast('Selecciona alumnos para descargar.');
  window.location.href = `/download/zip?ids=${encodeURIComponent(ids.join(','))}&kind=${encodeURIComponent(kind)}`;
}

function renderHistory() {
  document.getElementById('historyBody').innerHTML = (state.data.history || []).map(item => `
    <tr>
      <td>${escapeHtml(formatDate(item.date))}</td><td>${escapeHtml(item.user || '')}</td><td>${escapeHtml(item.student || '')}</td><td>${escapeHtml(item.dni || '')}</td>
      <td>${escapeHtml(item.activity || '')}</td><td>${escapeHtml(item.format || '')}</td><td><span class="status ${item.status}">${escapeHtml(item.status || '')}</span></td><td>${escapeHtml(item.filename || item.message || '')}</td>
    </tr>`).join('') || '<tr><td colspan="8">Sin historial todavía.</td></tr>';
}

function renderEmail() {
  const smtp = state.data.settings?.smtp || {};
  const template = state.data.settings?.email_template || {};
  document.getElementById('smtpHost').value = smtp.host || '';
  document.getElementById('smtpPort').value = smtp.port || '587';
  document.getElementById('smtpSecurity').value = smtp.security || 'starttls';
  document.getElementById('smtpUsername').value = smtp.username || '';
  document.getElementById('smtpPassword').value = '';
  document.getElementById('smtpFromEmail').value = smtp.from_email || '';
  document.getElementById('smtpFromName').value = smtp.from_name || 'Mainjobs Generador de Diplomas';
  document.getElementById('emailSubject').value = template.subject || 'Diploma de aprovechamiento - {{ACTIVIDAD}}';
  document.getElementById('emailBody').value = template.body || 'Buenos días,\n\nTe escribimos desde Mainjobs, la empresa que gestiona las actividades de la Agencia para el Empleo, para hacerte llegar el diploma de aprovechamiento correspondiente a la actividad {{ACTIVIDAD}} en la que participaste el día {{FECHA}}.\n\nUn cordial saludo';
  const attachment = state.data.email_attachment || {};
  document.getElementById('emailAttachmentInfo').textContent = attachment.filename ? `PDF subido: ${attachment.filename}` : 'No hay PDF manual subido.';
  const manualAttachment = state.data.manual_email_attachment || {};
  document.getElementById('manualAttachmentInfo').textContent = manualAttachment.filename ? `PDF manual: ${manualAttachment.filename}` : 'No hay PDF manual específico subido.';
  fillSelect('emailActivityFilter', unique('ACTIVIDAD'), 'Todas las actividades');
  fillSelect('emailSpecialtyFilter', unique('ESPECIALIDAD'), 'Todas las especialidades');
  fillSelect('emailLocationFilter', unique('UBICACIÓN'), 'Todas las ubicaciones');
  fillSelect('emailDateFilter', unique('FECHA'), 'Todas las fechas');
  renderEmailStudents();
  renderManualEmailStudentOptions();
  document.getElementById('emailHistoryBody').innerHTML = (state.data.email_history || []).map(item => `
    <tr>
      <td>${escapeHtml(formatDate(item.date))}</td><td>${escapeHtml(item.user || '')}</td><td>${escapeHtml(item.student || '')}</td>
      <td>${escapeHtml(item.email || '')}</td><td>${escapeHtml(item.activity || '')}</td><td><span class="status ${item.status === 'enviado' ? 'generado' : 'error'}">${escapeHtml(item.status || '')}</span></td>
      <td>${escapeHtml(item.filename || item.message || '')}</td>
    </tr>`).join('') || '<tr><td colspan="7">Sin emails enviados todavía.</td></tr>';
}

function renderManualEmailStudentOptions() {
  const select = document.getElementById('manualEmailStudent');
  const current = select.value;
  select.innerHTML = '<option value="">Sin alumno asociado</option>' + (state.data.students || []).map(student => {
    const fullName = `${student.NOMBRE || ''} ${student.APELLIDOS || ''}`.trim();
    return `<option value="${escapeAttr(student.id)}">${escapeHtml(fullName)} · ${escapeHtml(student.DNI || '')} · ${escapeHtml(student.ACTIVIDAD || 'Sin actividad')} · ${escapeHtml(student.FECHA || 'Sin fecha')}</option>`;
  }).join('');
  select.value = [...select.options].some(option => option.value === current) ? current : '';
}

function renderEmailStudents() {
  const search = document.getElementById('emailSearchInput').value.trim().toLowerCase();
  const activity = document.getElementById('emailActivityFilter').value;
  const specialty = document.getElementById('emailSpecialtyFilter').value;
  const location = document.getElementById('emailLocationFilter').value;
  const date = document.getElementById('emailDateFilter').value;
  const status = document.getElementById('emailStatusFilter').value;
  const pdf = document.getElementById('emailPdfFilter').value;
  state.emailFiltered = (state.data.students || []).filter(student => {
    const hasPdf = (student.files || []).some(file => file.type === 'pdf');
    const emailStatus = student.email_status || 'pendiente';
    const haystack = ['NOMBRE', 'APELLIDOS', 'DNI', 'EMAIL', 'ACTIVIDAD', 'ESPECIALIDAD', 'UBICACIÓN', 'FECHA'].map(key => student[key] || '').join(' ').toLowerCase();
    return (!search || haystack.includes(search))
      && (activity === 'all' || student.ACTIVIDAD === activity)
      && (specialty === 'all' || student.ESPECIALIDAD === specialty)
      && (location === 'all' || student.UBICACIÓN === location)
      && (date === 'all' || student.FECHA === date)
      && (status === 'all' || emailStatus === status)
      && (pdf === 'all' || (pdf === 'with' ? hasPdf : !hasPdf));
  });
  document.getElementById('emailStudentsBody').innerHTML = state.emailFiltered.map(emailStudentRow).join('');
  document.querySelectorAll('[data-select-email]').forEach(input => {
    input.addEventListener('change', () => {
      input.checked ? state.emailSelected.add(input.dataset.selectEmail) : state.emailSelected.delete(input.dataset.selectEmail);
      renderEmailSelectionInfo();
    });
  });
  document.getElementById('selectAllEmail').checked = state.emailFiltered.length > 0 && state.emailFiltered.every(student => state.emailSelected.has(student.id));
  renderEmailSelectionInfo();
}

function emailStudentRow(student) {
  const hasPdf = (student.files || []).some(file => file.type === 'pdf');
  const emailStatus = student.email_status || 'pendiente';
  const fullName = `${student.NOMBRE || ''} ${student.APELLIDOS || ''}`.trim();
  return `<tr>
    <td><input type="checkbox" data-select-email="${escapeAttr(student.id)}" ${state.emailSelected.has(student.id) ? 'checked' : ''}></td>
    <td>${escapeHtml(fullName)}</td>
    <td>${escapeHtml(student.DNI || '')}</td>
    <td>${escapeHtml(student.EMAIL || '')}</td>
    <td>${escapeHtml(student.FECHA || '')}</td>
    <td>${escapeHtml(student.ACTIVIDAD || '')}</td>
    <td>${escapeHtml(student.ESPECIALIDAD || '')}</td>
    <td><span class="status ${hasPdf ? 'generado' : 'pendiente'}">${hasPdf ? 'Disponible' : 'Sin PDF'}</span></td>
    <td><span class="status ${emailStatus === 'enviado' ? 'generado' : emailStatus === 'error' ? 'error' : 'pendiente'}">${escapeHtml(emailStatus)}</span></td>
  </tr>`;
}

function renderEmailSelectionInfo() {
  document.getElementById('emailSelectionInfo').textContent = `${state.emailSelected.size} seleccionado(s), ${state.emailFiltered.length} visibles`;
}

async function uploadEmailAttachment(event) {
  event.preventDefault();
  const result = await api('/api/upload-email-attachment', { method: 'POST', body: new FormData(event.target), raw: true });
  if (!result.ok) return toast(result.error || 'No se pudo subir el PDF.');
  state.data = result.state;
  document.getElementById('emailAttachmentMode').value = 'manual';
  renderEmail();
  toast('PDF adjunto subido.');
}

async function uploadManualEmailAttachment(event) {
  event.preventDefault();
  const result = await api('/api/upload-manual-email-attachment', { method: 'POST', body: new FormData(event.target), raw: true });
  if (!result.ok) return toast(result.error || 'No se pudo subir el PDF manual.');
  state.data = result.state;
  document.getElementById('manualAttachmentMode').value = 'manual';
  renderEmail();
  toast('PDF manual subido.');
}

async function saveEmailSettings() {
  const result = await api('/api/settings', {
    method: 'POST',
    body: JSON.stringify({
      smtp: {
        host: document.getElementById('smtpHost').value,
        port: document.getElementById('smtpPort').value || '587',
        security: document.getElementById('smtpSecurity').value,
        username: document.getElementById('smtpUsername').value,
        password: document.getElementById('smtpPassword').value,
        from_email: document.getElementById('smtpFromEmail').value,
        from_name: document.getElementById('smtpFromName').value,
      },
      email_template: {
        subject: document.getElementById('emailSubject').value,
        body: document.getElementById('emailBody').value,
      },
    }),
  });
  if (!result.ok) {
    toast(result.error || 'No se pudo guardar el email.');
    return false;
  }
  state.data = result.state;
  renderEmail();
  toast('Configuración de email guardada.');
  return true;
}

async function sendEmails() {
  const saved = await saveEmailSettings();
  if (!saved) return;
  const ids = [...state.emailSelected];
  if (!ids.length) return toast('Selecciona al menos un alumno.');
  document.getElementById('emailResult').textContent = 'Enviando emails...';
  const result = await api('/api/send-email', {
    method: 'POST',
    body: JSON.stringify({
      student_ids: ids,
      subject: document.getElementById('emailSubject').value,
      body: document.getElementById('emailBody').value,
      attachment_mode: document.getElementById('emailAttachmentMode').value,
    }),
  });
  if (!result.ok) {
    document.getElementById('emailResult').textContent = result.error || 'No se pudo enviar.';
    return toast(result.error || 'No se pudo enviar.');
  }
  state.data = result.state;
  renderEmail();
  document.getElementById('emailResult').textContent = `Enviados ${result.sent.length} email(s). Errores: ${result.errors.length}.`;
  toast('Proceso de email finalizado.');
}

async function sendManualEmails() {
  const saved = await saveEmailSettings();
  if (!saved) return;
  const emails = document.getElementById('manualEmails').value.split(/[\n,;]+/).map(item => item.trim()).filter(Boolean);
  if (!emails.length) return toast('Escribe al menos un email manual.');
  document.getElementById('manualEmailResult').textContent = 'Enviando email manual...';
  const result = await api('/api/send-manual-email', {
    method: 'POST',
    body: JSON.stringify({
      emails,
      subject: document.getElementById('manualEmailSubject').value,
      body: document.getElementById('manualEmailBody').value,
      attachment_mode: document.getElementById('manualAttachmentMode').value,
      fallback_student_id: document.getElementById('manualEmailStudent').value,
    }),
  });
  if (!result.ok) {
    document.getElementById('manualEmailResult').textContent = result.error || 'No se pudo enviar.';
    return toast(result.error || 'No se pudo enviar.');
  }
  state.data = result.state;
  renderEmail();
  document.getElementById('manualEmailResult').textContent = `Enviados ${result.sent.length} email(s). Errores: ${result.errors.length}.`;
  toast('Envío manual finalizado.');
}

function renderSettings() {
  document.getElementById('filenameBase').value = state.data.settings?.filename_base || 'Certificado';
  document.getElementById('keepCertificates').checked = Boolean(state.data.settings?.keep_certificates);
}

async function saveSettings() {
  const result = await api('/api/settings', {
    method: 'POST',
    body: JSON.stringify({
      filename_base: document.getElementById('filenameBase').value || 'Certificado',
      keep_certificates: document.getElementById('keepCertificates').checked,
    }),
  });
  if (!result.ok) return toast(result.error || 'No se pudieron guardar los ajustes.');
  state.data = result.state;
  toast('Ajustes guardados.');
}

async function clearData(target) {
  if (!confirm('¿Seguro que quieres borrar estos datos?')) return;
  const result = await api('/api/clear', { method: 'POST', body: JSON.stringify({ target }) });
  if (!result.ok) return toast(result.error || 'No se pudo borrar.');
  state.data = result.state;
  state.selected.clear();
  renderAll();
  toast('Datos borrados.');
}

function openStudentDialog(id) {
  state.editingId = id;
  const student = state.data.students.find(item => item.id === id);
  const errorHtml = studentErrorText(student)
    ? `<div class="dialog-alert"><strong>Errores detectados</strong><span>${escapeHtml(studentErrorText(student))}</span></div>`
    : '';
  document.getElementById('dialogFields').innerHTML = errorHtml + columns.map(column => {
    const value = student[column] || '';
    const input = column === 'CONTENIDO'
      ? `<textarea data-dialog-field="${column}">${escapeHtml(value)}</textarea>`
      : `<input data-dialog-field="${column}" value="${escapeAttr(value)}">`;
    return `<label>${column}${input}</label>`;
  }).join('');
  document.getElementById('studentDialog').showModal();
}

async function saveStudentFromDialog(event) {
  event.preventDefault();
  const student = state.data.students.find(item => item.id === state.editingId);
  document.querySelectorAll('[data-dialog-field]').forEach(input => student[input.dataset.dialogField] = input.value);
  const result = await api('/api/students', { method: 'POST', body: JSON.stringify({ students: state.data.students }) });
  if (!result.ok) return toast(result.error || 'No se pudo guardar.');
  state.data = result.state;
  state.validation = result.validation;
  document.getElementById('studentDialog').close();
  renderAll();
  toast('Alumno actualizado.');
}

async function api(url, options = {}) {
  const fetchOptions = { credentials: 'same-origin', ...options };
  if (!options.raw) fetchOptions.headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  delete fetchOptions.raw;
  const response = await fetch(url, fetchOptions);
  const text = await response.text();
  try {
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) data.ok = false;
    return data;
  } catch {
    return { ok: response.ok, text };
  }
}

function chip(text) {
  return `<span class="chip">${escapeHtml(text)}</span>`;
}

function formatDate(value) {
  if (!value) return '';
  return value.replace('T', ' ');
}

function toast(message) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.classList.remove('hidden');
  setTimeout(() => node.classList.add('hidden'), 3200);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#096;');
}
