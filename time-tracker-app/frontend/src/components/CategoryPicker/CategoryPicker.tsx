import { useEffect, useLayoutEffect, useRef, useState, type ReactElement } from "react";
import { createPortal } from "react-dom";
import type { CategoryRead } from "../../api/types";
import { CategoryChip } from "../CategoryChip/CategoryChip";
import styles from "./CategoryPicker.module.css";

interface CategoryPickerProps {
  categories: CategoryRead[];
  value: CategoryRead | null;
  onChange: (category: CategoryRead | null) => void;
  label?: string;
  /** When true, hides the "No category" clear option so a selection can never be removed, and
   * marks the placeholder as required. Category is mandatory on every entry/timer (see
   * `app/schemas.py`), so any required call site must set this. */
  required?: boolean;
}

interface PopoverPosition {
  top: number;
  left: number;
  minWidth: number;
  openAbove: boolean;
}

/** Small popover-style category picker shared by the quick-add card, inline entry edit, and the
 * manual-entry form (per `design/screens.md` §3 "same popover component in all three call
 * sites"). Single-select; `null` clears the category.
 *
 * The option list is rendered in a `createPortal` to `document.body` (fixed-positioned from the
 * trigger's bounding rect) so ancestor containers with `overflow: hidden` (e.g. the bordered
 * entry list on Today/DayGroup, which clips for rounded corners) never clip it. */
export function CategoryPicker({
  categories,
  value,
  onChange,
  label = "Category",
  required = false,
}: CategoryPickerProps): ReactElement {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PopoverPosition | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLUListElement>(null);

  const updatePosition = (): void => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const maxHeight = 240;
    const gap = 4;
    const margin = 8;
    const spaceBelow = window.innerHeight - rect.bottom;
    const openAbove = spaceBelow < maxHeight && rect.top > spaceBelow;
    // The picker sits mid-row in the inline entry editor, so a trigger near the right edge would
    // otherwise push the fixed-positioned popover off-screen. Clamp it into the viewport.
    const minWidth = Math.max(rect.width, 180);
    const maxLeft = window.innerWidth - minWidth - margin;
    setPosition({
      top: openAbove ? rect.top - gap : rect.bottom + gap,
      left: Math.max(margin, Math.min(rect.left, maxLeft)),
      minWidth,
      openAbove,
    });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function onDocClick(event: MouseEvent): void {
      const target = event.target as Node;
      const insideRoot = rootRef.current && rootRef.current.contains(target);
      const insidePopover = popoverRef.current && popoverRef.current.contains(target);
      if (!insideRoot && !insidePopover) setOpen(false);
    }
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") setOpen(false);
    }
    function onReposition(): void {
      updatePosition();
    }

    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open]);

  const popoverStyle: PopoverPosition | null = position;
  const placeholderLabel = required ? `${label} *` : label;

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        ref={triggerRef}
        className={styles.trigger}
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-required={required || undefined}
        aria-label={placeholderLabel}
      >
        {value ? (
          <CategoryChip category={value} />
        ) : (
          <span className={styles.placeholder}>{placeholderLabel} ▾</span>
        )}
      </button>
      {open &&
        popoverStyle &&
        createPortal(
          <ul
            ref={popoverRef}
            className={styles.popover}
            role="listbox"
            style={{
              top: popoverStyle.top,
              left: popoverStyle.left,
              minWidth: popoverStyle.minWidth,
              transform: popoverStyle.openAbove ? "translateY(-100%)" : undefined,
            }}
          >
            {!required && (
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
            )}
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
          </ul>,
          document.body,
        )}
    </div>
  );
}
