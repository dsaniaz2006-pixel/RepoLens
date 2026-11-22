/**
 * Deterministic browser-test API boundary.
 *
 * The workspace renders its Home/usage panel before Playwright clicks a tab.
 * A live /api/usage 401 would otherwise redirect the test to /login/, even if
 * /api/auth/me itself was mocked. Keep all initial authenticated GETs local to
 * the test, while never disabling the real app's session-expiry handling.
 *
 * Register this default route BEFORE test-specific routes: Playwright runs
 * newer matching routes first, so individual tests can safely override it.
 */
export const DEFAULT_WORKSPACE_USAGE = Object.freeze({
  plan: 'free',
  reset_at: 1890000000,
  usage: {
    analyze: {used: 0, limit: 5},
    ask: {used: 0, limit: 20},
    index: {used: 0, limit: 2},
  },
});

export function workspaceMockResponse(path, {user, csrfToken} = {}) {
  switch (path) {
    case '/api/auth/me':
      return {status: 200, json: {user: user || {id: 'ui-dev', name: 'Test user'}, csrf_token: csrfToken || 'test-csrf'}};
    case '/api/history':
    case '/api/repositories':
    case '/api/workspaces':
    case '/api/conversations':
    case '/api/insights/diff':
    case '/api/insights/security':
    case '/api/insights/checklist':
    case '/api/insights/flow':
      return {status: 200, json: []};
    case '/api/usage':
      return {status: 200, json: DEFAULT_WORKSPACE_USAGE};
    case '/api/config-status':
      return {status: 200, json: {
        model_provider: 'gemini', gemini_key_configured: true,
        github_token_configured: true, message: 'Configured on server',
      }};
    case '/api/auth/keys':
      return {status: 200, json: {keys: []}};
    case '/api/auth/sessions':
      return {status: 200, json: {sessions: []}};
    case '/api/auth/audit':
      return {status: 200, json: {events: []}};
    default:
      return null;
  }
}

export async function mockAuthenticatedWorkspace(page, options = {}) {
  const unexpected = [];
  await page.route('**/api/**', route => {
    if (route.request().url().includes('/api/health')) return route.fulfill({ json: { status: 'ok' } });
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const response = request.method() === 'GET'
      ? workspaceMockResponse(path, options)
      : null;
    if (response) return route.fulfill(response);
    // Unexpected calls fail visibly instead of touching a real backend and
    // causing a misleading auth redirect. No fake success for untested APIs.
    unexpected.push(`${request.method()} ${path}`);
    return route.fulfill({status: 501, json: {detail: `Unmocked workspace test request: ${request.method()} ${path}`}});
  });
  return unexpected;
}
