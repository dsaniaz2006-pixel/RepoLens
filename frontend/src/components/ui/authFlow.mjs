// Keep authentication decisions tied to the server. The UI never invents an OAuth provider.
const JOIN_ROUTE = /^\/join\?token=[A-Za-z0-9_-]{20,200}$/;
const PROVIDERS = new Set(['google','github']);

export function allowedNext(next='') {
  return typeof next === 'string' && JOIN_ROUTE.test(next) ? next : '';
}
export function oauthLoginUrl(provider, next='') {
  if (!PROVIDERS.has(provider)) throw new Error('Unsupported provider');
  const validNext=allowedNext(next);
  return `/api/auth/login/${provider}${validNext?'?next='+encodeURIComponent(validNext):''}`;
}
export function postLoginRedirect(next='') {
  return allowedNext(next)||'/dashboard/';
}
export function getProviderAvailability(data) {
  const providers=data?.providers;
  if(!providers||typeof providers.google!=='boolean'||typeof providers.github!=='boolean') {
    throw new Error('Invalid provider configuration');
  }
  return {google:providers.google,github:providers.github};
}
export const AUTH_ERROR_MESSAGES = Object.freeze({
  provider_unavailable:'This sign-in provider is not available yet. The site owner needs to finish OAuth setup.',
  signin_failed:'Sign-in could not be completed. It may have expired or been cancelled. Please try again.',
  too_many_attempts:'Too many unsuccessful sign-in attempts. Try again in about 15 minutes.',
});
