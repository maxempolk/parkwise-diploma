import { type FormEvent, useCallback, useEffect, useState } from "react";

import { IdentityFields } from "../components/IdentityFields";
import { ButtonLoader, RecordsSkeleton } from "../components/LoadingIndicator";
import { ReservationCard } from "../components/ReservationCard";
import { SessionCard } from "../components/SessionCard";
import { useToast } from "../components/ToastProvider";
import { api, query } from "../api";
import { getGuestIdentity, saveGuestIdentity, saveParkingSession } from "../storage/parkingSession";
import type { GuestOverview } from "../types";

export function MyParking() {
  const identity = getGuestIdentity();
  const [phone, setPhone] = useState(identity.phone);
  const [plate, setPlate] = useState(identity.plate);
  const [data, setData] = useState<GuestOverview | null>(null);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(() => !identity.phone || !identity.plate);
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  const loadParking = useCallback(async () => {
    setMessage("");
    setLoading(true);
    try {
      saveGuestIdentity(phone, plate);
      const overview = await api<GuestOverview>(`/api/me?${query({ phone, license_plate: plate })}`);
      const session = overview.sessions.find((item) => item.status === "active" || item.status === "overdue");
      if (session) saveParkingSession(session);
      setData(overview);
    } catch (error) {
      const nextMessage = (error as Error).message;
      setMessage(nextMessage);
      showToast("error", nextMessage);
    } finally {
      setLoading(false);
    }
  }, [phone, plate, showToast]);

  useEffect(() => {
    if (!editing && phone && plate) void loadParking();
  }, [editing, phone, plate, loadParking]);

  function submitLookup(event: FormEvent) {
    event.preventDefault();
    setEditing(false);
  }

  const currentSession = data?.sessions.find((item) => item.status === "active" || item.status === "overdue");
  const completedSessions = data?.sessions.filter((item) => item.status === "completed") ?? [];
  const confirmedReservations = (data?.reservations.filter((item) => item.status === "confirmed") ?? [])
    .sort((left, right) => new Date(left.starts_at).getTime() - new Date(right.starts_at).getTime());

  return (
    <main className="page my-parking-page">
      <section className="panel wide">
        <p className="eyebrow">Guest access</p>
        <h1>{editing ? "Find my parking" : "My parking"}</h1>
        {editing ? <form className="lookup" onSubmit={submitLookup}><IdentityFields phone={phone} plate={plate} setPhone={setPhone} setPlate={setPlate} /><button className="button primary" disabled={loading}>{loading ? <ButtonLoader label="Opening parking…" /> : "Show my parking"}</button></form> : <div className="identity-summary"><p>Showing parking for <strong>{plate}</strong></p><button className="text-link" onClick={() => setEditing(true)}>Change vehicle or details</button></div>}
        {message && <p className="error">{message}</p>}
        {loading && !data && <RecordsSkeleton />}
        {data && <div className="records">
          <section className="parking-group current-parking-group"><div className="parking-group-heading"><h2>Current parking</h2>{currentSession && <span className="group-count">Live</span>}</div>{currentSession ? <SessionCard item={currentSession} /> : <p className="muted">No active parking session.</p>}</section>
          {confirmedReservations.length > 0 && <section className="parking-group"><div className="parking-group-heading"><h2>Your bookings</h2><span className="group-count">{confirmedReservations.length}</span></div>{confirmedReservations.map((item) => <ReservationCard key={item.id} item={item} />)}</section>}
          <section className="parking-group"><div className="parking-group-heading"><h2>Completed sessions</h2>{completedSessions.length > 0 && <span className="group-count">{completedSessions.length}</span>}</div>{completedSessions.length ? completedSessions.map((item) => <SessionCard key={item.id} item={item} />) : <p className="muted">No completed parking sessions yet.</p>}</section>
        </div>}
      </section>
    </main>
  );
}
