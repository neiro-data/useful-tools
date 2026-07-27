import { useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import type { CategoryRead, EntryRead, TagRead } from "../../api/types";
import { CategoryPicker } from "../CategoryPicker/CategoryPicker";
import { TagEditor } from "../TagChip/TagEditor";
import { RecentChipsRail } from "../RecentChipsRail/RecentChipsRail";
import { DateTimePicker } from "../DateTimePicker/DateTimePicker";
import { useLiveTimer } from "../../hooks/useLiveTimer";
import { formatElapsedSeconds } from "../../utils/duration";
import { timeRangeError, toLocalDateTimeInput } from "../../utils/timeRange";
import styles from "./TimerWidget.module.css";

export interface StartPayload {
  title: string;
  category: CategoryRead;
  tagNames: string[];
  /** Backs the API's `notes` field; labelled "Comment" in the UI (see component doc comment). */
  notes: string | null;
}

interface TimerWidgetProps {
  runningEntry: EntryRead | null;
  categories: CategoryRead[];
  knownTags: TagRead[];
  recentCategories: CategoryRead[];
  recentTags: TagRead[];
  onStart: (payload: StartPayload) => Promise<void> | void;
  onStop: () => Promise<void> | void;
  onUpdateRunning: (payload: StartPayload) => Promise<void> | void;
  onManualAdd: (payload: StartPayload & { startTs: string; endTs: string }) => Promise<void> | void;
  starting?: boolean;
}

/** Normalizes a free-text comment input to `null` when blank, so we never send `notes: ""`.
 * For use on SUBMIT (quick-add / manual save), where trimming is what you want. */
function normalizeNotes(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/** Per-keystroke variant for the running-timer comment, which is a controlled input whose value
 * comes straight back from the server on every change. Trimming here would delete a space the
 * moment it is typed (the round-tripped value replaces the input's contents), making multi-word
 * comments impossible to enter — so only a truly empty string collapses to `null`. */
function normalizeNotesLive(value: string): string | null {
  return value.length > 0 ? value : null;
}

/** Today's hero card (`design/screens.md` §1.1/§1.2/§8.4): idle quick-add form vs running timer,
 * in one component since they're mutually exclusive render modes of the same card.
 *
 * User-facing copy calls the free-text field "Comment", but it's wired to the API/prop field
 * `notes` (see `app/schemas.py`) — the label/field-name mismatch is deliberate, not a bug. */
export function TimerWidget({
  runningEntry,
  categories,
  knownTags,
  recentCategories,
  recentTags,
  onStart,
  onStop,
  onUpdateRunning,
  onManualAdd,
  starting = false,
}: TimerWidgetProps): ReactElement {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<CategoryRead | null>(null);
  const [tagNames, setTagNames] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [manualMode, setManualMode] = useState(false);
  const [manualStart, setManualStart] = useState(() => defaultManualStart());
  const [manualEnd, setManualEnd] = useState(() => toLocalDateTimeInput(new Date()));
  // Bumped after every successful start/manual-save so `TagEditor` remounts with a clean internal
  // draft — `tagNames` alone resetting to `[]` doesn't clear its own in-progress input text (see
  // `ManualEntryForm`'s `formKey` for the same pattern).
  const [formKey, setFormKey] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const elapsed = useLiveTimer(runningEntry?.start_ts);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const target = event.target as HTMLElement;
    // Recent-category (1-6) and recent-tag (Shift+1-6) shortcuts must only fire when focus is
    // NOT inside a field — otherwise typing a digit into the quick-add title, comment, or the
    // manual date/time pickers gets hijacked instead of entering that character. Bail out for
    // every key (not just digits) whenever the event originates from an editable control.
    const isFieldTarget =
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable;
    if (isFieldTarget) return;

    if (!event.shiftKey && event.key >= "1" && event.key <= "6") {
      const index = Number(event.key) - 1;
      const picked = recentCategories[index];
      if (picked) {
        event.preventDefault();
        setCategory(picked);
      }
    } else if (event.shiftKey && event.key >= "1" && event.key <= "6") {
      const index = Number(event.key) - 1;
      const picked = recentTags[index];
      if (picked) {
        event.preventDefault();
        setTagNames((prev) => (prev.includes(picked.name) ? prev : [...prev, picked.name]));
      }
    }
  }

  const canStart = title.trim().length > 0 && category !== null;
  // Only meaningful in manual mode — starting a timer has no end time to cross over.
  const manualRangeError = manualMode ? timeRangeError(manualStart, manualEnd) : null;
  const canSaveManual = canStart && manualRangeError === null;

  async function handleStart(): Promise<void> {
    if (title.trim().length === 0 || category === null) return;
    await onStart({ title: title.trim(), category, tagNames, notes: normalizeNotes(notes) });
    setTitle("");
    setCategory(null);
    setTagNames([]);
    setNotes("");
    setFormKey((key) => key + 1);
  }

  async function handleManualSave(): Promise<void> {
    if (title.trim().length === 0 || category === null) return;
    if (timeRangeError(manualStart, manualEnd) !== null) return;
    await onManualAdd({
      title: title.trim(),
      category,
      tagNames,
      notes: normalizeNotes(notes),
      startTs: new Date(manualStart).toISOString(),
      endTs: new Date(manualEnd).toISOString(),
    });
    setTitle("");
    setCategory(null);
    setTagNames([]);
    setNotes("");
    setManualMode(false);
    setFormKey((key) => key + 1);
  }

  if (runningEntry) {
    return (
      <div className={styles.card} data-mode="running">
        <div className={styles.trackingLabel} aria-live="polite">
          <span className={styles.pulseDot} aria-hidden="true" />
          Tracking
        </div>
        <input
          className={styles.runningTitleInput}
          value={runningEntry.title}
          onChange={(event) =>
            void onUpdateRunning({
              title: event.target.value,
              category: runningEntry.category,
              tagNames: runningEntry.tags.map((t) => t.name),
              notes: runningEntry.notes,
            })
          }
          aria-label="Running entry title"
        />
        <div className={styles.runningMeta}>
          <CategoryPicker
            categories={categories}
            value={runningEntry.category}
            onChange={(next) =>
              void (
                next &&
                onUpdateRunning({
                  title: runningEntry.title,
                  category: next,
                  tagNames: runningEntry.tags.map((t) => t.name),
                  notes: runningEntry.notes,
                })
              )
            }
            required
          />
          <TagEditor
            value={runningEntry.tags.map((t) => t.name)}
            onChange={(names) =>
              void onUpdateRunning({
                title: runningEntry.title,
                category: runningEntry.category,
                tagNames: names,
                notes: runningEntry.notes,
              })
            }
            knownTags={knownTags}
          />
        </div>
        <input
          className={styles.runningNotesInput}
          placeholder="Comment (optional)"
          value={runningEntry.notes ?? ""}
          onChange={(event) =>
            void onUpdateRunning({
              title: runningEntry.title,
              category: runningEntry.category,
              tagNames: runningEntry.tags.map((t) => t.name),
              notes: normalizeNotesLive(event.target.value),
            })
          }
          aria-label="Running entry comment"
        />
        <div className={styles.timerRow}>
          <span className={styles.timerDisplay}>{formatElapsedSeconds(elapsed)}</span>
          <button type="button" className={styles.stopButton} onClick={() => void onStop()}>
            Stop ⏹
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.card} data-mode="idle" ref={rootRef} onKeyDown={handleKeyDown}>
      <div className={styles.idleTopRow}>
        <input
          className={styles.quickAddInput}
          placeholder="What are you working on?"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !manualMode) void handleStart();
          }}
          autoFocus
        />
        {!manualMode ? (
          <>
            <button
              type="button"
              className={styles.startButton}
              disabled={!canStart || starting}
              onClick={() => void handleStart()}
            >
              Start ▶
            </button>
            <button type="button" className={styles.manualLink} onClick={() => setManualMode(true)}>
              + Manual entry
            </button>
          </>
        ) : (
          <button
            type="button"
            className={styles.startButton}
            disabled={!canSaveManual}
            onClick={() => void handleManualSave()}
          >
            Save
          </button>
        )}
      </div>

      {!canStart && (
        <p className={styles.hint}>
          {title.trim().length === 0
            ? "Enter a title and pick a category to start."
            : "Pick a category to start."}
        </p>
      )}

      {manualMode && (
        <>
          <div className={styles.manualTimes}>
            <DateTimePicker value={manualStart} onChange={setManualStart} label="Start" />
            <DateTimePicker value={manualEnd} onChange={setManualEnd} label="End" />
            <button type="button" className={styles.manualLink} onClick={() => setManualMode(false)}>
              Cancel
            </button>
          </div>
          {manualRangeError && (
            <p className={styles.error} role="alert">
              {manualRangeError}
            </p>
          )}
        </>
      )}

      <div className={styles.idleMeta}>
        <CategoryPicker categories={categories} value={category} onChange={setCategory} required />
        <TagEditor
          key={formKey}
          value={tagNames}
          onChange={setTagNames}
          knownTags={knownTags}
          recentTags={recentTags}
        />
      </div>

      <input
        className={styles.notesInput}
        placeholder="Comment (optional)"
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        aria-label="Quick-add comment"
      />

      <RecentChipsRail
        recentCategories={recentCategories}
        recentTags={recentTags}
        selectedCategory={category}
        selectedTagNames={tagNames}
        onSelectCategory={setCategory}
        onToggleTag={(name) =>
          setTagNames((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]))
        }
      />
    </div>
  );
}

function defaultManualStart(): string {
  const d = new Date();
  d.setHours(d.getHours() - 1);
  return toLocalDateTimeInput(d);
}
