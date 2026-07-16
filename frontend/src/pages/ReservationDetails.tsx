import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, query } from "../api";
import { spotLabels } from "../constants";
import { ButtonLoader, PageLoader } from "../components/LoadingIndicator";
import { useToast } from "../components/ToastProvider";
import { getGuestIdentity, saveParkingSession } from "../storage/parkingSession";
import type { GuestOverview, ParkingSession, Reservation } from "../types";

export function ReservationDetails() {
  const { reservationId } = useParams();
  const navigate = useNavigate();
  const identity = getGuestIdentity();
  const [item, setItem] = useState<Reservation | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const { showToast } = useToast();

  useEffect(() => {
    if (!identity.phone || !identity.plate) {
      setMessage("Enter your guest details on My parking first.");
      return;
    }

    api<GuestOverview>(`/api/me?${query({ phone: identity.phone, license_plate: identity.plate })}`)
      .then((overview) => {
        const reservation = overview.reservations.find((candidate) => candidate.id === Number(reservationId));
        if (reservation) setItem(reservation);
        else setMessage("Booking was not found.");
      })
      .catch((error) => setMessage((error as Error).message));
  }, [identity.phone, identity.plate, reservationId]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  async function checkIn() {
    if (!item) return;
    setBusy(true);
    setMessage("");
    try {
      const session = await api<ParkingSession>(`/api/reservations/${item.id}/check-in?${query({ phone: identity.phone, license_plate: identity.plate })}`, { method: "POST" });
      saveParkingSession(session);
      showToast("success", `Parking started at spot ${session.spot.number}.`);
      navigate(`/sessions/${session.id}`);
    } catch (error) {
      const nextMessage = (error as Error).message;
      setMessage(nextMessage);
      showToast("error", nextMessage);
    } finally {
      setBusy(false);
    }
  }

  if (message && !item) return <main className="page"><section className="panel wide"><p className="error">{message}</p><Link className="button secondary" to="/my">Go to My parking</Link></section></main>;
  if (!item) return <PageLoader label="Loading booking" />;

  const canCheckIn = item.status === "confirmed" && now >= new Date(item.starts_at).getTime();

  return (
    <main className="active-page reservation-page">
      <section className="active-hero reservation-hero">
        <span className={`active-status ${item.status === "confirmed" ? "completed" : "overdue"}`}><i className="live-dot" />{item.status.replace("_", " ")}</span>
        <p>Your upcoming parking</p>
        <h1>{spotLabels[item.spot_type]}</h1>
        <div className="active-stats"><div><small>Arrival</small><strong>{new Date(item.starts_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</strong></div><div><small>Departure</small><strong>{new Date(item.ends_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</strong></div></div>
        {canCheckIn && <div className="active-actions reservation-actions"><button className="button active-primary" disabled={busy} onClick={checkIn}>{busy ? <ButtonLoader label="Checking in…" /> : "Check in now"}</button></div>}
        <Link className="active-history-link" to="/my">← Back to My parking</Link>
      </section>
      <aside className="active-sidebar">
        <section className="active-card"><h2>Booking details</h2><dl><div><dt>Vehicle</dt><dd>{item.license_plate}</dd></div><div><dt>Spot type</dt><dd>{spotLabels[item.spot_type]}</dd></div><div><dt>Status</dt><dd>{item.status.replace("_", " ")}</dd></div></dl></section>
        <section className="active-card reservation-note"><h2>{canCheckIn ? "Ready to arrive" : "Arrival"}</h2><p>{canCheckIn ? "Check in now to receive your assigned spot number." : `Check-in opens at ${new Date(item.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.`}</p>{message && <p className="reservation-error">{message}</p>}</section>
      </aside>
    </main>
  );
}
