import { useEffect, useRef, useState, type ReactElement } from "react";
import type { CategoryRead } from "../../api/types";
import { CategoryChip } from "../CategoryChip/CategoryChip";
import styles from "./CategoryPicker.module.css";

interface CategoryPickerProps {
  categories: CategoryRead[];
  value: CategoryRead | null;
  onChange: (category: CategoryRead | null) => void;
  label?: string;
}

/** Small popover-style category picker shared by the quick-add card, inline entry edit, and the
 * manual-entry form (per `design/screens.md` §3 "same popover component in all three call
 * sites"). Single-select; `null` clears the category. */
export function CategoryPicker({
  categories,
  value,
  onChange,
  label = "Category",
}: CategoryPickerProps): ReactElement {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(event: MouseEvent): void {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
      >
        {value ? <CategoryChip category={value} /> : <span className={styles.placeholder}>{label} ▾</span>}
      </button>
      {open && (
        <ul className={styles.popover} role="listbox">
          <li>
            <button
              type="button"
              className={styles.clearOption}
              onClick={() => {
                onChange(null);
                setOpen(false);
              }}
            >
              No category
            </button>
          </li>
          {categories.map((category) => (
            <li key={category.id}>
              <button
                type="button"
                className={styles.option}
                onClick={() => {
                  onChange(category);
                  setOpen(false);
                }}
              >
                <CategoryChip category={category} variant="option" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
