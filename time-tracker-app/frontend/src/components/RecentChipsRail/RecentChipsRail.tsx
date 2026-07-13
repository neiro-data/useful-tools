import type { ReactElement } from "react";
import type { CategoryRead, TagRead } from "../../api/types";
import { CategoryChip } from "../CategoryChip/CategoryChip";
import { TagChip } from "../TagChip/TagChip";
import styles from "./RecentChipsRail.module.css";

interface RecentChipsRailProps {
  recentCategories: CategoryRead[];
  recentTags: TagRead[];
  selectedCategory: CategoryRead | null;
  selectedTagNames: string[];
  onSelectCategory: (category: CategoryRead) => void;
  onToggleTag: (name: string) => void;
}

/** Recent/favorite category+tag rail (`design/screens.md` §8.7): click applies; number keys
 * `1`-`6` (categories) / `Shift+1`-`Shift+6` (tags) apply the Nth chip while focus is in the
 * quick-add area (handled by the parent `TimerWidget`'s keydown listener). */
export function RecentChipsRail({
  recentCategories,
  recentTags,
  selectedCategory,
  selectedTagNames,
  onSelectCategory,
  onToggleTag,
}: RecentChipsRailProps): ReactElement {
  return (
    <div className={styles.root}>
      {recentCategories.length > 0 && (
        <div className={styles.row}>
          <span className={styles.label}>Recent:</span>
          {recentCategories.slice(0, 6).map((category) => (
            <CategoryChip
              key={category.id}
              category={category}
              variant={selectedCategory?.id === category.id ? "applied" : "option"}
              onClick={() => onSelectCategory(category)}
            />
          ))}
        </div>
      )}
      {recentTags.length > 0 && (
        <div className={styles.row}>
          <span className={styles.label}>Tags:</span>
          {recentTags.slice(0, 8).map((tag) => (
            <TagChip
              key={tag.id}
              name={tag.name}
              selected={selectedTagNames.includes(tag.name)}
              onClick={() => onToggleTag(tag.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
