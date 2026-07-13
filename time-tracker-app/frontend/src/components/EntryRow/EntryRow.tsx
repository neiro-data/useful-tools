import { useState, type ReactElement } from "react";
import type { CategoryRead, EntryRead, TagRead } from "../../api/types";
import { CategoryChip } from "../CategoryChip/CategoryChip";
import { CategoryPicker } from "../CategoryPicker/CategoryPicker";
import { TagChip } from "../TagChip/TagChip";
import { TagEditor } from "../TagChip/TagEditor";
import { formatDurationMinutes } from "../../utils/duration";
import { categoryColorVar } from "../../utils/categoryColor";
import styles from "./EntryRow.module.css";

export interface EntryRowSaveValues {
  title: string;
  category: CategoryRead | null;
  tagNames: string[];
}

interface EntryRowProps {
  entry: EntryRead;
  categories: CategoryRead[];
  knownTags: TagRead[];
  /** Renders the accent (not category) color bar + pulse — this is the live running entry. */
  isRunning?: boolean;
  onSave: (values: EntryRowSaveValues) => Promise<void> | void;
  onDelete: () => Promise<void> | void;
}

/** The core repeating row used identically on Today, Week, and Month (`design/screens.md` §8.3 /
 * §3). Single-line view state; expands into an inline edit form on click/Enter. */
export function EntryRow({
  entry,
  categories,
  knownTags,
  isRunning = false,
  onSave,
  onDelete,
}: EntryRowProps): ReactElement {
  const [mode, setMode] = useState<"view" | "edit" | "confirm-delete">("view");
  const [title, setTitle] = useState(entry.title);
  const [category, setCategory] = useState<CategoryRead | null>(entry.category);
  const [tagNames, setTagNames] = useState<string[]>(entry.tags.map((tag) => tag.name));
  const [saving, setSaving] = useState(false);

  function startEdit(): void {
    setTitle(entry.title);
    setCategory(entry.category);
    setTagNames(entry.tags.map((tag) => tag.name));
    setMode("edit");
  }

  async function save(): Promise<void> {
    setSaving(true);
    try {
      await onSave({ title, category, tagNames });
      setMode("view");
    } finally {
      setSaving(false);
    }
  }

  const barColor = isRunning ? "var(--color-accent)" : categoryColorVar(entry.category?.color);

  if (mode === "confirm-delete") {
    return (
      <div className={styles.row} data-testid="entry-row">
        <span className={styles.bar} style={{ background: barColor }} aria-hidden="true" />
        <div className={styles.confirmBar}>
          <span>Delete "{entry.title}"?</span>
          <div className={styles.confirmActions}>
            <button type="button" className={styles.dangerButton} onClick={() => void onDelete()}>
              Yes, delete
            </button>
            <button type="button" className={styles.secondaryButton} onClick={() => setMode("view")}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "edit") {
    return (
      <div className={styles.row} data-testid="entry-row">
        <span className={styles.bar} style={{ background: barColor }} aria-hidden="true" />
        <div
          className={styles.editForm}
          onKeyDown={(event) => {
            if (event.key === "Escape") setMode("view");
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void save();
          }}
        >
          <input
            className={styles.titleInput}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            aria-label="Entry title"
            autoFocus
          />
          <div className={styles.editMeta}>
            <CategoryPicker categories={categories} value={category} onChange={setCategory} />
            <TagEditor value={tagNames} onChange={setTagNames} knownTags={knownTags} />
          </div>
          <div className={styles.editActions}>
            <button
              type="button"
              className={styles.primaryButton}
              disabled={saving}
              onClick={() => void save()}
            >
              Save
            </button>
            <button type="button" className={styles.secondaryButton} onClick={() => setMode("view")}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={styles.row}
      data-testid="entry-row"
      tabIndex={0}
      role="button"
      onClick={startEdit}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === "e" || event.key === "E") startEdit();
        if (event.key === "Backspace" || event.key === "Delete") setMode("confirm-delete");
      }}
    >
      <span className={styles.bar} style={{ background: barColor }} aria-hidden="true" />
      <span className={styles.title}>{entry.title}</span>
      {entry.category && <CategoryChip category={entry.category} />}
      <span className={styles.tags}>
        {entry.tags.map((tag) => (
          <TagChip key={tag.id} name={tag.name} />
        ))}
      </span>
      <span className={styles.duration}>
        {isRunning ? "…" : formatDurationMinutes(entry.duration_minutes)}
      </span>
      <button
        type="button"
        className={styles.menuButton}
        aria-label={`Actions for ${entry.title}`}
        onClick={(event) => {
          event.stopPropagation();
          setMode("confirm-delete");
        }}
      >
        ⋯
      </button>
    </div>
  );
}
