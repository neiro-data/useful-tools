import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import type { TagRead } from "../../api/types";
import { TagChip } from "./TagChip";
import styles from "./TagEditor.module.css";

interface TagEditorProps {
  /** Currently-applied tags, by name (new, not-yet-created names are allowed). */
  value: string[];
  onChange: (names: string[]) => void;
  knownTags?: TagRead[];
  /** Recently-used tags, most-recent first (e.g. `/today`'s `recent_tags`, or
   * `recentTagsFromEntries` for Week/Month). When provided, focusing the input while the draft is
   * empty shows a "Recent" section (already-applied tags excluded, capped at 8) instead of no
   * suggestions at all. Omit to fall back to exactly the filter-only behavior below. */
  recentTags?: TagRead[] | undefined;
  placeholder?: string;
}

const RECENT_LIMIT = 8;

interface DropdownOption {
  name: string;
  id: number | null;
}

/** Free-text tag input with autocomplete against existing tags (`design/screens.md` §1.3):
 * `Enter` or `,` commits a chip; unknown text is allowed and creates a new tag on save.
 *
 * Two complementary suggestion surfaces: typing filters `knownTags` (unchanged from the original
 * behavior); a `▾` toggle beside the input opens the full known-tag list (alphabetical, scrollable)
 * regardless of the draft. When `recentTags` is supplied, focusing the input with an empty draft
 * additionally surfaces a "Recent" section so a frequently-used tag doesn't need to be retyped. */
export function TagEditor({
  value,
  onChange,
  knownTags = [],
  recentTags,
  placeholder = "#tag input…",
}: TagEditorProps): ReactElement {
  const [draft, setDraft] = useState("");
  const [inputFocused, setInputFocused] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();

  const appliedLower = new Set(value.map((name) => name.toLowerCase()));

  const filteredSuggestions: DropdownOption[] =
    draft.trim().length > 0
      ? knownTags
          .filter(
            (tag) =>
              tag.name.toLowerCase().includes(draft.trim().toLowerCase()) &&
              !appliedLower.has(tag.name.toLowerCase()),
          )
          .slice(0, 5)
          .map((tag) => ({ name: tag.name, id: tag.id }))
      : [];

  const recentSuggestions: DropdownOption[] =
    draft.trim().length === 0 && recentTags !== undefined
      ? dedupeCaseInsensitive(recentTags.filter((tag) => !appliedLower.has(tag.name.toLowerCase())))
          .slice(0, RECENT_LIMIT)
          .map((tag) => ({ name: tag.name, id: tag.id }))
      : [];

  const knownListOptions: DropdownOption[] = knownTags
    .filter((tag) => !appliedLower.has(tag.name.toLowerCase()))
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((tag) => ({ name: tag.name, id: tag.id }));

  // Precedence: the full-list dropdown (explicit `▾` toggle) wins over the implicit
  // filter/recent suggestions, which are mutually exclusive by construction (draft empty vs not).
  const visibleOptions: DropdownOption[] = dropdownOpen
    ? knownListOptions
    : inputFocused
      ? draft.trim().length > 0
        ? filteredSuggestions
        : recentSuggestions
      : [];
  const showRecentHeading = !dropdownOpen && draft.trim().length === 0 && recentSuggestions.length > 0;
  const listVisible = visibleOptions.length > 0;

  useEffect(() => {
    setActiveIndex(-1);
  }, [draft, dropdownOpen, inputFocused]);

  useEffect(() => {
    function onOutsideClick(event: MouseEvent): void {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
        setInputFocused(false);
      }
    }
    document.addEventListener("mousedown", onOutsideClick);
    return () => document.removeEventListener("mousedown", onOutsideClick);
  }, []);

  function commit(name: string): void {
    const trimmed = name.trim().replace(/^#/, "");
    if (trimmed.length === 0 || appliedLower.has(trimmed.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...value, trimmed]);
    setDraft("");
    setDropdownOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown" && listVisible) {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % visibleOptions.length);
      return;
    }
    if (event.key === "ArrowUp" && listVisible) {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? visibleOptions.length - 1 : index - 1));
      return;
    }
    if (event.key === "Escape") {
      if (dropdownOpen || listVisible) {
        event.preventDefault();
        setDropdownOpen(false);
        setActiveIndex(-1);
      }
      return;
    }
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      const active = activeIndex >= 0 ? visibleOptions[activeIndex] : undefined;
      commit(active ? active.name : draft);
      return;
    }
    if (event.key === "Backspace" && draft.length === 0 && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className={styles.root} ref={rootRef}>
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
          onFocus={() => setInputFocused(true)}
          placeholder={placeholder}
          aria-label="Add tag"
          role="combobox"
          aria-expanded={listVisible}
          aria-controls={listboxId}
          aria-autocomplete="list"
          // Focus never leaves the input while arrowing through the list (that's what makes the
          // existing Enter/`,`/Backspace semantics keep working), so the highlighted option is only
          // discoverable to assistive tech via aria-activedescendant. Without it, ArrowDown moves a
          // purely visual highlight and a screen-reader user hears nothing.
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined
          }
        />
        {knownTags.length > 0 && (
          <button
            type="button"
            className={styles.dropdownToggle}
            aria-label={dropdownOpen ? "Hide all tags" : "Show all tags"}
            aria-expanded={dropdownOpen}
            onClick={() => setDropdownOpen((open) => !open)}
          >
            ▾
          </button>
        )}
      </div>
      {/* The `<li>` wrappers below carry role="presentation" so the listbox's only ARIA children
       * are the options themselves — a bare `<li>` in between breaks the listbox -> option
       * parent/child relationship assistive tech walks. The "Recent" heading is presentational for
       * the same reason. */}
      {listVisible && (
        <ul id={listboxId} className={styles.suggestions} role="listbox">
          {showRecentHeading && (
            <li className={styles.suggestionsHeading} role="presentation">
              Recent
            </li>
          )}
          {visibleOptions.map((option, index) => (
            <li key={option.id ?? option.name} role="presentation">
              <button
                type="button"
                id={`${listboxId}-option-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                className={index === activeIndex ? styles.optionActive : undefined}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => commit(option.name)}
              >
                #{option.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Case-insensitive de-dupe that keeps the first occurrence (recents are already most-recent
 * first, so "first" is "most recent"). */
function dedupeCaseInsensitive(tags: TagRead[]): TagRead[] {
  const seen = new Set<string>();
  const deduped: TagRead[] = [];
  for (const tag of tags) {
    const key = tag.name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(tag);
  }
  return deduped;
}
