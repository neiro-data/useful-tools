import { createTag } from "../api/tags";
import type { TagRead } from "../api/types";

/** Resolves a list of tag names to ids, creating any tag that doesn't exist yet in `knownTags`
 * (per `design/screens.md` §1.3: "unknown tag text creates a new tag on save"). Returns the
 * resolved ids plus any newly-created `TagRead`s so the caller can extend its local tag cache. */
export async function resolveTagIds(
  names: string[],
  knownTags: TagRead[],
): Promise<{ ids: number[]; created: TagRead[] }> {
  const byName = new Map(knownTags.map((tag) => [tag.name.toLowerCase(), tag]));
  const ids: number[] = [];
  const created: TagRead[] = [];

  for (const name of names) {
    const existing = byName.get(name.toLowerCase());
    if (existing) {
      ids.push(existing.id);
      continue;
    }
    const newTag = await createTag({ name });
    ids.push(newTag.id);
    created.push(newTag);
    byName.set(newTag.name.toLowerCase(), newTag);
  }

  return { ids, created };
}
