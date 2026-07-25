import { useState, type ReactElement } from "react";
import type { CategoryRead, EntryCreateManual, TagRead } from "../../api/types";
import { CategoryPicker } from "../CategoryPicker/CategoryPicker";
import { TagEditor } from "../TagChip/TagEditor";
import { DateTimePicker } from "../DateTimePicker/DateTimePicker";
import styles from "./ManualEntryForm.module.css";

export interface ManualEntryFormValues extends Omit<EntryCreateManual, "tag_ids"> {
  tagNames: string[];
}

interface ManualEntryFormProps {
  categories: CategoryRead[];
  knownTags: TagRead[];
  /** `YYYY-MM-DDTHH:mm` defaults for the `DateTimePicker` start/end controls. */
  defaultStart: string;
  defaultEnd: string;
  onSubmit: (entry: ManualEntryFormValues) => Promise<void> | void;
  onCancel: () => void;
}

/** Full manual-entry form (title, notes, category, tags, start, end) — used for "Add a manual
 * entry" from the empty state and each Week/Month day group's "+ Add entry" affordance. */
export function ManualEntryForm({
  categories,
  knownTags,
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
    const startTs = new Date(start).toISOString();
    const endTs = new Date(end).toISOString();
    if (endTs < startTs) {
      setError("End must be after start.");
      return;
    }
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
        <TagEditor value={tagNames} onChange={setTagNames} knownTags={knownTags} />
      </div>
      <div className={styles.timesRow}>
        <DateTimePicker value={start} onChange={setStart} label="Start" />
        <DateTimePicker value={end} onChange={setEnd} label="End" />
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primaryButton}
          disabled={submitting}
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
