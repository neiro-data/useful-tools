import type { ReactElement } from "react";
import { useNavigate } from "react-router-dom";
import type { EntryRead } from "../../api/types";
import { useLiveTimer } from "../../hooks/useLiveTimer";
import { formatElapsedSeconds } from "../../utils/duration";
import styles from "./TimerBanner.module.css";

interface TimerBannerProps {
  runningTimer: EntryRead;
  onStop: () => void;
}

/** Sticky "timer running" banner shown on Week/Month while a timer started from Today is still
 * live (`design/screens.md` §2.3). Clicking navigates to Today; `Stop` stops it in place. */
export function TimerBanner({ runningTimer, onStop }: TimerBannerProps): ReactElement {
  const navigate = useNavigate();
  const elapsed = useLiveTimer(runningTimer.start_ts);

  return (
    <div className={styles.banner} role="status">
      <button type="button" className={styles.link} onClick={() => navigate("/today")}>
        <span className={styles.dot} aria-hidden="true" />
        Tracking "{runningTimer.title}" — <span className={styles.time}>{formatElapsedSeconds(elapsed)}</span>
      </button>
      <button
        type="button"
        className={styles.stopButton}
        onClick={(event) => {
          event.stopPropagation();
          onStop();
        }}
      >
        Stop
      </button>
    </div>
  );
}
