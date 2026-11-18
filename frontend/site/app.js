import './config.js';
const repo = window.REPOLENS_CONFIG?.repositoryUrl;
if (repo && /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(repo)) {
  const footer = document.querySelector('[data-repository-footer]');
  if (footer) {
    const link = document.createElement('a');
    link.href = repo; link.className = 'text-link'; link.textContent = 'View source on GitHub ↗';
    footer.replaceWith(link);
  }
}
async function authJSON(path) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
    if (!response.ok) throw new Error('unavailable');
    return await response.json();
  } finally { clearTimeout(timer); }
}
const authPage = document.querySelector('[data-auth-page]');
if (authPage) {
  const status = document.querySelector('#auth-status');
  const errors = {
    provider_unavailable: 'This sign-in provider is not available yet. The site owner needs to finish OAuth setup.',
    signin_failed: 'Sign-in could not be completed. It may have expired or been cancelled. Please try again.',
    too_many_attempts: 'Too many unsuccessful sign-in attempts from this network. Try again in about 15 minutes.',
  };
  const params = new URLSearchParams(location.search);
  status.textContent = errors[params.get('error')] || (params.get('reason') === 'expired' ? 'Please sign in to open your workspace.' : 'Checking sign-in options…');
  const retry = document.querySelector('#provider-retry');
  let checking = false;
  async function loadProviders() {
    if (checking) return;
    checking = true;
    retry.disabled = true;
    status.textContent = 'Checking sign-in options…';
    for (const button of document.querySelectorAll('[data-provider]')) button.disabled = true;
    try {
      const data = await authJSON('/api/auth/providers');
      if (!data.providers || typeof data.providers.google !== 'boolean' || typeof data.providers.github !== 'boolean') throw new Error('invalid');
      let count = 0;
      for (const button of document.querySelectorAll('[data-provider]')) {
        const enabled = data.providers[button.dataset.provider] === true;
        button.disabled = !enabled;
        button.title = enabled ? '' : 'The site owner has not configured this provider yet.';
        if (enabled) count++;
      }
      if (!count) status.textContent = 'Google and GitHub sign-in are not configured yet. The site owner must add OAuth app credentials before accounts can be created.';
      else status.textContent = errors[params.get('error')] || (count === 2 ? 'Choose a provider to continue securely.' : 'One sign-in provider is available. The other is awaiting setup.');
    } catch (error) {
      status.textContent = error.name === 'AbortError'
        ? 'The sign-in service took too long to respond. Check that the server is running, then select Check again.'
        : 'The sign-in service is unavailable. Check that the server is running, then select Check again.';
    } finally { checking = false; retry.disabled = false; }
  }
  retry.addEventListener('click', loadProviders);
  for (const button of document.querySelectorAll('[data-provider]')) {
    button.addEventListener('click', () => {
      status.textContent = 'Opening secure sign-in…';
      const next=params.get('next')||'';
      location.assign('/api/auth/login/' + button.dataset.provider + (/^\/join\?token=[A-Za-z0-9_-]{20,200}$/.test(next)?'?next='+encodeURIComponent(next):''));
    });
  }
  loadProviders();
  authJSON('/api/auth/me')
    .then(data => {
      if (data.user?.id) {const next=params.get('next')||'';location.replace(/^\/join\?token=[A-Za-z0-9_-]{20,200}$/.test(next)?next:'/dashboard/');}
    }).catch(() => {});
}
