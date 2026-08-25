(() => {
  const panel = document.getElementById('app');
  const formulario = document.getElementById('login');
  if (!panel || !formulario) return;

  document.body.classList.add('nutresa-login');
  const titulo = formulario.closest('.ops-card')?.querySelector('h2');
  if (titulo) titulo.textContent = 'Acceso Nutresa';

  const observador = new MutationObserver(() => {
    if (panel.querySelector('.lab-grid')) {
      document.body.classList.remove('nutresa-login');
      observador.disconnect();
    }
  });
  observador.observe(panel, { childList: true, subtree: true });
})();
