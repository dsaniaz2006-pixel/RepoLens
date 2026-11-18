/**
 * Proxy only the invitation exchange route, never public assets such as
 * /join.html and /join.js. Vite's plain '/join' prefix also matches both,
 * which causes 500 proxy failures when FastAPI is not running.
 *
 * The token-bearing /join?token=... path is deliberately served by FastAPI.
 */
export const JOIN_PROXY_PATTERN = '^/join(?:\\?|$)';
