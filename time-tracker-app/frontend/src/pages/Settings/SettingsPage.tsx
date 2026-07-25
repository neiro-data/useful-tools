import { useEffect, useMemo, useState, type CSSProperties, type FormEvent, type ReactElement } from "react";
import { useSettings } from "../../hooks/useSettings";
import { useTimezones } from "../../hooks/useTimezones";
import { useCategories } from "../../hooks/useCategories";
import { createCategory } from "../../api/categories";
import type {
  CategoryColorKey,
  EntryMode,
  ExportFormat,
  SettingsUpdate,
  TimezoneOption,
  WeekStart,
} from "../../api/types";
import { ApiError } from "../../api/errors";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import { CategoryChip } from "../../components/CategoryChip/CategoryChip";
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

/** The design system's 12 fixed palette keys (`design/tokens.css` `--cat-*`, `CategoryColorKey`
 * in `src/api/types.ts`). Preferred over raw hex because they adapt to light/dark mode. */
const PALETTE_KEYS: CategoryColorKey[] = [
  "red",
  "orange",
  "amber",
  "lime",
  "green",
  "teal",
  "cyan",
  "blue",
  "indigo",
  "violet",
  "pink",
  "slate",
];

const DEFAULT_HEX = "#4c6ef5";

interface FormState {
  default_entry_mode: EntryMode;
  week_starts_on: WeekStart;
  default_export_format: ExportFormat;
  database_label: string;
  timezone: string;
}

/** Groups timezone options by their IANA region prefix (`Europe/`, `America/`, ...) for
 * `<optgroup>` rendering. Zones with no `/` (e.g. `UTC`) fall into an "Other" group. Preserves the
 * server's alphabetical ordering within and across groups. */
function groupTimezonesByRegion(options: TimezoneOption[]): Map<string, TimezoneOption[]> {
  const groups = new Map<string, TimezoneOption[]>();
  for (const option of options) {
    const slashIndex = option.name.indexOf("/");
    const region = slashIndex === -1 ? "Other" : option.name.slice(0, slashIndex);
    const existing = groups.get(region);
    if (existing) {
      existing.push(option);
    } else {
      groups.set(region, [option]);
    }
  }
  return groups;
}

/** Settings screen (Task 6): editable app preferences backed by `GET`/`PATCH /settings`, plus a
 * timezone dropdown sourced from `GET /settings/timezones` and a category-creation section backed
 * by `GET`/`POST /categories`. Only fields the backend allows to change (`SettingsUpdate`) are
 * exposed on the settings form; `id` is read-only. */
