// Dashboard sections are views, not scroll-snapped pages or URL routes.
export const WORKSPACE_PAGES = Object.freeze([
  'Home', 'Analyze Repo', 'Knowledge Hub', 'Conversations',
  'Past Analyses', 'Settings', 'Public Gallery',
]);
export function isWorkspacePage(value) {
  return typeof value === 'string' && WORKSPACE_PAGES.includes(value);
}
export function nextWorkspacePage(current, requested) {
  return isWorkspacePage(requested) ? requested : current;
}
