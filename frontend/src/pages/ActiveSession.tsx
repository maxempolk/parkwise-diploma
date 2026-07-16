import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, query } from "../api";
import { spotLabels } from "../constants";
import { ExtensionDurationPicker } from "../components/ExtensionDurationPicker";
import { ButtonLoader, PageLoader } from "../components/LoadingIndicator";
import { SessionProgress } from "../components/SessionProgress";
import { useToast } from "../components/ToastProvider";
import { getGuestIdentity, saveParkingSession } from "../storage/parkingSession";
import type { GuestOverview, ParkingSession, SessionEstimate } from "../types";
import { formatDuration } from "../utils/time";

function useCurrentTime() {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return now;
}

export function ActiveSession() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const identity = getGuestIdentity();
  const [item, setItem] = useState<ParkingSession | null>(null);
  const [message, setMessage] = useState("");
  const [showExtension, setShowExtension] = useState(false);
  const [extensionMinutes, setExtensionMinutes] = useState(30);
  const [customExtensionHours, setCustomExtensionHours] = useState("");
  const [activeAction, setActiveAction] = useState<"extend" | "complete" | null>(null);
  const [estimatedCost, setEstimatedCost] = useState<string | null>(null);
  const now = useCurrentTime();
  const { showToast } = useToast();

  useEffect(() => {
    if (!identity.phone || !identity.plate) { setMessage("Enter your guest details on My parking first."); return; }
    api<GuestOverview>(`/api/me?${query({ phone: identity.phone, license_plate: identity.plate })}`)
      .then((overview) => {
        const session = overview.sessions.find((candidate) => candidate.id === Number(sessionId));
        if (session) { saveParkingSession(session); setItem(session); } else setMessage("Parking session was not found.");
      })
      .catch((error) => setMessage((error as Error).message));
  }, [identity.phone, identity.plate, sessionId]);

  useEffect(() => {
    if (!item || item.status === "completed") return;
    let cancelled = false;
    const loadEstimate = () => api<SessionEstimate>(`/api/sessions/${item.id}/estimate?${query({ phone: identity.phone, license_plate: identity.plate })}`)
      .then((result) => { if (!cancelled) setEstimatedCost(result.estimated_cost); })
      .catch(() => { if (!cancelled) setEstimatedCost(null); });
    void loadEstimate();
    const interval = window.setInterval(() => { void loadEstimate(); }, 30_000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [identity.phone, identity.plate, item?.id, item?.status]);

  async function extend() {
    if (!item) return;
    const hasCustomDuration = customExtensionHours.trim() !== "";
    const customHours = Number(customExtensionHours);
    const customDurationIsValid = !hasCustomDuration || (Number.isFinite(customHours) && customHours >= 0.5 && customHours <= 24 && Number.isInteger(customHours * 2));
    if (!customDurationIsValid) { setMessage("Choose an extension from 30 minutes to 24 hours."); return; }
    const addedMinutes = hasCustomDuration ? customHours * 60 : extensionMinutes;
    const expectedEndAt = new Date(new Date(item.expected_end_at).getTime() + addedMinutes * 60_000);
    setActiveAction("extend");
    try {
      const updated = await api<ParkingSession>(`/api/sessions/${item.id}/extend?${query({ phone: identity.phone, license_plate: identity.plate })}`, { method: "POST", body: JSON.stringify({ expected_end_at: expectedEndAt.toISOString() }) });
      saveParkingSession(updated);
      setItem(updated);
      setShowExtension(false);
      setMessage("");
      showToast("success", "Parking extended.");
    } catch (error) {
      const nextMessage = (error as Error).message;
      setMessage(nextMessage);
      showToast("error", nextMessage);
    } finally {
      setActiveAction(null);
    }
  }

  async function complete() {
    if (!item) return;
    setActiveAction("complete");
    try {
      const updated = await api<ParkingSession>(`/api/sessions/${item.id}/complete?${query({ phone: identity.phone, license_plate: identity.plate })}`, { method: "POST" });
      saveParkingSession(updated);
      showToast("success", `Parking finished. Final cost: $${updated.total_cost}.`);
      navigate("/my");
    } catch (error) {
      const nextMessage = (error as Error).message;
      setMessage(nextMessage);
      showToast("error", nextMessage);
    } finally {
      setActiveAction(null);
    }
  }

  if (message && !item) return <main className="page"><section className="panel"><p className="error">{message}</p><Link className="button secondary" to="/my">Go to My parking</Link></section></main>;
  if (!item) return <PageLoader label="Loading parking session" />;

  const isCompleted = item.status === "completed";
  const elapsed = isCompleted && item.ended_at ? new Date(item.ended_at).getTime() - new Date(item.started_at).getTime() : now - new Date(item.started_at).getTime();
  const statusText = isCompleted ? "Parking completed" : item.status === "overdue" ? "Parking overdue" : "Parking active";

  return (
    <main className="active-page">
      <section className="active-hero">
        <span className={`active-status ${item.status}`}><i className="live-dot" />{statusText}</span>
        <p>Your assigned spot</p>
        <h1>{String(item.spot.number).padStart(2, "0")}</h1>
        <div className="active-stats"><div><small>Elapsed time</small><strong>{formatDuration(elapsed)}</strong></div><div><small>{isCompleted ? "Final cost" : "Estimated cost"}</small><strong>{isCompleted && item.total_cost ? `$${item.total_cost}` : estimatedCost ? `$${estimatedCost}` : "—"}</strong></div></div>
        {!isCompleted && <div className="active-actions"><button className="button active-secondary" disabled={activeAction !== null} onClick={() => { setExtensionMinutes(30); setCustomExtensionHours(""); setShowExtension((value) => !value); }}>{activeAction === "extend" ? <ButtonLoader label="Extending…" /> : "Extend parking"}</button><button className="button active-primary" disabled={activeAction !== null} onClick={complete}>{activeAction === "complete" ? <ButtonLoader label="Finishing…" /> : "Finish parking"}</button></div>}
        {!isCompleted && <Link className="active-history-link" to="/my">Parking history and upcoming bookings →</Link>}
        {isCompleted && <Link className="button active-primary completed-link" to="/">Back to home</Link>}
      </section>
      <aside className="active-sidebar">
        {!isCompleted && <SessionProgress item={item} currentTime={now} />}
        <section className="active-card"><h2>Session details</h2><dl><div><dt>Vehicle</dt><dd>{item.license_plate}</dd></div><div><dt>Spot type</dt><dd>{spotLabels[item.spot.spot_type]}</dd></div><div><dt>{isCompleted ? "Ended at" : "Expected end"}</dt><dd>{new Date(isCompleted && item.ended_at ? item.ended_at : item.expected_end_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</dd></div></dl></section>
        {showExtension && <section className="extension-card"><h2>Request extension</h2><p>Add time to your current parking session. Availability will be checked before it is confirmed.</p><ExtensionDurationPicker presetMinutes={extensionMinutes} customHours={customExtensionHours} onPresetChange={setExtensionMinutes} onCustomHoursChange={setCustomExtensionHours} /><button className="button primary full" disabled={activeAction !== null} onClick={extend}>{activeAction === "extend" ? <ButtonLoader label="Checking…" /> : "Check availability"}</button></section>}
        {message && <p className="session-message">{message}</p>}
      </aside>
    </main>
  );
}
