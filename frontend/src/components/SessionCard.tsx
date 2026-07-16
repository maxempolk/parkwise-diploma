import { Link } from "react-router-dom";

import { spotLabels } from "../constants";
import type { ParkingSession } from "../types";
import { SessionProgress } from "./SessionProgress";

interface SessionCardProps {
  item: ParkingSession;
}

export function SessionCard({ item }: SessionCardProps) {
  return (
    <Link className="record-link" to={`/sessions/${item.id}`} aria-label={`View parking session at spot ${item.spot.number}`}>
      <article className="record session-record">
        <div className="session-details">
          <span className={`badge ${item.status}`}>{item.status}</span>
          <h3>Spot {item.spot.number} · {spotLabels[item.spot.spot_type]}</h3>
          <p>{new Date(item.started_at).toLocaleString()} · {item.license_plate}</p>
          {item.status !== "completed" && <SessionProgress item={item} />}
          {item.total_cost && <strong className="session-cost">${item.total_cost}</strong>}
        </div>
        <span className="record-arrow" aria-hidden="true">→</span>
      </article>
    </Link>
  );
}
