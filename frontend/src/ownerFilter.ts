/** The owner-filter value a page should start with for a given role,
 * before the viewer has touched the control — shared across
 * TasksPage/PipelinePage/ContactsListPage so the three pages can't
 * silently drift apart on this. Admin defaults to "Everyone" (the
 * tenant-wide view is what an admin most often wants); manager stays
 * defaulted to "Mine" (their own queue is still the thing they check
 * first) — counselor's is ignored since OwnerFilter renders nothing
 * for them and their list is always implicitly their own. */
export function defaultOwnerFilterValue(role: string, meId: string): string | undefined {
  if (role === "admin") {
    return undefined;
  }
  return meId;
}
