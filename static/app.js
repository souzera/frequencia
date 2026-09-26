const form = document.querySelector('#download-form');
const input = document.querySelector('#url');
const format = document.querySelector('#type');
const source = document.querySelector('#source');
const status = document.querySelector('#status');
const button = document.querySelector('#submit');
const link = document.querySelector('#download-link');
let timer, inspection = 0, fileUrl;

input.addEventListener('input', () => {
  clearTimeout(timer);
  const version = ++inspection;
  source.textContent = 'Cole o link para identificar a origem.';
  format.options[1].disabled = false;
  if (!input.value.trim()) return;
  timer = setTimeout(async () => {
    try {
      const response = await fetch('/api/media/inspect', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: input.value.trim()})
      });
      const data = await response.json();
      if (version !== inspection) return;
      if (!response.ok) throw new Error(data.error);
      const spotify = data.source === 'spotify';
      source.textContent = spotify ? 'Spotify identificado · faixa individual' : 'YouTube identificado · áudio ou vídeo';
      format.options[1].disabled = spotify;
      if (spotify) format.value = 'audio';
    } catch (error) {
      if (version === inspection) source.textContent = error.message || 'Não foi possível identificar o link.';
    }
  }, 350);
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (button.disabled) return;
  const body = {url: input.value.trim(), type: format.value, authorized: document.querySelector('#authorized').checked};
  button.disabled = true;
  link.hidden = true;
  if (fileUrl) URL.revokeObjectURL(fileUrl);
  status.className = '';
  status.textContent = 'Preparando seu arquivo… Mantenha esta página aberta. Isso pode levar alguns minutos.';
  try {
    const response = await fetch('/api/media/download', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'O servidor não conseguiu concluir o preparo. Tente novamente.');
    }
    fileUrl = URL.createObjectURL(await response.blob());
    link.href = fileUrl;
    link.download = body.type === 'audio' ? 'audio.mp3' : 'video.mp4';
    link.hidden = false;
    link.click();
    status.textContent = 'Arquivo pronto! Se o download não começar, use o link abaixo.';
  } catch (error) {
    status.className = 'error';
    status.textContent = error.message || 'Falha de conexão. Tente novamente.';
  } finally {
    button.disabled = false;
  }
});
window.addEventListener('pagehide', () => { if (fileUrl) URL.revokeObjectURL(fileUrl); });
