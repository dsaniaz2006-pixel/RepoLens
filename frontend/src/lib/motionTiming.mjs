/** RepoLens calm motion. 0.04s is a stagger BETWEEN items, not their total duration. */
export const REVEAL_STAGGER_MS = 40;
export const REVEAL_DURATION_MS = 950;
export const WELCOME_SCENE_DURATION_MS = 4200;
export const WELCOME_REDUCED_DURATION_MS = 500;
export const WELCOME_RING_HOLD_MS = 360;
export const WELCOME_MORPH_DURATION_MS = 2500;

export function revealDelayMs(index, groupSize = 8) {
  if (!Number.isFinite(index) || index < 0) return 0;
  return (Math.floor(index) % Math.max(1, Math.floor(groupSize))) * REVEAL_STAGGER_MS;
}

export function welcomeMorphProgress(elapsedMs, reducedMotion = false) {
  if (reducedMotion) return 1;
  const progress = Math.max(0, Math.min(1, (elapsedMs - WELCOME_RING_HOLD_MS) / WELCOME_MORPH_DURATION_MS));
  return 1 - Math.pow(1 - progress, 3); // slow, gentle settle
}
