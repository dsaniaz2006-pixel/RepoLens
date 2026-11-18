import { mountDepthRibbons } from './depth-ribbons.js';
/* Lightweight original landing motion. No auth calls, trackers or third-party scripts. */
const body = document.body;
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

// Reveal sections only where IntersectionObserver can safely restore them.
if (!reducedMotion.matches && 'IntersectionObserver' in window) {
  body.classList.add('js-motion');
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  }, {rootMargin: '0px 0px -35px 0px', threshold: .06});
  document.querySelectorAll('[data-reveal]').forEach(element => {
    // The first viewport must never wait on IntersectionObserver/slow hardware.
    if (element.matches('.hero-copy, .hero-art')) element.classList.add('is-visible');
    else observer.observe(element);
  });
} else {
  document.querySelectorAll('[data-reveal]').forEach(element => element.classList.add('is-visible'));
}

// This is an illustrative UI demo, never a real repository analysis request.
const previewButtons = [...document.querySelectorAll('[data-preview]')];
const previewPanels = [...document.querySelectorAll('[data-panel]')];
for (const button of previewButtons) {
  button.addEventListener('click', () => {
    const selected = button.dataset.preview;
    for (const option of previewButtons) {
      const active = option === button;
      option.classList.toggle('is-active', active);
      option.setAttribute('aria-pressed', String(active));
    }
    for (const panel of previewPanels) panel.hidden = panel.dataset.panel !== selected;
  });
}

// Perspective-parallax is pointer-only and deliberately subtle. All input is
// local presentation state; the illustrative panel makes no API requests.
const tilt = document.querySelector('[data-tilt-window]');
const finePointer = window.matchMedia('(pointer:fine)');
if (tilt && !reducedMotion.matches && finePointer.matches) {
  const art = tilt.closest('.hero-art');
  art.addEventListener('pointermove', event => {
    const bounds = art.getBoundingClientRect();
    const x = Math.max(-.5, Math.min(.5, (event.clientX - bounds.left) / bounds.width - .5));
    const y = Math.max(-.5, Math.min(.5, (event.clientY - bounds.top) / bounds.height - .5));
    art.style.setProperty('--tilt-y', `${(x * 12).toFixed(2)}deg`);
    art.style.setProperty('--tilt-x', `${(-y * 9).toFixed(2)}deg`);
    art.style.setProperty('--depth-x', `${(x * 15).toFixed(2)}px`);
    art.style.setProperty('--depth-y', `${(y * 12).toFixed(2)}px`);
  }, { passive: true });
  art.addEventListener('pointerleave', () => {
    for (const name of ['--tilt-y', '--tilt-x', '--depth-x', '--depth-y'])
      art.style.removeProperty(name);
  });
}

// A volumetric, perspective-projected ribbon sculpture (no third-party 3D
// package), paused off screen and replaced by a still frame for reduced motion.
mountDepthRibbons(document.querySelector('#stream-canvas'),
  document.querySelector('.relay-hero'), reducedMotion);
