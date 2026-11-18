/** Immutable local state transition for the assigned-onboarding checkbox. */
export function setAssignmentTask(rows, assignmentId, taskId, done) {
  return rows.map(row => row.id === assignmentId ? {
    ...row,
    data: {
      ...row.data,
      snapshot: {
        ...row.data.snapshot,
        tasks: (row.data.snapshot?.tasks || []).map(task => task.id === taskId ? {...task, done} : task)
      }
    }
  } : row);
}
