// Navigation and printing only. This guide never controls an instrument.
(() => {
  function reveal(hash) {
    const target = document.getElementById(hash.replace(/^#/, ''));
    if (!target || !target.closest('#testing-guide')) return;
    for (let section = target.closest('details'); section; section = section.parentElement.closest('details')) section.open = true;
    target.scrollIntoView({ block: 'start' });
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('#testing-guide a[href^="#"]');
    if (link) reveal(link.hash);
  });
  window.addEventListener('hashchange', () => reveal(location.hash));
  if (location.hash) reveal(location.hash);
  let printState;
  window.addEventListener('beforeprint', () => {
    printState = [...document.querySelectorAll('#testing-guide details')].map(el => [el, el.open]);
    printState.forEach(([el]) => { el.open = true; });
  });
  window.addEventListener('afterprint', () => {
    printState?.forEach(([el, open]) => { el.open = open; });
  });
})();
