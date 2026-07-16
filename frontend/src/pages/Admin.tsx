import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { spotLabels } from "../constants";
import { useToast } from "../components/ToastProvider";
import type { ParkingSession, Reservation, Spot, SpotType, Tariff } from "../types";

interface AdminDashboardProps {
  token: string;
  onLogout: () => void;
}

interface AdminLoginProps {
  onLogin: (token: string) => void;
}

interface MetricProps {
  label: string;
  value: string | number;
}

interface AdminTableProps {
  rows: Array<{ id: number; cells: (string | number | ReactNode)[] }>;
  labels: string[];
}

interface BulkCreateResult {
  created_numbers: number[];
  skipped_numbers: number[];
}

function toDateTimeLocal(value: string) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}T${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function localDateValue(value: string) {
  const date = new Date(value);
  return dateInputValue(date);
}

function dateInputValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatStatus(status: string) {
  return status.split("_").map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`).join(" ");
}

function Metric({ label, value }: MetricProps) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong></article>;
}

function AdminTable({ rows, labels }: AdminTableProps) {
  if (!rows.length) return <p className="muted">No records yet.</p>;
  const hasActions = labels.includes("Actions");
  return <div className="table">{rows.map((row) => <div className={`table-row ${hasActions ? "table-row-actions" : ""}`} key={row.id}>{row.cells.map((cell, index) => <span data-label={labels[index]} key={`${row.id}-${index}`}>{cell}</span>)}</div>)}</div>;
}

interface AdminCalendarProps {
  reservations: Reservation[];
  selectedDate: string;
  onDateChange: (value: string) => void;
  onManage: (reservation: Reservation) => void;
}

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  return dateInputValue(date);
}

function AdminCalendar({ reservations, selectedDate, onDateChange, onManage }: AdminCalendarProps) {
  const dayStart = new Date(`${selectedDate}T00:00:00`);
  const dayEnd = new Date(dayStart);
  dayEnd.setDate(dayEnd.getDate() + 1);
  const dayReservations = reservations.filter((reservation) => new Date(reservation.starts_at) < dayEnd && new Date(reservation.ends_at) > dayStart).sort((left, right) => new Date(left.starts_at).getTime() - new Date(right.starts_at).getTime());
  const bookingsByType = (Object.keys(spotLabels) as SpotType[]).reduce<Record<SpotType, number>>((result, spotType) => ({ ...result, [spotType]: dayReservations.filter((reservation) => reservation.spot_type === spotType && reservation.status === "confirmed").length }), { standard: 0, ev: 0, accessible: 0 });
  const dayLabel = dayStart.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

  return <section className="panel reservation-calendar">
    <div className="calendar-toolbar">
      <div><p className="eyebrow">Reservation calendar</p><h2>{dayLabel}</h2><p className="muted">{dayReservations.length} booking{dayReservations.length === 1 ? "" : "s"} on this day.</p></div>
      <div className="calendar-controls">
        <div className="calendar-nav" aria-label="Calendar day navigation"><button aria-label="Previous day" className="table-action" type="button" onClick={() => onDateChange(shiftDate(selectedDate, -1))}>←</button><button className="table-action" type="button" onClick={() => onDateChange(dateInputValue(new Date()))}>Today</button><button aria-label="Next day" className="table-action" type="button" onClick={() => onDateChange(shiftDate(selectedDate, 1))}>→</button></div>
        <label className="calendar-date">Date<input aria-label="Calendar date" type="date" value={selectedDate} onChange={(event) => onDateChange(event.target.value)} /></label>
      </div>
    </div>
    <div className="calendar-capacity" aria-label="Confirmed bookings by spot type">{(Object.entries(spotLabels) as Array<[SpotType, string]>).map(([spotType, label]) => <div key={spotType}><span>{label}</span><strong>{bookingsByType[spotType]}</strong><small>confirmed</small></div>)}</div>
    <div className="calendar-timeline" key={selectedDate}>
      {dayReservations.length ? dayReservations.map((reservation) => <article className={`calendar-event ${reservation.status}`} key={reservation.id}>
        <div className="calendar-time"><strong>{new Date(reservation.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</strong><span>to {new Date(reservation.ends_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></div>
        <div className="calendar-event-info"><div><strong>{reservation.license_plate}</strong><span>{spotLabels[reservation.spot_type]}</span></div><span className={`badge ${reservation.status}`}>{formatStatus(reservation.status)}</span></div>
        <button className="table-action" type="button" onClick={() => onManage(reservation)}>Manage</button>
      </article>) : <p className="calendar-empty">No reservations for this day.</p>}
    </div>
  </section>;
}

function tokenExpiresAt(token: string): number {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(payload.length / 4) * 4, "=");
    const expiresAt = JSON.parse(window.atob(base64)).exp;
    return typeof expiresAt === "number" ? expiresAt * 1000 : 0;
  } catch {
    return 0;
  }
}

function AdminLogin({ onLogin }: AdminLoginProps) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { showToast } = useToast();

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await api<{ access_token: string }>("/api/admin/login", { method: "POST", body: JSON.stringify({ username, password }) });
      onLogin(result.access_token);
      showToast("success", "Signed in.");
    } catch (requestError) {
      const message = (requestError as Error).message;
      setError(message);
      showToast("error", message);
    }
  }

  return <main className="page narrow"><section className="panel"><p className="eyebrow">Restricted area</p><h1>Administrator sign in</h1><form onSubmit={submit}><label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>{error && <p className="error">{error}</p>}<button className="button primary">Sign in</button></form></section></main>;
}

function AdminDashboard({ token, onLogout }: AdminDashboardProps) {
  const [spots, setSpots] = useState<Spot[]>([]);
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [tariffPrices, setTariffPrices] = useState<Record<SpotType, string>>({ standard: "", ev: "", accessible: "" });
  const [stats, setStats] = useState<Record<string, string | number>>({});
  const [dashboard, setDashboard] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [startNumber, setStartNumber] = useState("1");
  const [quantity, setQuantity] = useState("10");
  const [creationMode, setCreationMode] = useState<"bulk" | "single">("bulk");
  const [numberingMode, setNumberingMode] = useState<"automatic" | "manual">("automatic");
  const [type, setType] = useState<SpotType>("standard");
  const [selectedSpot, setSelectedSpot] = useState<Spot | null>(null);
  const [selectedReservation, setSelectedReservation] = useState<Reservation | null>(null);
  const [selectedSession, setSelectedSession] = useState<ParkingSession | null>(null);
  const [moveTargetId, setMoveTargetId] = useState("");
  const [sessionExtensionHours, setSessionExtensionHours] = useState("1");
  const [reservationStart, setReservationStart] = useState("");
  const [reservationEnd, setReservationEnd] = useState("");
  const [reservationSpotType, setReservationSpotType] = useState<SpotType>("standard");
  const [sessionQuery, setSessionQuery] = useState("");
  const [sessionStatus, setSessionStatus] = useState<"open" | "active" | "overdue" | "completed" | "all">("open");
  const [sessionSpot, setSessionSpot] = useState("");
  const [sessionDate, setSessionDate] = useState("");
  const [calendarDate, setCalendarDate] = useState(() => dateInputValue(new Date()));
  const [blockReason, setBlockReason] = useState("Maintenance");
  const { showToast } = useToast();

  const logoutForExpiredToken = useCallback(() => {
    onLogout();
    showToast("info", "Your administrator session expired. Please sign in again.");
  }, [onLogout, showToast]);

  const handleRequestError = useCallback((requestError: unknown) => {
    if (requestError instanceof ApiError && requestError.status === 401) {
      logoutForExpiredToken();
      return;
    }
    const message = (requestError as Error).message;
    setError(message);
    showToast("error", message);
  }, [logoutForExpiredToken, showToast]);

  useEffect(() => {
    const expiresAt = tokenExpiresAt(token);
    const delay = expiresAt - Date.now();
    if (delay <= 0) {
      logoutForExpiredToken();
      return;
    }
    const timer = window.setTimeout(logoutForExpiredToken, delay);
    return () => window.clearTimeout(timer);
  }, [logoutForExpiredToken, token]);

  const load = useCallback(async () => {
    try {
      const [nextSpots, nextSessions, nextReservations, nextTariffs, nextStats, nextDashboard] = await Promise.all([
        api<Spot[]>("/api/admin/spots", {}, token),
        api<ParkingSession[]>("/api/admin/sessions", {}, token),
        api<Reservation[]>("/api/admin/reservations", {}, token),
        api<Tariff[]>("/api/admin/tariffs", {}, token),
        api<Record<string, string | number>>("/api/admin/statistics", {}, token),
        api<Record<string, number>>("/api/admin/dashboard", {}, token),
      ]);
      setSpots(nextSpots);
      setSessions(nextSessions);
      setReservations(nextReservations);
      setTariffPrices({
        standard: nextTariffs.find((tariff) => tariff.spot_type === "standard")?.price_per_30_minutes ?? "",
        ev: nextTariffs.find((tariff) => tariff.spot_type === "ev")?.price_per_30_minutes ?? "",
        accessible: nextTariffs.find((tariff) => tariff.spot_type === "accessible")?.price_per_30_minutes ?? "",
      });
      setStats(nextStats);
      setDashboard(nextDashboard);
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }, [handleRequestError, token]);

  useEffect(() => { void load(); }, [load]);

  async function addSpot(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/admin/spots", { method: "POST", body: JSON.stringify({ number: Number(number), spot_type: type }) }, token);
      setNumber("");
      await load();
      showToast("success", "Parking spot added.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function addSpotsBulk(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await api<BulkCreateResult>("/api/admin/spots/bulk", { method: "POST", body: JSON.stringify({ start_number: numberingMode === "manual" ? Number(startNumber) : undefined, quantity: Number(quantity), spot_type: type }) }, token);
      await load();
      const skipped = result.skipped_numbers.length ? ` ${result.skipped_numbers.length} existing spot${result.skipped_numbers.length === 1 ? " was" : "s were"} skipped.` : "";
      showToast("success", `${result.created_numbers.length} ${spotLabels[type]} spot${result.created_numbers.length === 1 ? "" : "s"} added.${skipped}`);
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function saveTariffs(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/admin/tariffs/bulk", { method: "PUT", body: JSON.stringify({ tariffs: (Object.entries(tariffPrices) as Array<[SpotType, string]>).map(([spotType, value]) => ({ spot_type: spotType, price_per_30_minutes: value })) }) }, token);
      await load();
      showToast("success", "Tariffs saved.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function updateSpotBlock() {
    if (!selectedSpot) return;
    const path = selectedSpot.is_blocked ? "unblock" : "block";
    const reason = selectedSpot.is_blocked ? undefined : blockReason.trim();
    if (!selectedSpot.is_blocked && !reason) {
      showToast("error", "Enter a reason before blocking this spot.");
      return;
    }
    try {
      await api(`/api/admin/spots/${selectedSpot.id}/${path}`, { method: "POST", body: reason ? JSON.stringify({ reason }) : undefined }, token);
      await load();
      showToast("success", selectedSpot.is_blocked ? "Parking spot unblocked." : "Parking spot blocked.");
      setSelectedSpot(null);
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function changeSpotLifecycle(action: "activate" | "deactivate" | "delete") {
    if (!selectedSpot) return;
    try {
      const method = action === "delete" ? "DELETE" : "POST";
      await api(`/api/admin/spots/${selectedSpot.id}${action === "delete" ? "" : `/${action}`}`, { method }, token);
      await load();
      setSelectedSpot(null);
      showToast("success", action === "delete" ? "Parking spot deleted." : action === "activate" ? "Parking spot reactivated." : "Parking spot deactivated.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function checkInReservation() {
    if (!selectedReservation) return;
    try {
      const session = await api<ParkingSession>(`/api/admin/reservations/${selectedReservation.id}/check-in`, { method: "POST" }, token);
      await load();
      setSelectedReservation(null);
      showToast("success", `Checked in at spot ${session.spot.number}.`);
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function cancelReservation() {
    if (!selectedReservation) return;
    try {
      await api(`/api/admin/reservations/${selectedReservation.id}/cancel`, { method: "POST" }, token);
      await load();
      setSelectedReservation(null);
      showToast("success", "Reservation cancelled.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function updateAdminReservation() {
    if (!selectedReservation) return;
    try {
      const updated = await api<Reservation>(`/api/admin/reservations/${selectedReservation.id}`, { method: "PUT", body: JSON.stringify({ spot_type: reservationSpotType, starts_at: new Date(reservationStart).toISOString(), ends_at: new Date(reservationEnd).toISOString() }) }, token);
      await load();
      setSelectedReservation(updated);
      setReservationStart(toDateTimeLocal(updated.starts_at));
      setReservationEnd(toDateTimeLocal(updated.ends_at));
      showToast("success", "Reservation updated.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function completeSelectedSession() {
    if (!selectedSession) return;
    try {
      await api(`/api/admin/sessions/${selectedSession.id}/complete`, { method: "POST" }, token);
      await load();
      setSelectedSession(null);
      showToast("success", "Parking session completed.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function extendSelectedSession() {
    if (!selectedSession) return;
    const hours = Number(sessionExtensionHours);
    if (!Number.isFinite(hours) || hours < 0.5 || hours > 24 || !Number.isInteger(hours * 2)) {
      showToast("error", "Enter an extension from 0.5 to 24 hours in 30-minute steps.");
      return;
    }
    const expectedEndAt = new Date(new Date(selectedSession.expected_end_at).getTime() + hours * 60 * 60_000);
    try {
      const updated = await api<ParkingSession>(`/api/admin/sessions/${selectedSession.id}/extend`, { method: "POST", body: JSON.stringify({ expected_end_at: expectedEndAt.toISOString() }) }, token);
      await load();
      setSelectedSession(updated);
      showToast("success", "Parking session extended.");
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  async function moveSelectedSession() {
    if (!selectedSession || !moveTargetId) return;
    try {
      const moved = await api<ParkingSession>(`/api/admin/sessions/${selectedSession.id}/move`, { method: "POST", body: JSON.stringify({ spot_id: Number(moveTargetId) }) }, token);
      await load();
      setSelectedSession(moved);
      showToast("success", `Vehicle moved to spot ${moved.spot.number}.`);
    } catch (requestError) {
      handleRequestError(requestError);
    }
  }

  function manageReservation(reservation: Reservation) {
    setSelectedReservation(reservation);
    setReservationStart(toDateTimeLocal(reservation.starts_at));
    setReservationEnd(toDateTimeLocal(reservation.ends_at));
    setReservationSpotType(reservation.spot_type);
  }

  const previewQuantity = Number(quantity);
  const previewStart = Number(startNumber);
  const previewEnd = previewStart > 0 && previewQuantity > 0 ? previewStart + previewQuantity - 1 : null;
  const activeSessions = sessions.filter((session) => session.status === "active" || session.status === "overdue");
  const visibleSessions = sessions.filter((session) => {
    const query = sessionQuery.trim().toLowerCase();
    const matchesQuery = !query || session.license_plate.toLowerCase().includes(query) || session.phone.toLowerCase().includes(query);
    const matchesStatus = sessionStatus === "all" || (sessionStatus === "open" ? session.status !== "completed" : session.status === sessionStatus);
    const matchesSpot = !sessionSpot || session.spot_id === Number(sessionSpot);
    const matchesDate = !sessionDate || localDateValue(session.started_at) === sessionDate;
    return matchesQuery && matchesStatus && matchesSpot && matchesDate;
  });
  const canManageSelectedSession = selectedSession?.status === "active" || selectedSession?.status === "overdue";
  const moveTargets = selectedSession ? spots.filter((spot) => spot.id !== selectedSession.spot_id && spot.spot_type === selectedSession.spot.spot_type && spot.is_active && !spot.is_blocked && !activeSessions.some((session) => session.spot_id === spot.id)) : [];
  const canAdminCheckIn = selectedReservation?.status === "confirmed" && Date.now() >= new Date(selectedReservation.starts_at).getTime();

  return (
    <main className="admin-page">
      <div className="admin-heading"><div><p className="eyebrow">Operations</p><h1>Parking dashboard</h1></div><button className="button secondary" onClick={onLogout}>Sign out</button></div>
      {error && <p className="error">{error}</p>}
      <section className="metrics"><Metric label="Available now" value={Math.max(0, dashboard.available_spots ?? 0)} /><Metric label="Active now" value={dashboard.active_sessions ?? 0} /><Metric label="Needs attention" value={dashboard.overdue_sessions ?? 0} /><Metric label="Revenue" value={`$${stats.simulated_revenue_usd ?? 0}`} /></section>
      <section className="panel live-operations">
        <div><p className="eyebrow">Live overview</p><h2>Operations now</h2><p className="muted">{dashboard.total_spots ?? spots.length} spots configured · {dashboard.blocked_spots ?? 0} blocked</p></div>
        {activeSessions.length ? <div className="live-session-list">{activeSessions.map((session) => <article className={`live-session ${session.status === "overdue" ? "overdue" : ""}`} key={session.id}><span className="badge">{session.status}</span><strong>{session.license_plate}</strong><small>Spot {session.spot.number} · until {new Date(session.expected_end_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small></article>)}</div> : <p className="live-empty">No cars are currently parked.</p>}
      </section>
      <div className="admin-grid">
        <section className="panel spot-manager">
          <div className="spot-manager-heading"><div><h2>Parking spots</h2><p className="muted">Create a group, then manage individual spots below.</p></div><span>{spots.length} total</span></div>
          <div className="creation-tabs" role="tablist" aria-label="Spot creation mode"><button className={creationMode === "bulk" ? "selected" : ""} type="button" onClick={() => setCreationMode("bulk")}>Bulk add</button><button className={creationMode === "single" ? "selected" : ""} type="button" onClick={() => setCreationMode("single")}>Add one</button></div>
          {creationMode === "bulk" ? <form className="bulk-form" onSubmit={addSpotsBulk}>
            <label>Type<select value={type} onChange={(event) => setType(event.target.value as SpotType)}>{Object.entries(spotLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <fieldset className="numbering-choice"><legend>Numbering</legend><label><input checked={numberingMode === "automatic"} name="numbering" type="radio" onChange={() => setNumberingMode("automatic")} />Assign automatically</label><label><input checked={numberingMode === "manual"} name="numbering" type="radio" onChange={() => setNumberingMode("manual")} />Choose start</label></fieldset>
            <label>Quantity<input required min="1" max="200" type="number" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
            {numberingMode === "manual" && <label>Start number<input required min="1" type="number" value={startNumber} onChange={(event) => setStartNumber(event.target.value)} /></label>}
            <p className="bulk-preview">{numberingMode === "automatic" ? <>Numbers will be assigned after <strong>Spot {String(spots.at(-1)?.number ?? 0).padStart(2, "0")}</strong>.</> : previewEnd ? <>Preview: <strong>{spotLabels[type]} · Spots {String(previewStart).padStart(2, "0")}–{String(previewEnd).padStart(2, "0")}</strong></> : "Enter a valid range to preview it."}</p>
            <button className="button primary" disabled={!previewQuantity || (numberingMode === "manual" && !previewEnd)}>Add {previewQuantity || ""} spots</button>
          </form> : <form className="inline-form" onSubmit={addSpot}><input aria-label="Spot number" required min="1" type="number" value={number} onChange={(event) => setNumber(event.target.value)} placeholder="Number" /><select value={type} onChange={(event) => setType(event.target.value as SpotType)}>{Object.entries(spotLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><button className="button primary">Add spot</button></form>}
          <div className="spot-grid">{spots.map((spot) => <button aria-label={`Spot ${spot.number}, ${spot.is_blocked ? "blocked" : !spot.is_active ? "inactive" : "available"}. Manage this spot`} key={spot.id} className={`spot ${spot.is_blocked ? "blocked" : ""} ${!spot.is_active ? "inactive" : ""}`} onClick={() => { setSelectedSpot(spot); setBlockReason(spot.block_reason || "Maintenance"); }}><strong>{spot.number}</strong><small>{spot.is_blocked ? "Blocked" : !spot.is_active ? "Inactive" : spotLabels[spot.spot_type]}</small></button>)}</div>
        </section>
        <section className="panel"><h2>Tariffs</h2><p className="muted">Price per 30 minutes in USD.</p><form className="tariff-form" onSubmit={saveTariffs}>{(Object.entries(spotLabels) as Array<[SpotType, string]>).map(([spotType, label]) => <label key={spotType}><span>{label}</span><div><b>$</b><input required aria-label={`${label} price per 30 minutes`} type="number" min="0.01" step="0.01" value={tariffPrices[spotType]} onChange={(event) => setTariffPrices((current) => ({ ...current, [spotType]: event.target.value }))} /></div></label>)}<button className="button primary">Save tariffs</button></form></section>
      </div>
      <section className="panel table-panel"><div className="table-heading"><div><h2>Sessions</h2><p className="muted">{visibleSessions.length} shown · completed sessions are hidden by default.</p></div></div><div className="session-filters"><label>Search<input value={sessionQuery} onChange={(event) => setSessionQuery(event.target.value)} placeholder="Phone or vehicle" /></label><label>Status<select value={sessionStatus} onChange={(event) => setSessionStatus(event.target.value as typeof sessionStatus)}><option value="open">Open only</option><option value="active">Active</option><option value="overdue">Overdue</option><option value="completed">Completed</option><option value="all">All sessions</option></select></label><label>Spot<select value={sessionSpot} onChange={(event) => setSessionSpot(event.target.value)}><option value="">All spots</option>{spots.map((spot) => <option key={spot.id} value={spot.id}>Spot {spot.number}</option>)}</select></label><label>Date<input type="date" value={sessionDate} onChange={(event) => setSessionDate(event.target.value)} /></label></div><AdminTable labels={["Vehicle", "Spot", "Status", "Started", "Actions"]} rows={visibleSessions.map((session) => ({ id: session.id, cells: [session.license_plate, `Spot ${session.spot.number}`, <span className={`badge ${session.status}`}>{formatStatus(session.status)}</span>, new Date(session.started_at).toLocaleString(), <button className="table-action" type="button" onClick={() => { setSelectedSession(session); setMoveTargetId(""); setSessionExtensionHours("1"); }}>Manage</button>] }))} /></section>
      <AdminCalendar reservations={reservations} selectedDate={calendarDate} onDateChange={setCalendarDate} onManage={manageReservation} />
      {selectedSpot && <div className="spot-dialog-backdrop" role="presentation" onMouseDown={() => setSelectedSpot(null)}>
        <section aria-labelledby="spot-dialog-title" aria-modal="true" className="spot-dialog" onMouseDown={(event) => event.stopPropagation()} role="dialog">
          <p className="eyebrow">Spot {selectedSpot.number}</p>
          <h2 id="spot-dialog-title">Manage parking spot</h2>
          <p className="muted">{spotLabels[selectedSpot.spot_type]} · {selectedSpot.is_blocked ? `Blocked: ${selectedSpot.block_reason}` : !selectedSpot.is_active ? "Inactive" : "Available for assignment"}</p>
          <span className={`badge ${selectedSpot.is_blocked ? "blocked" : !selectedSpot.is_active ? "cancelled" : ""}`}>{selectedSpot.is_blocked ? "blocked" : !selectedSpot.is_active ? "inactive" : "active"}</span>

          {selectedSpot.is_active && <section className="spot-action-section">
            <h3>Maintenance</h3>
            {selectedSpot.is_blocked ? <><p>Blocked spots cannot receive new assignments.</p><button className="button primary full" type="button" onClick={() => void updateSpotBlock()}>Unblock spot</button></> : <><p>Temporarily remove this spot from assignment.</p><label>Block reason<input value={blockReason} onChange={(event) => setBlockReason(event.target.value)} /></label><button className="button danger full" disabled={!blockReason.trim()} type="button" onClick={() => void updateSpotBlock()}>Block for maintenance</button></>}
          </section>}

          <section className="spot-action-section">
            <h3>Availability</h3>
            <p>{selectedSpot.is_active ? "Deactivate a spot that is permanently unavailable. Its history will be preserved." : "This spot is inactive and excluded from new assignments."}</p>
            {selectedSpot.is_active ? <button className="button secondary full" type="button" onClick={() => void changeSpotLifecycle("deactivate")}>Deactivate spot</button> : <button className="button primary full" type="button" onClick={() => void changeSpotLifecycle("activate")}>Reactivate spot</button>}
          </section>

          <section className="spot-action-section danger-zone">
            <h3>Danger zone</h3>
            <p>Delete is available only when this spot has no session history and is not required by confirmed bookings.</p>
            <button className="button danger full" type="button" onClick={() => void changeSpotLifecycle("delete")}>Delete unused spot</button>
          </section>
          <button className="dialog-close" type="button" onClick={() => setSelectedSpot(null)}>Close</button>
        </section>
      </div>}
      {selectedReservation && <div className="spot-dialog-backdrop" role="presentation" onMouseDown={() => setSelectedReservation(null)}><section aria-labelledby="reservation-dialog-title" aria-modal="true" className="spot-dialog" onMouseDown={(event) => event.stopPropagation()} role="dialog"><p className="eyebrow">Reservation #{selectedReservation.id}</p><h2 id="reservation-dialog-title">{selectedReservation.license_plate}</h2><p className="muted">{spotLabels[selectedReservation.spot_type]} · {new Date(selectedReservation.starts_at).toLocaleString()}–{new Date(selectedReservation.ends_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p><span className={`badge ${selectedReservation.status}`}>{formatStatus(selectedReservation.status)}</span>{selectedReservation.status === "confirmed" && <section className="admin-reservation-edit"><h3>Edit reservation</h3><label>Spot type<select value={reservationSpotType} onChange={(event) => setReservationSpotType(event.target.value as SpotType)}>{Object.entries(spotLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Arrival<input type="datetime-local" step="1800" value={reservationStart} onChange={(event) => setReservationStart(event.target.value)} /></label><label>Departure<input type="datetime-local" step="1800" value={reservationEnd} onChange={(event) => setReservationEnd(event.target.value)} /></label><button className="button secondary full" type="button" onClick={() => void updateAdminReservation()}>Check availability and save</button></section>}<div className="dialog-actions admin-reservation-actions"> <button className="button secondary" type="button" onClick={() => setSelectedReservation(null)}>Close</button>{selectedReservation.status === "confirmed" && <><button className="button danger" type="button" onClick={() => void cancelReservation()}>Cancel booking</button>{canAdminCheckIn ? <button className="button primary" type="button" onClick={() => void checkInReservation()}>Check in</button> : <p className="admin-hint">Check-in opens at the booking start time.</p>}</>}</div></section></div>}
      {selectedSession && <div className="spot-dialog-backdrop" role="presentation" onMouseDown={() => setSelectedSession(null)}><section aria-labelledby="session-dialog-title" aria-modal="true" className="spot-dialog" onMouseDown={(event) => event.stopPropagation()} role="dialog"><p className="eyebrow">Session #{selectedSession.id}</p><h2 id="session-dialog-title">{selectedSession.license_plate}</h2><p className="muted">Currently at Spot {selectedSession.spot.number} · {spotLabels[selectedSession.spot.spot_type]}</p><span className={`badge ${selectedSession.status}`}>{formatStatus(selectedSession.status)}</span>{canManageSelectedSession && <><section className="admin-session-extension"><h3>Extend parking</h3><p>Add time to the current expected end. Availability will be checked before the session is extended.</p><label>Additional hours<input type="number" inputMode="decimal" min="0.5" max="24" step="0.5" value={sessionExtensionHours} onChange={(event) => setSessionExtensionHours(event.target.value)} /></label><button className="button primary full" type="button" onClick={() => void extendSelectedSession()}>Check and extend</button></section><label>Move to available spot<select value={moveTargetId} onChange={(event) => setMoveTargetId(event.target.value)}><option value="">Choose a spot</option>{moveTargets.map((spot) => <option key={spot.id} value={spot.id}>Spot {spot.number}</option>)}</select></label></>}<div className="dialog-actions admin-session-actions"><button className="button secondary" type="button" onClick={() => setSelectedSession(null)}>Close</button>{canManageSelectedSession && <><button className="button secondary" disabled={!moveTargetId} type="button" onClick={() => void moveSelectedSession()}>Move vehicle</button><button className="button danger" type="button" onClick={() => void completeSelectedSession()}>Complete session</button></>}</div></section></div>}
    </main>
  );
}

export function Admin() {
  const [token, setToken] = useState(sessionStorage.getItem("adminToken") ?? "");
  if (!token) return <AdminLogin onLogin={(value) => { sessionStorage.setItem("adminToken", value); setToken(value); }} />;
  return <AdminDashboard token={token} onLogout={() => { sessionStorage.removeItem("adminToken"); setToken(""); }} />;
}