export function SettingsPage(): ReactElement {
  const { settings, loading, error, save } = useSettings();
  const { timezones, error: timezonesError } = useTimezones();
  const {
    categories,
    loading: categoriesLoading,
    error: categoriesError,
    reload: reloadCategories,
  } = useCategories();

  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [categoryName, setCategoryName] = useState("");
  const [colorKey, setColorKey] = useState<CategoryColorKey>("blue");
  const [customHex, setCustomHex] = useState(DEFAULT_HEX);
  const [useCustomColor, setUseCustomColor] = useState(false);
  const [sortOrder, setSortOrder] = useState(0);
  const [categorySaving, setCategorySaving] = useState(false);
  const [categoryError, setCategoryError] = useState<string | null>(null);

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
  const canSave = !loading && !saving && form !== null && !labelBlank;

  // The saved zone might not be in the fetched list (e.g. the list failed to load, or a
  // server/browser drift edge case) — make sure it's always selectable/selected regardless.
  const timezoneOptions = useMemo(() => {
    if (!form) return timezones;
    if (timezones.some((option) => option.name === form.timezone)) return timezones;
    return [...timezones, { name: form.timezone, utc_offset: "" }];
  }, [timezones, form]);

  const timezoneGroups = useMemo(() => groupTimezonesByRegion(timezoneOptions), [timezoneOptions]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!form || !settings || labelBlank) return;

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
    if (form.timezone !== settings.timezone) {
      update.timezone = form.timezone;
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

  const categoryNameTrimmed = categoryName.trim();
  const categoryNameInvalid = categoryNameTrimmed.length === 0 || categoryNameTrimmed.length > 200;

  async function handleCreateCategory(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (categoryNameInvalid || categorySaving) return;

    setCategorySaving(true);
    setCategoryError(null);

    try {
      await createCategory({
        name: categoryNameTrimmed,
        color: useCustomColor ? customHex : colorKey,
        sort_order: sortOrder,
      });
      setCategoryName("");
      setColorKey("blue");
      setUseCustomColor(false);
      setCustomHex(DEFAULT_HEX);
      setSortOrder(0);
      await reloadCategories();
    } catch (err) {
      if (err instanceof ApiError && err.code === "conflict") {
        setCategoryError(`A category named "${categoryNameTrimmed}" already exists.`);
      } else {
        setCategoryError(err instanceof ApiError ? err.message : "Failed to create category.");
      }
    } finally {
      setCategorySaving(false);
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
              onChange={(event) => updateField("default_export_format", event.target.value as ExportFormat)}
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
            <select
              id="settings-timezone"
              className={styles.select}
              value={form.timezone}
              onChange={(event) => updateField("timezone", event.target.value)}
              aria-describedby={timezonesError ? "settings-timezone-hint" : undefined}
            >
              {[...timezoneGroups.entries()].map(([region, options]) => (
                <optgroup key={region} label={region}>
                  {options.map((option) => (
                    <option key={option.name} value={option.name}>
                      {option.utc_offset ? `${option.name} (UTC${option.utc_offset})` : option.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            {timezonesError && (
              <p id="settings-timezone-hint" className={styles.fieldHint}>
                Couldn&apos;t load the full timezone list; only the current zone is shown. You can still save
                other settings.
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

      <section className={styles.formCard}>
        <h2 className={styles.sectionTitle}>Categories</h2>

        {categoriesError && (
          <p className={styles.fieldHint} role="alert">
            {categoriesError}
          </p>
        )}
        {!categoriesLoading && !categoriesError && (
          <div className={styles.categoryList}>
            {categories.length === 0 ? (
              <p className={styles.label}>No categories yet.</p>
            ) : (
              categories.map((category) => <CategoryChip key={category.id} category={category} />)
            )}
          </div>
        )}

        {categoryError && (
          <div className={styles.errorBanner} role="alert">
            {categoryError}
          </div>
        )}

        <form className={styles.categoryForm} onSubmit={handleCreateCategory}>
          <div className={styles.field}>
            <label htmlFor="new-category-name" className={styles.label}>
              Name
            </label>
            <input
              id="new-category-name"
              type="text"
              className={styles.input}
              value={categoryName}
              onChange={(event) => setCategoryName(event.target.value)}
              maxLength={200}
              aria-label="Category name"
            />
          </div>

          <div className={styles.field}>
            <span className={styles.label}>Colour</span>
            <p className={styles.fieldHint}>
              Named colours adapt to light and dark mode; a custom hex code always renders exactly as picked.
              Prefer a named colour unless you need an exact hex.
            </p>
            <div className={styles.swatchRow} role="group" aria-label="Colour">
              {PALETTE_KEYS.map((key) => (
                <button
                  key={key}
                  type="button"
                  className={`${styles.swatch} ${
                    !useCustomColor && colorKey === key ? styles.swatchSelected : ""
                  }`}
                  style={{ "--swatch-color": `var(--cat-${key})` } as CSSProperties}
                  aria-label={key}
                  aria-pressed={!useCustomColor && colorKey === key}
                  onClick={() => {
                    setColorKey(key);
                    setUseCustomColor(false);
                  }}
                />
              ))}
              <label className={styles.customColorLabel}>
                <input
                  type="color"
                  aria-label="Custom colour"
                  value={customHex}
                  onChange={(event) => {
                    setCustomHex(event.target.value);
                    setUseCustomColor(true);
                  }}
                />
                Custom
              </label>
            </div>
          </div>

          <div className={styles.field}>
            <label htmlFor="new-category-sort-order" className={styles.label}>
              Sort order
            </label>
            <input
              id="new-category-sort-order"
              type="number"
              min={0}
              className={styles.input}
              value={sortOrder}
              onChange={(event) => setSortOrder(Math.max(0, Number(event.target.value) || 0))}
            />
          </div>

          <div className={styles.actions}>
            <button
              type="submit"
              className={styles.saveButton}
              disabled={categorySaving || categoryNameInvalid}
            >
              {categorySaving ? "Adding…" : "Add category"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
