import { useState, type ReactElement } from "react";
import type { CategoryRead, EntryCreateManual, EntryRead, TagRead } from "../../api/types";
import { EntryRow, type EntryRowSaveValues } from "../EntryRow/EntryRow";
import { ManualEntryForm, type ManualEntryFormValues } from "../ManualEntryForm/ManualEntryForm";
import { formatDayHeading } from "../../utils/dateRange";
import { formatDurationMinutes } from "../../utils/duration";
import { totalMinutes } from "../../utils/aggregate";
import { resolveTagIds } from "../../utils/resolveTagIds";
import styles from "./DayGroup.module.css";

interface DayGroupProps {
  isoDate: string;
  entries: EntryRead[];
  categories: CategoryRead[];
  knownTags: TagRead[];
  defaultExpanded: boolean;
  onSaveEntry: (entryId: number, values: EntryRowSaveValues) => Promise<void>;
  onDeleteEntry: (entryId: number) => Promise<void>;
  onAddEntry: (entry: EntryCreateManual) => Promise<void>;
  onKnownTagsCreated: (created: TagRead[]) => void;
}

/** Collapsible per-day section shared by Week and Month (`design/screens.md` §2.2): same
 * entry-row component as Today, plus a hover-revealed "+ Add entry" affordance for that day. */
export function DayGroup({
  isoDate,
  entries,
  categories,
  knownTags,
  defaultExpanded,
  onSaveEntry,
  onDeleteEntry,
  onAddEntry,
  onKnownTagsCreated,
}: DayGroupProps): ReactElement {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [addingEntry, setAddingEntry] = useState(false);
  const dayTotal = totalMinutes(entries);

  async function handleManualSubmit(values: ManualEntryFormValues): Promise<void> {
    const { ids, created } = await resolveTagIds(values.tagNames, knownTags);
    if (created.length > 0) onKnownTagsCreated(created);
    await onAddEntry({
      title: values.title,
      notes: values.notes ?? null,
      category_id: values.category_id ?? null,
      tag_ids: ids,
      start_ts: values.start_ts,
      end_ts: values.end_ts,
    });
    setAddingEntry(false);
  }

  const firstEntry = entries[0];
  const lastEnd = firstEntry ? (firstEntry.end_ts ?? firstEntry.start_ts) : null;
  const defaultStart = (lastEnd ?? `${isoDate}T09:00:00`).slice(0, 16);
  const defaultStartDate = new Date(defaultStart);
  const defaultEndDate = new Date(defaultStartDate.getTime() + 30 * 60_000);

  return (
    <div className={styles.group}>
      <button
        type="button"
        className={styles.header}
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <span className={styles.disclosure} aria-hidden="true">
          {expanded ? "▾" : "▸"}
        </span>
        <span className={styles.dayLabel}>{formatDayHeading(isoDate)}</span>
        <span className={styles.dayTotal}>{formatDurationMinutes(dayTotal)}</span>
        <span
          role="button"
          tabIndex={0}
          className={styles.addButton}
          onClick={(event) => {
            event.stopPropagation();
            setAddingEntry(true);
            setExpanded(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.stopPropagation();
              setAddingEntry(true);
              setExpanded(true);
            }
          }}
        >
          + Add entry
        </span>
      </button>

      {expanded && (
        <div className={styles.body}>
          {addingEntry && (
            <ManualEntryForm
              categories={categories}
              knownTags={knownTags}
              defaultStart={defaultStart}
              defaultEnd={defaultEndDate.toISOString().slice(0, 16)}
              onSubmit={handleManualSubmit}
              onCancel={() => setAddingEntry(false)}
            />
          )}
          {entries.length === 0 && !addingEntry ? (
            <p className={styles.emptyDay}>No entries</p>
          ) : (
            <div className={styles.list}>
              {entries.map((entry) => (
                <EntryRow
                  key={entry.id}
                  entry={entry}
                  categories={categories}
                  knownTags={knownTags}
                  onSave={(values) => onSaveEntry(entry.id, values)}
                  onDelete={() => onDeleteEntry(entry.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
