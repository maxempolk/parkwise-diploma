import { Link } from "react-router-dom";

import { spotLabels } from "../constants";
import type { Reservation } from "../types";

interface ReservationCardProps {
  item: Reservation;
}

export function ReservationCard({ item }: ReservationCardProps) {
  return (
    <Link className="record-link" to={`/reservations/${item.id}`} aria-label={`View ${spotLabels[item.spot_type]} booking`}>
      <article className="record">
        <div>
          <span className={`badge ${item.status}`}>{item.status.replace("_", " ")}</span>
          <h3>{spotLabels[item.spot_type]}</h3>
          <p>{new Date(item.starts_at).toLocaleString()} — {new Date(item.ends_at).toLocaleString()}</p>
        </div>
        <span className="record-arrow" aria-hidden="true">→</span>
      </article>
    </Link>
  );
}
