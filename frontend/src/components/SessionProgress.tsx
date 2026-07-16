import { useEffect, useState } from "react";

import type { ParkingSession } from "../types";
import { formatDuration } from "../utils/time";

interface SessionProgressProps {
  item: ParkingSession;
  currentTime?: number;
}

function useCurrentTime() {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return now;
}

export function SessionProgress({ item, currentTime }: SessionProgressProps) {
  const start = new Date(item.started_at).getTime();
  const end = new Date(item.expected_end_at).getTime();
  const liveNow = useCurrentTime();
  const now = currentTime ?? liveNow;
  const total = Math.max(1, end - start);
  const elapsed = Math.max(0, now - start);
  const overdue = now > end;
  const progress = Math.min(100, (elapsed / total) * 100);

  return (
    <div className={`session-progress ${overdue ? "is-overdue" : ""}`}>
      <div className="progress-heading"><span>Session time</span><strong>{Math.round(progress)}%</strong></div>
      <div className="progress-track" aria-label={`${Math.round(progress)} percent of parking time elapsed`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="progress-labels">
        <span><small>Elapsed</small>{formatDuration(elapsed)}</span>
        <span><small>{overdue ? "Overdue" : "Remaining"}</small>{formatDuration(overdue ? now - end : end - now)}</span>
      </div>
    </div>
  );
}
