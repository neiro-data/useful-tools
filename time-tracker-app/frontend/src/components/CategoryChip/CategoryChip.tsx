import type { CSSProperties, ReactElement } from "react";
import type { CategoryRead } from "../../api/types";
import { categoryChipTint, categoryColorVar } from "../../utils/categoryColor";
import styles from "./CategoryChip.module.css";

interface CategoryChipProps {
  category: CategoryRead | Pick<CategoryRead, "name" | "color">;
  /** Picker-option rendering (outlined, no fill) vs applied/selected (filled tint). */
  variant?: "applied" | "option";
  selected?: boolean;
  onClick?: () => void;
}

/** Category chip (design system §8.5): a color dot + name, never color alone. One per entry. */
export function CategoryChip({ category, variant = "applied", onClick }: CategoryChipProps): ReactElement {
  const isOption = variant === "option";
  const style = {
    "--chip-color": categoryColorVar(category.color),
    "--chip-tint": categoryChipTint(category.color),
  } as CSSProperties;

  const Tag = onClick ? "button" : "span";

  return (
    <Tag
      type={onClick ? "button" : undefined}
      className={`${styles.chip} ${isOption ? styles.option : styles.applied}`}
      style={style}
      onClick={onClick}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span>{category.name}</span>
    </Tag>
  );
}
