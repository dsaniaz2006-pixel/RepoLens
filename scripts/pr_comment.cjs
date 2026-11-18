'use strict';
/**
 * GitHub Actions PR comment policy. Keep this dependency-free so the logic
 * can be unit tested without network or a GitHub token.
 */
const MARKER = '<!-- repolens-impact -->';
const AUTHOR = 'github-actions[bot]';
const MAX_REPORT = 60000;

function prepareComment(report) {
  if (typeof report !== 'string' || !report.trim()) {
    throw new Error('RepoLens did not produce a PR analysis report');
  }
  const clipped = report.length > MAX_REPORT;
  return MARKER + '\n' + report.slice(0, MAX_REPORT) +
    (clipped ? '\n\n_RepoLens comment truncated; inspect the full report artifact for complete coverage._' : '');
}

async function upsertComment(github, context, body) {
  const args = {
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: context.issue.number,
  };
  // Only update comments written by our own GitHub Actions bot; any bot can
  // post a similar marker and must not be a candidate for modification.
  const comments = await github.paginate(github.rest.issues.listComments, args);
  const old = comments.find(comment => comment.user?.login === AUTHOR &&
    typeof comment.body === 'string' && comment.body.startsWith(MARKER));
  if (old) {
    return github.rest.issues.updateComment({
      owner: args.owner, repo: args.repo, comment_id: old.id, body,
    });
  }
  return github.rest.issues.createComment({...args, body});
}
module.exports = {MARKER, AUTHOR, MAX_REPORT, prepareComment, upsertComment};
