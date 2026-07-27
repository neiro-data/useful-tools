import { useState, type ReactElement } from "react";
import type { CategoryRead, EntryCreateManual, TagRead } from "../../api/types";
import { CategoryPicker } from "../CategoryPicker/CategoryPicker";
import { TagEditor } from "../TagChip/TagEditor";
import { DateTimePicker } from "../DateTimePicker/DateTimePicker";
import { timeRangeError } from "../../utils/timeRange";
import styles from "./ManualEntryForm.module.css";

export interface ManualEntryFormValues extends Omit<EntryCreateManual, "tag_ids"> {
  tagNames: string[];
}

interface ManualEntryFormProps {
  categories: CategoryRead[];
  knownTags: TagRead[];
  /** Recently-used tag names, most-recent first, for `TagEditor`'s "Recent" section. Omit to fall
   * back to `TagEditor`'s default (filter-only) behavior. */
  recentTags?: TagRead[] | undefined;
  /** `YYYY-MM-DDTHH:mm` defaults for the `DateTimePicker` start/end controls. */
  defaultStart: string;
  defaultEnd: string;
  onSubmit: (entry: ManualEntryFormValues) => Promise<void> | void;
  onCancel: () => void;
}

/** Full manual-entry form (title, notes, category, tags, start, end) — used for "Add a manual
 * entry" from the empty state and each Week/Month day group's "+ Add entry" affordance.
 *
 * `defaultStart`/`defaultEnd` are only read as *initial* state: on a successful submit, the form
 * resets every field (title/notes/category/tags) and re-seeds start/end from the (possibly
 * updated) props, rather than leaving stale values behind. This matters because the empty-state
 * instance on Today stays mounted across submits, so without an explicit reset the next entry
 * would silently start pre-filled with the previous one's title/category/tags. `formKey` is bumped
 * on every successful submit and passed as `TagEditor`'s `key`, forcing it to remount with a clean
 * internal draft — `tagNames` alone resetting to `[]` doesn't clear `TagEditor`'s own in-progress
 * (uncommitted) input text. */
export function ManualEntryForm({
  categories,
  knownTags,
  recentTags,
  defaultStart,
  defaultEnd,
  onSubmit,
  onCancel,
}: ManualEntryFormProps): ReactElement {
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [category, setCategory] = useState<CategoryRead | null>(null);
  const [tagNames, setTagNames] = useState<string[]>([]);
  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultEnd);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formKey, setFormKey] = useState(0);

  // Live, so the message appears as soon as the pickers cross over rather than only on Save —
  // and so the Save button can be disabled while the range is impossible.
  const rangeError = timeRangeError(start, end);

  async function handleSubmit(): Promise<void> {
    setError(null);
    if (title.trim().length === 0) {
      setError("Title is required.");
      return;
    }
    if (category === null) {
      setError("Category is required.");
      return;
    }
    if (rangeError !== null) {
      setError(rangeError);
      return;
    }
    const startTs = new Date(start).toISOString();
    const endTs = new Date(end).toISOString();
    setSubmitting(true);
    try {
      await onSubmit({
        title: title.trim(),
        notes: notes.trim().length > 0 ? notes.trim() : null,
        category_id: category.id,
        tagNames,
        start_ts: startTs,
        end_ts: endTs,
      });
      setTitle("");
      setNotes("");
      setCategory(null);
      setTagNames([]);
      setError(null);
      setStart(defaultStart);
      setEnd(defaultEnd);
      setFormKey((key) => key + 1);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.form}>
      <input
        className={styles.titleInput}
        placeholder="Entry title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        aria-label="Manual entry title"
        autoFocus
      />
      {/* User-facing label is "Comment"; the prop/wire field stays `notes` (see `app/schemas.py`) —
       * deliberate naming mismatch, not a bug. */}
      <textarea
        className={styles.notesInput}
        placeholder="Comment (optional)"
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        aria-label="Manual entry comment"
      />
      <div className={styles.metaRow}>
        <CategoryPicker categories={categories} value={category} onChange={setCategory} required />
        <TagEditor
          key={formKey}
          value={tagNames}
          onChange={setTagNames}
          knownTags={knownTags}
          recentTags={recentTags}
        />
      </div>
      <div className={styles.timesRow}>
        <DateTimePicker value={start} onChange={setStart} label="Start" />
        <DateTimePicker value={end} onChange={setEnd} label="End" />
      </div>
      {(error ?? rangeError) && (
        <p className={styles.error} role="alert">
          {error ?? rangeError}
        </p>
      )}
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primaryButton}
          disabled={submitting || rangeError !== null}
          onClick={() => void handleSubmit()}
        >
          Save
        </button>
        <button type="button" className={styles.secondaryButton} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
