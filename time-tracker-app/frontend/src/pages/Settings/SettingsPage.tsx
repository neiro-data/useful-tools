import { useEffect, useState, type FormEvent, type ReactElement } from "react";
import { useSettings } from "../../hooks/useSettings";
import type { EntryMode, ExportFormat, SettingsUpdate, WeekStart } from "../../api/types";
import { ApiError } from "../../api/errors";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import styles from "./SettingsPage.module.css";

const ENTRY_MODE_OPTIONS: { value: EntryMode; label: string }[] = [
  { value: "timer", label: "Timer" },
  { value: "manual", label: "Manual" },
];

const WEEK_START_OPTIONS: { value: WeekStart; label: string }[] = [
  { value: "monday", label: "Monday" },
  { value: "sunday", label: "Sunday" },
];

const EXPORT_FORMAT_OPTIONS: { value: ExportFormat; label: string }[] = [
  { value: "html", label: "HTML" },
  { value: "csv", label: "CSV" },
  { value: "pdf", label: "PDF" },
  { value: "md", label: "Markdown" },
];

interface FormState {
  default_entry_mode: EntryMode;
  week_starts_on: WeekStart;
  default_export_format: ExportFormat;
  database_label: string;
  timezone: string;
}

/** Settings screen (Task 6): editable app preferences backed by `GET`/`PATCH /settings`. Only
 * fields the backend allows to change (`SettingsUpdate`) are exposed; `id` is read-only. */
export function SettingsPage(): ReactElement {
  const { settings, loading, error, save } = useSettings();
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setForm({
      default_entry_mode: settings.default_entry_mode,
      week_starts_on: settings.week_starts_on,
      default_export_format: settings.default_export_format,
      database_label: settings.database_label,
      timezone: settings.timezone,
    });
  }, [settings]);

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]): void {
    setForm((current) => (current ? { ...current, [key]: value } : current));
    setSaved(false);
  }

  const labelBlank = form ? form.database_label.trim().length === 0 : true;
  const timezoneBlank = form ? form.timezone.trim().length === 0 : true;
  const canSave = !loading && !saving && form !== null && !labelBlank && !timezoneBlank;

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!form || !settings || labelBlank || timezoneBlank) return;

    setSaving(true);
    setSaveError(null);
    setSaved(false);

    const update: SettingsUpdate = {};
    if (form.default_entry_mode !== settings.default_entry_mode) {
      update.default_entry_mode = form.default_entry_mode;
    }
    if (form.week_starts_on !== settings.week_starts_on) {
      update.week_starts_on = form.week_starts_on;
    }
    if (form.default_export_format !== settings.default_export_format) {
      update.default_export_format = form.default_export_format;
    }
    if (form.database_label.trim() !== settings.database_label) {
      update.database_label = form.database_label.trim();
    }
    if (form.timezone.trim() !== settings.timezone) {
      update.timezone = form.timezone.trim();
    }

    if (Object.keys(update).length === 0) {
      setSaving(false);
      setSaved(true);
      return;
    }

    try {
      await save(update);
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Settings</h1>
      </header>

      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}
      {saveError && (
        <div className={styles.errorBanner} role="alert">
          {saveError}
        </div>
      )}
      {saved && !saveError && (
        <div className={styles.successBanner} role="status">
          Settings saved.
        </div>
      )}

      {loading ? (
        <Skeleton height={280} />
      ) : form ? (
        <form className={styles.formCard} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor="settings-entry-mode" className={styles.label}>
              Default entry mode
            </label>
            <select
              id="settings-entry-mode"
              className={styles.select}
              value={form.default_entry_mode}
              onChange={(event) => updateField("default_entry_mode", event.target.value as EntryMode)}
            >
              {ENTRY_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="settings-week-start" className={styles.label}>
              Week starts on
            </label>
            <select
              id="settings-week-start"
              className={styles.select}
              value={form.week_starts_on}
              onChange={(event) => updateField("week_starts_on", event.target.value as WeekStart)}
            >
              {WEEK_START_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="settings-export-format" className={styles.label}>
              Default export format
            </label>
            <select
              id="settings-export-format"
              className={styles.select}
              value={form.default_export_format}
              onChange={(event) =>
                updateField("default_export_format", event.target.value as ExportFormat)
              }
            >
              {EXPORT_FORMAT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="settings-database-label" className={styles.label}>
              Database label
            </label>
            <input
              id="settings-database-label"
              type="text"
              className={styles.input}
              value={form.database_label}
              onChange={(event) => updateField("database_label", event.target.value)}
              aria-invalid={labelBlank}
              aria-describedby={labelBlank ? "settings-database-label-hint" : undefined}
            />
            {labelBlank && (
              <p id="settings-database-label-hint" className={styles.fieldHint}>
                Database label cannot be blank.
              </p>
            )}
          </div>

          <div className={styles.field}>
            <label htmlFor="settings-timezone" className={styles.label}>
              Timezone
            </label>
            <input
              id="settings-timezone"
              type="text"
              className={styles.input}
              placeholder="e.g. Europe/Lisbon"
              value={form.timezone}
              onChange={(event) => updateField("timezone", event.target.value)}
              aria-invalid={timezoneBlank}
              aria-describedby={timezoneBlank ? "settings-timezone-hint" : undefined}
            />
            {timezoneBlank && (
              <p id="settings-timezone-hint" className={styles.fieldHint}>
                Timezone cannot be blank.
              </p>
            )}
          </div>

          <div className={styles.actions}>
            <button type="submit" className={styles.saveButton} disabled={!canSave}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
