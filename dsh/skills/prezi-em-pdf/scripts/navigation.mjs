// Navigation is separate from the browser so stop conditions can be tested deterministically.
export async function captureFrames({ first, next, isBlank, save, maxPages, deadlineMs,
  noChangeStreak, isTerminal = async () => false, isDuplicate, now = Date.now }) {
  const startedAt = now();
  let count = 1, last = first, duplicates = 0;
  let returnedToStart = false, lastWasDuplicate = false;
  const seen = [first];
  const findExactDuplicate = frame => seen.findIndex(previous => Buffer.compare(previous, frame) === 0);
  const finish = (stopReason, completed = false, completionEvidence = undefined) => ({
    completed, stopReason,
    ...(completionEvidence ? { completionEvidence } : {}),
    durationMs: now() - startedAt, frameCount: count,
  });
  await save(0, first);
  for (let index = 1; index < maxPages; index++) {
    if (now() - startedAt >= deadlineMs) return finish('deadline');
    if (await isTerminal()) return finish('viewer-end', true, 'viewer-next-disabled');
    const step = await next(index);
    if (step?.terminal) {
      return finish('viewer-restart', true, 'viewer-restart-visible');
    }
    const frame = step?.frame ?? step;
    if (!frame) return finish(returnedToStart ? 'returned-to-start' : 'empty-frame');
    // A blank frame interrupts a consecutive frozen-frame sequence.
    if (isBlank(frame)) { duplicates = 0; continue; }
    if (Buffer.compare(last, frame) === 0) {
      duplicates++;
      if (duplicates >= noChangeStreak) {
        return count > 1 && !returnedToStart && !lastWasDuplicate
          ? finish('stable-viewer-terminal', true, 'five-identical-frames-after-navigation')
          : finish(returnedToStart ? 'returned-to-start' : lastWasDuplicate ? 'repeated-view-stall' : 'no-navigation');
      }
      continue;
    }
    duplicates = 0;
    const duplicateIndex = isDuplicate
      ? await isDuplicate(frame, seen)
      : findExactDuplicate(frame);
    if (Number.isInteger(duplicateIndex) && duplicateIndex >= 0) {
      returnedToStart = duplicateIndex === 0;
      lastWasDuplicate = true;
      last = frame;
      continue;
    }
    returnedToStart = false;
    lastWasDuplicate = false;
    await save(index, frame);
    seen.push(frame);
    last = frame;
    count++;
  }
  return finish('max-pages');
}
