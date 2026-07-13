import { useState, type KeyboardEvent, type ReactElement } from "react";
import type { TagRead } from "../../api/types";
import { TagChip } from "./TagChip";
import styles from "./TagEditor.module.css";

interface TagEditorProps {
  /** Currently-applied tags, by name (new, not-yet-created names are allowed). */
  value: string[];
  onChange: (names: string[]) => void;
  knownTags?: TagRead[];
  placeholder?: string;
}

/** Free-text tag input with autocomplete against existing tags (`design/screens.md` §1.3):
 * `Enter` or `,` commits a chip; unknown text is allowed and creates a new tag on save. */
export function TagEditor({
  value,
  onChange,
  knownTags = [],
  placeholder = "#tag input…",
}: TagEditorProps): ReactElement {
  const [draft, setDraft] = useState("");

  const suggestions =
    draft.trim().length > 0
      ? knownTags
          .filter(
            (tag) => tag.name.toLowerCase().includes(draft.trim().toLowerCase()) && !value.includes(tag.name),
          )
          .slice(0, 5)
      : [];

  function commit(name: string): void {
    const trimmed = name.trim().replace(/^#/, "");
    if (trimmed.length === 0 || value.includes(trimmed)) {
      setDraft("");
      return;
    }
    onChange([...value, trimmed]);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit(draft);
    } else if (event.key === "Backspace" && draft.length === 0 && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.chips}>
        {value.map((name) => (
          <TagChip
            key={name}
            name={name}
            removable
            onRemove={() => onChange(value.filter((n) => n !== name))}
          />
        ))}
        <input
          className={styles.input}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          aria-label="Add tag"
        />
      </div>
      {suggestions.length > 0 && (
        <ul className={styles.suggestions} role="listbox">
          {suggestions.map((tag) => (
            <li key={tag.id}>
              <button type="button" onClick={() => commit(tag.name)}>
                #{tag.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
