import { useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import type { CategoryRead, EntryRead, TagRead } from "../../api/types";
import { CategoryPicker } from "../CategoryPicker/CategoryPicker";
import { TagEditor } from "../TagChip/TagEditor";
import { RecentChipsRail } from "../RecentChipsRail/RecentChipsRail";
import { useLiveTimer } from "../../hooks/useLiveTimer";
import { formatElapsedSeconds } from "../../utils/duration";
import styles from "./TimerWidget.module.css";

export interface StartPayload {
  title: string;
  category: CategoryRead | null;
  tagNames: string[];
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

/** Today's hero card (`design/screens.md` §1.1/§1.2/§8.4): idle quick-add form vs running timer,
 * in one component since they're mutually exclusive render modes of the same card. */
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
  const [manualMode, setManualMode] = useState(false);
  const [manualStart, setManualStart] = useState(() => defaultManualStart());
  const [manualEnd, setManualEnd] = useState(() => new Date().toISOString().slice(0, 16));
  const rootRef = useRef<HTMLDivElement>(null);

  const elapsed = useLiveTimer(runningEntry?.start_ts);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const target = event.target as HTMLElement;
    const isTextField = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
    if (isTextField && !(event.key >= "1" && event.key <= "6")) return;

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

  async function handleStart(): Promise<void> {
    if (title.trim().length === 0) return;
    await onStart({ title: title.trim(), category, tagNames });
    setTitle("");
    setCategory(null);
    setTagNames([]);
  }

  async function handleManualSave(): Promise<void> {
    if (title.trim().length === 0) return;
    await onManualAdd({
      title: title.trim(),
      category,
      tagNames,
      startTs: new Date(manualStart).toISOString(),
      endTs: new Date(manualEnd).toISOString(),
    });
    setTitle("");
    setCategory(null);
    setTagNames([]);
    setManualMode(false);
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
            })
          }
          aria-label="Running entry title"
        />
        <div className={styles.runningMeta}>
          <CategoryPicker
            categories={categories}
            value={runningEntry.category}
            onChange={(next) =>
              void onUpdateRunning({
                title: runningEntry.title,
                category: next,
                tagNames: runningEntry.tags.map((t) => t.name),
              })
            }
          />
          <TagEditor
            value={runningEntry.tags.map((t) => t.name)}
            onChange={(names) =>
              void onUpdateRunning({
                title: runningEntry.title,
                category: runningEntry.category,
                tagNames: names,
              })
            }
            knownTags={knownTags}
          />
        </div>
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
              disabled={title.trim().length === 0 || starting}
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
            disabled={title.trim().length === 0}
            onClick={() => void handleManualSave()}
          >
            Save
          </button>
        )}
      </div>

      {manualMode && (
        <div className={styles.manualTimes}>
          <label>
            Start
            <input
              type="datetime-local"
              value={manualStart}
              onChange={(event) => setManualStart(event.target.value)}
            />
          </label>
          <label>
            End
            <input
              type="datetime-local"
              value={manualEnd}
              onChange={(event) => setManualEnd(event.target.value)}
            />
          </label>
          <button type="button" className={styles.manualLink} onClick={() => setManualMode(false)}>
            Cancel
          </button>
        </div>
      )}

      <div className={styles.idleMeta}>
        <CategoryPicker categories={categories} value={category} onChange={setCategory} />
        <TagEditor value={tagNames} onChange={setTagNames} knownTags={knownTags} />
      </div>

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
  return d.toISOString().slice(0, 16);
}
