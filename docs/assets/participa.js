(() => {
  const productos = document.querySelector('.product-strip');
  if (!productos) return;
  productos.insertAdjacentHTML('beforebegin', `
    <section class="steps-section" aria-labelledby="participa-titulo">
      <div class="section-kicker">ASÍ PARTICIPAS</div>
      <h2 id="participa-titulo">Haz que tu exhibición brille</h2>
      <div class="steps-grid">
        <article><b>01</b><span>Encuentra tu PDV</span></article>
        <article><b>02</b><span>Sube hasta 5 fotografías</span></article>
        <article><b>03</b><span>Elige tu favorita</span></article>
        <article><b>04</b><span>Confirma y participa</span></article>
      </div>
    </section>
    <footer class="brand-footer">Con Bénet tú decides cómo cuidarte.</footer>
  `);
})();
