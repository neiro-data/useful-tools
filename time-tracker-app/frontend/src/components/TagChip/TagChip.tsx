import type { ReactElement } from "react";
import styles from "./TagChip.module.css";

interface TagChipProps {
  name: string;
  selected?: boolean;
  removable?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
}

/** Tag chip (design system §8.6): fully rounded, monochrome — tags never compete with category
 * color for attention. */
export function TagChip({
  name,
  selected = false,
  removable = false,
  onClick,
  onRemove,
}: TagChipProps): ReactElement {
  const Tag = onClick ? "button" : "span";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      className={`${styles.chip} ${selected ? styles.selected : ""}`}
      onClick={onClick}
    >
      #{name}
      {removable && (
        <button
          type="button"
          className={styles.remove}
          aria-label={`Remove tag ${name}`}
          onClick={(event) => {
            event.stopPropagation();
            onRemove?.();
          }}
        >
          ×
        </button>
      )}
    </Tag>
  );
}
