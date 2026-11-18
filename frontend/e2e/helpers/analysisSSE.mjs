/** Browser-test fixture for the real /api/analyze/stream contract. */
export function analysisSSE(report) {
  const events = [
    {status: 'progress', message: 'Analyzing repository source…'},
    {status: 'done', result: report},
  ];
  return events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('');
}
