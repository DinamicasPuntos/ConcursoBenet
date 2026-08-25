(() => {
  const contenedor = document.getElementById('app');
  if (!contenedor) return;

  const agregarGuia = () => {
    if (contenedor.dataset.guiaAgregada || contenedor.textContent.trim() === 'Cargando...') return;
    contenedor.dataset.guiaAgregada = 'true';
    contenedor.insertAdjacentHTML('afterbegin', `
      <section class="pdv-guide" aria-label="Cómo participar">
        <div><span class="pdv-guide-kicker">ASÍ PARTICIPAS</span><h2>Tu exhibición tiene todo para brillar</h2><p>Sube tus fotos, elige tu favorita y confirma tu participación antes del cierre.</p></div>
        <ol><li><b>1</b><span>Sube hasta 5 fotos</span></li><li><b>2</b><span>Elige tu favorita</span></li><li><b>3</b><span>Confirma y participa</span></li></ol>
      </section>`);
  };

  new MutationObserver(agregarGuia).observe(contenedor, { childList: true, subtree: true });
  agregarGuia();
})();
