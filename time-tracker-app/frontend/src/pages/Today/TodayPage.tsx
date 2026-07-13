import { useCallback, useEffect, useState, type ReactElement } from "react";
import { getToday } from "../../api/today";
import { startTimer, stopTimer } from "../../api/timer";
import { createEntry, deleteEntry, updateEntry } from "../../api/entries";
import { listCategories } from "../../api/categories";
import { listTags } from "../../api/tags";
import { ApiError } from "../../api/errors";
import type { CategoryRead, TagRead, TodayResponse } from "../../api/types";
import { TimerWidget, type StartPayload } from "../../components/TimerWidget/TimerWidget";
import { EntryRow, type EntryRowSaveValues } from "../../components/EntryRow/EntryRow";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import { formatDurationMinutes } from "../../utils/duration";
import { totalMinutes } from "../../utils/aggregate";
import { resolveTagIds } from "../../utils/resolveTagIds";
import styles from "./TodayPage.module.css";

export function TodayPage(): ReactElement {
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [tags, setTags] = useState<TagRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{ runningEntryId: number; pending: StartPayload } | null>(null);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    const [todayResponse, categoryResponse, tagResponse] = await Promise.all([
      getToday(),
      listCategories(),
      listTags(),
    ]);
    setToday(todayResponse);
    setCategories(categoryResponse.items);
    setTags(tagResponse.items);
  }, []);

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load Today."))
      .finally(() => setLoading(false));
  }, [load]);

  // Global "S" shortcut: toggle start/stop of the current/most recent timer, unless focus is in
  // a text field (design/screens.md §1.6).
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      const target = event.target as HTMLElement | null;
      const isTextField = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA");
      if (isTextField || event.key !== "s") return;
      event.preventDefault();
      if (today?.running_timer) void handleStop();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [today?.running_timer]);

  async function handleStart(payload: StartPayload): Promise<void> {
    setStarting(true);
    try {
      const { ids } = await resolveTagIds(payload.tagNames, tags);
      await startTimer({ title: payload.title, category_id: payload.category?.id ?? null, tag_ids: ids });
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.isTimerAlreadyRunning && err.runningEntryId !== null) {
        setConflict({ runningEntryId: err.runningEntryId, pending: payload });
      } else {
        setError(err instanceof ApiError ? err.message : "Could not start the timer.");
      }
    } finally {
      setStarting(false);
    }
  }

  async function handleStopAndStartPending(): Promise<void> {
    if (!conflict) return;
    const pending = conflict.pending;
    setConflict(null);
    await stopTimer();
    await handleStart(pending);
  }

  async function handleStop(): Promise<void> {
    await stopTimer();
    await load();
  }

  async function handleUpdateRunning(payload: StartPayload): Promise<void> {
    if (!today?.running_timer) return;
    const { ids, created } = await resolveTagIds(payload.tagNames, tags);
    if (created.length > 0) setTags((prev) => [...prev, ...created]);
    await updateEntry(today.running_timer.id, {
      title: payload.title,
      category_id: payload.category?.id ?? null,
      tag_ids: ids,
    });
    await load();
  }

  async function handleManualAdd(payload: StartPayload & { startTs: string; endTs: string }): Promise<void> {
    const { ids, created } = await resolveTagIds(payload.tagNames, tags);
    if (created.length > 0) setTags((prev) => [...prev, ...created]);
    await createEntry({
      title: payload.title,
      category_id: payload.category?.id ?? null,
      tag_ids: ids,
      start_ts: payload.startTs,
      end_ts: payload.endTs,
    });
    await load();
  }

  async function handleSaveEntry(entryId: number, values: EntryRowSaveValues): Promise<void> {
    const { ids, created } = await resolveTagIds(values.tagNames, tags);
    if (created.length > 0) setTags((prev) => [...prev, ...created]);
    await updateEntry(entryId, {
      title: values.title,
      category_id: values.category?.id ?? null,
      tag_ids: ids,
    });
    await load();
  }

  async function handleDeleteEntry(entryId: number): Promise<void> {
    await deleteEntry(entryId);
    await load();
  }

  const todayLabel = new Date().toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  const runningTotal = today ? totalMinutes(today.entries) : 0;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>
          Today <span className={styles.dateLabel}>· {todayLabel}</span>
        </h1>
      </header>

      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}

      {loading || !today ? (
        <div className={styles.loadingCard}>
          <Skeleton height={44} />
        </div>
      ) : (
        <>
          <TimerWidget
            runningEntry={today.running_timer}
            categories={categories}
            knownTags={tags}
            recentCategories={today.recent_categories}
            recentTags={today.recent_tags}
            onStart={handleStart}
            onStop={handleStop}
            onUpdateRunning={handleUpdateRunning}
            onManualAdd={handleManualAdd}
            starting={starting}
          />

          {conflict && (
            <div className={styles.conflictBanner} role="alert">
              <span>⚠ A timer is already running (entry #{conflict.runningEntryId}).</span>
              <div className={styles.conflictActions}>
                <button type="button" onClick={() => void handleStopAndStartPending()}>
                  Stop it and start this instead
                </button>
                <button type="button" onClick={() => setConflict(null)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className={styles.listHeader}>
            <h2>Today's entries</h2>
            <span className={styles.total}>
              {today.running_timer ? "Total so far: " : "Total: "}
              {formatDurationMinutes(runningTotal)}
            </span>
          </div>

          {today.entries.length === 0 ? (
            <div className={styles.emptyState}>
              No entries yet today. Start a timer above, or add a manual entry for something already done.
            </div>
          ) : (
            <div className={styles.list}>
              {today.entries.map((entry) => (
                <EntryRow
                  key={entry.id}
                  entry={entry}
                  categories={categories}
                  knownTags={tags}
                  onSave={(values) => handleSaveEntry(entry.id, values)}
                  onDelete={() => handleDeleteEntry(entry.id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
