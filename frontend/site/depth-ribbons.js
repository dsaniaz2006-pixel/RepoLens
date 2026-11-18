/**
 * Original perspective-projected light sculpture for the public RepoLens hero.
 * No WebGL, remote assets or network requests: the strands are a 3D parametric
 * tube projected onto a small 2D canvas. This is decorative, not a source map.
 */
export function mountDepthRibbons(canvas, hero, reducedMotion) {
  if (!canvas || !hero) return () => {};
  const ctx = canvas.getContext('2d', { alpha: true });
  if (!ctx) return () => {};

  const STRANDS = 52;
  const STEPS = 46;
  const staticMode = reducedMotion.matches;
  let width = 1;
  let height = 1;
  let frame = 0;
  let raf = 0;
  let visible = true;
  let lastTime = 0;
  let stopped = false;

  const bezier = (a, b, c, d, t) => {
    const u = 1 - t;
    return u*u*u*a + 3*u*u*t*b + 3*u*t*t*c + t*t*t*d;
  };
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
  const hash = n => (Math.sin(n * 127.1 + 24.31) * 43758.5453) % 1;
  const point = (arm, t, strand, time) => {
    // The light comes together at a small portal and spreads in 3D, like the
    // Relay reference recording. Coordinates are normalized so resizing works.
    const x = arm === 0
      ? bezier(.48, .37, .78, .78, t)
      : bezier(.48, .46, .92, 1.15, t);
    const y = arm === 0
      ? bezier(.61, .31, .36, -.22, t)
      : bezier(.61, .76, .65, 1.15, t);
    const theta = (strand / STRANDS) * Math.PI * 2 + t * (arm ? 2.6 : -3.2) + time * .045;
    const radius = (4 + 70 * Math.pow(t, .75)) * Math.min(1, width / 1440 * 1.4);
    const depth = Math.sin(theta) * radius;
    const perspective = 1 / (1 - depth / 850);
    const roll = Math.cos(theta) * radius * .68;
    const wobble = Math.sin(6 * t + time * .18 + strand * .07) * t * 7;
    const px = (x * width + roll - width * .48) * perspective + width * .48;
    const py = (y * height + Math.sin(theta) * radius * .31 + wobble - height * .61) * perspective + height * .61;
    return { x: px, y: py, front: clamp((depth / 85 + 1) * .5, 0, 1), perspective };
  };

  function glow() {
    ctx.globalCompositeOperation = 'screen';
    const originX = width * .48;
    const originY = height * .61;
    const halo = ctx.createRadialGradient(originX, originY, 0, originX, originY, width * .21);
    halo.addColorStop(0, 'rgba(117,200,255,.23)');
    halo.addColorStop(.12, 'rgba(64,148,215,.16)');
    halo.addColorStop(.43, 'rgba(36,103,161,.065)');
    halo.addColorStop(1, 'rgba(28,78,127,0)');
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, width, height);

    // The tilted elliptical portal gives the light a visible point of origin.
    ctx.save();
    ctx.translate(originX, originY);
    ctx.rotate(-.62);
    ctx.scale(.32, 1);
    const ring = ctx.createRadialGradient(0, 0, 4, 0, 0, 34);
    ring.addColorStop(0, 'rgba(208,239,255,.20)');
    ring.addColorStop(.42, 'rgba(106,186,242,.30)');
    ring.addColorStop(.66, 'rgba(86,158,219,.09)');
    ring.addColorStop(1, 'rgba(83,145,191,0)');
    ctx.fillStyle = ring;
    ctx.beginPath(); ctx.arc(0, 0, 34, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(158,215,251,.27)';
    ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.ellipse(0, 0, 25, 16, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }

  function drawArm(arm, time) {
    // A depth-sorted set of filament strands: distant strands are softer,
    // closer strands are brighter, while the radial twist adds real parallax.
    const order = Array.from({ length: STRANDS }, (_, i) => i)
      .sort((a, b) => Math.sin(a / STRANDS * Math.PI * 2) - Math.sin(b / STRANDS * Math.PI * 2));
    for (const strand of order) {
      const phase = strand / STRANDS * Math.PI * 2;
      const front = (Math.sin(phase) + 1) / 2;
      const highlight = strand % 11 === 0;
      const strength = (highlight ? .4 : .18) * (.55 + .45 * front);
      const gradient = ctx.createLinearGradient(width * .48, height * .61,
        width * (arm ? 1.04 : .76), height * (arm ? 1.08 : -.08));
      gradient.addColorStop(0, `rgba(182,230,255,${strength * .9})`);
      gradient.addColorStop(.33, `rgba(100,185,243,${strength})`);
      gradient.addColorStop(.75, `rgba(63,131,208,${strength * .68})`);
      gradient.addColorStop(1, 'rgba(43,102,168,0)');
      ctx.strokeStyle = gradient;
      ctx.lineWidth = (highlight ? 1.65 : .7) * (.85 + front * .5);
      ctx.shadowBlur = highlight ? 8 : 0;
      ctx.shadowColor = highlight ? 'rgba(81,169,231,.6)' : 'rgba(49,119,180,.2)';
      ctx.beginPath();
      for (let step = 0; step <= STEPS; step++) {
        const t = step / STEPS;
        const p = point(arm, t, strand, time);
        if (!step) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
  }

  function sparks(time) {
    // Deterministic points travel along the ribbons at staggered speeds.
    for (let i = 0; i < 40; i++) {
      const arm = i % 2;
      const t = (i / 40 + time * (.014 + (i % 5) * .004)) % 1;
      const p = point(arm, t, (i * 17) % STRANDS, time);
      const twinkle = .38 + .35 * Math.cos(i * 2.73 + time * 1.1);
      const radius = i % 9 === 0 ? 1.65 : .7;
      const alpha = clamp((.72 - Math.abs(t - .43) * .6) * twinkle, .08, .55);
      ctx.fillStyle = `rgba(164,219,255,${alpha})`;
      ctx.beginPath();ctx.arc(p.x, p.y, radius, 0, Math.PI*2);ctx.fill();
    }
  }

  function draw(time = 0) {
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    glow();
    drawArm(0, time);
    drawArm(1, time);
    sparks(time);
    ctx.restore();
  }

  function resize() {
    const bounds = hero.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = Math.max(bounds.width, 1);
    height = Math.max(bounds.height, 1);
    canvas.width = Math.max(1, Math.round(width * dpr));
    canvas.height = Math.max(1, Math.round(height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw(frame);
  }

  function tick(timestamp) {
    raf = 0;
    if (stopped || staticMode || document.hidden || !visible) return;
    if (!lastTime) lastTime = timestamp;
    // Cap animation to ~24 fps; a static fallback is always available.
    if (timestamp - lastTime > 40) {
      frame += Math.min((timestamp - lastTime) / 1000, .06);
      lastTime = timestamp;
      draw(frame);
    }
    raf = window.requestAnimationFrame(tick);
  }
  function start() {
    if (!stopped && !staticMode && !raf && !document.hidden && visible) {
      lastTime = 0;
      raf = window.requestAnimationFrame(tick);
    }
  }
  function stop() {
    if (raf) window.cancelAnimationFrame(raf);
    raf = 0;
  }
  const visibility = () => document.hidden ? stop() : start();
  window.addEventListener('resize', resize, { passive: true });
  document.addEventListener('visibilitychange', visibility);
  let observer;
  if ('IntersectionObserver' in window) {
    observer = new IntersectionObserver(entries => {
      visible = entries[0]?.isIntersecting ?? true;
      if (visible) start(); else stop();
    }, { threshold: .01 });
    observer.observe(hero);
  }
  resize();
  start();
  return () => {
    stopped = true;
    stop();
    observer?.disconnect();
    window.removeEventListener('resize', resize);
    document.removeEventListener('visibilitychange', visibility);
  };
}
