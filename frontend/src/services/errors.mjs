/** Normalize non-JSON server failures without accidentally printing HTML or proxy pages. */
export function serverErrorMessage(status, raw, detail) {
  const detailText = typeof detail === 'string' ? detail
    : Array.isArray(detail) ? detail.map((item) => item?.msg || 'Invalid field').join('; ') : '';
  if (detailText.trim()) return detailText.slice(0, 1000);
  return `API returned HTTP ${status}${raw.trim() ? ' with a non-JSON response' : ' with an empty response'}. ` +
    'Check your FastAPI terminal for the underlying exception and verify that port 8000 is running.';
}
