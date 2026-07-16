import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, query } from "../api";
import { getGuestIdentity, saveParkingSession } from "../storage/parkingSession";
import type { Availability, GuestOverview, ParkingSession } from "../types";

const ticketEdgePath = "M .045 0 H .955 Q .955 .12 1 .12 V .433 Q .967 .433 .967 .50 Q .967 .567 1 .567 V .88 Q .955 .88 .955 1 H .045 Q .045 .88 0 .88 V .567 Q .033 .567 .033 .50 Q .033 .433 0 .433 V .12 Q .045 .12 .045 0 Z";

export function Home() {
  const [activeSession, setActiveSession] = useState<ParkingSession | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [hasParking, setHasParking] = useState(false);
  const [hasUpcomingReservation, setHasUpcomingReservation] = useState(false);
  const [availability, setAvailability] = useState<Availability | null>(null);

  useEffect(() => {
    api<Availability>("/api/availability").then(setAvailability).catch(() => setAvailability(null));
  }, []);

  useEffect(() => {
    const { phone, plate } = getGuestIdentity();
    if (!phone || !plate) { setSessionChecked(true); return; }

    api<GuestOverview>(`/api/me?${query({ phone, license_plate: plate })}`)
      .then((overview) => {
        const session = overview.sessions.find((item) => item.status === "active" || item.status === "overdue") ?? null;
        if (session) saveParkingSession(session);
        setActiveSession(session);
        setHasParking(overview.sessions.length > 0 || overview.reservations.length > 0);
        setHasUpcomingReservation(overview.reservations.some((reservation) => reservation.status === "confirmed" && new Date(reservation.starts_at).getTime() > Date.now()));
      })
      .catch(() => { setActiveSession(null); setHasParking(false); setHasUpcomingReservation(false); })
      .finally(() => setSessionChecked(true));
  }, []);

  const total = availability?.total ?? "—";

  return (
    <main className="home">
      <svg className="ticket-defs" aria-hidden="true" focusable="false">
        <defs><clipPath id="availability-ticket-edge" clipPathUnits="objectBoundingBox"><path d={ticketEdgePath} /></clipPath></defs>
      </svg>
      <div className="parking-photo" role="img" aria-label="Modern private parking entrance" />
      <aside className="availability" aria-label={availability ? `${availability.total} open spots: ${availability.standard} standard, ${availability.ev} EV and ${availability.accessible} accessible` : "Checking parking availability"}>
        <div className="availability-total">
          <span><i className="live-dot" />Available now</span>
          <em className="availability-updated">Updated just now</em>
          <p><strong>{total}</strong> spots</p>
          <small className="availability-note">Your spot is assigned when you arrive.</small>
        </div>
        <dl className="availability-stub">
          <div><dd>{availability?.standard ?? "—"}</dd><dt>STANDARD</dt></div>
          <div><dd>{availability?.ev ?? "—"}</dd><dt>EV</dt></div>
          <div><dd>{availability?.accessible ?? "—"}</dd><dt>ACCESSIBLE</dt></div>
          <i className="availability-barcode" aria-hidden="true" />
        </dl>
      </aside>
      <section className="home-copy">
        <p className="eyebrow">Private parking, simplified</p>
        <h1>Your spot is ready when you are.</h1>
        <p className="lead">Arrive now or reserve ahead. We will choose the right spot and have its number ready for you.</p>
        <div className="hero-actions">
          <Link className="button primary" to="/quick"><span className="button-icon" aria-hidden="true">P</span>Park now</Link>
          <Link className="button secondary" to="/book">Book in advance</Link>
        </div>
        {activeSession && <Link className="session-link" to={`/sessions/${activeSession.id}`}>Continue parking <span>·</span> Spot {String(activeSession.spot.number).padStart(2, "0")} →</Link>}
        {!activeSession && sessionChecked && hasUpcomingReservation && <Link className="session-link" to="/my">View upcoming booking →</Link>}
        {!activeSession && sessionChecked && !hasUpcomingReservation && hasParking && <Link className="session-link" to="/my">Parking history →</Link>}
      </section>
    </main>
  );
}
