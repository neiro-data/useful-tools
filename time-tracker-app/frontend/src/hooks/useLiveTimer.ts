import { useEffect, useState } from "react";
import { secondsSince } from "../utils/duration";

/** Ticks once a second while `startTs` is set, deriving elapsed seconds from the stored start
 * time (never a client-only counter), so it stays correct across refreshes/tab-backgrounding. */
export function useLiveTimer(startTs: string | null | undefined): number {
  const [elapsed, setElapsed] = useState<number>(() => (startTs ? secondsSince(startTs) : 0));

  useEffect(() => {
    if (!startTs) {
      setElapsed(0);
      return;
    }
    setElapsed(secondsSince(startTs));
    const id = window.setInterval(() => {
      setElapsed(secondsSince(startTs));
    }, 1000);
    return () => window.clearInterval(id);
  }, [startTs]);

  return elapsed;
}
