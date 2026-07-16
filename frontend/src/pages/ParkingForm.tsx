import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, query } from "../api";
import { spotLabels } from "../constants";
import { IdentityFields } from "../components/IdentityFields";
import { ButtonLoader, InlineLoader } from "../components/LoadingIndicator";
import { useToast } from "../components/ToastProvider";
import { getGuestIdentity, saveGuestIdentity, saveParkingSession } from "../storage/parkingSession";
import type { Availability, ParkingSession, SpotType, Tariff } from "../types";

interface ParkingFormProps {
  quick?: boolean;
}

const bookingDurations = [
  { minutes: 30, label: "30 min" },
  { minutes: 60, label: "1 hour" },
  { minutes: 120, label: "2 hours" },
  { minutes: 180, label: "3 hours" },
  { minutes: 240, label: "4 hours" },
  { minutes: 360, label: "6 hours" },
  { minutes: 480, label: "8 hours" },
  { minutes: 720, label: "12 hours" },
  { minutes: 1440, label: "24 hours" },
];

function nextHalfHour() {
  const value = new Date();
  value.setSeconds(0, 0);
  value.setMinutes(value.getMinutes() < 30 ? 30 : 0);
  if (value.getMinutes() === 0) value.setHours(value.getHours() + 1);
  return value;
}

function dateValue(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function timeValue(value: Date) {
  return `${String(value.getHours()).padStart(2, "0")}:${String(value.getMinutes()).padStart(2, "0")}`;
}

export function ParkingForm({ quick = false }: ParkingFormProps) {
  const navigate = useNavigate();
  const identity = getGuestIdentity();
  const [phone, setPhone] = useState(identity.phone);
  const [plate, setPlate] = useState(identity.plate);
  const [spotType, setSpotType] = useState<SpotType>("standard");
  const initialStart = useMemo(nextHalfHour, []);
  const [arrivalDate, setArrivalDate] = useState(() => dateValue(initialStart));
  const [arrivalTime, setArrivalTime] = useState(() => timeValue(initialStart));
  const [presetDurationMinutes, setPresetDurationMinutes] = useState(60);
  const [customHours, setCustomHours] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const { showToast } = useToast();

  const hasCustomDuration = customHours.trim() !== "";
  const customDurationHours = Number(customHours);
  const customDurationIsValid = !hasCustomDuration || (
    Number.isFinite(customDurationHours)
    && customDurationHours >= 0.5
    && customDurationHours <= 24
    && Number.isInteger(customDurationHours * 2)
  );
  const durationMinutes = hasCustomDuration && customDurationIsValid ? customDurationHours * 60 : presetDurationMinutes;

  const period = useMemo(() => {
    if (hasCustomDuration && !customDurationIsValid) return null;
    if (!arrivalDate || !arrivalTime) return null;
    const startsAt = new Date(`${arrivalDate}T${arrivalTime}`);
    if (Number.isNaN(startsAt.getTime())) return null;
    const endsAt = new Date(startsAt.getTime() + durationMinutes * 60_000);
    return { startsAt, endsAt };
  }, [arrivalDate, arrivalTime, customDurationIsValid, durationMinutes, hasCustomDuration]);

  const availabilityPath = useMemo(() => {
    if (quick) return "/api/availability";
    if (!period) return null;
    return `/api/availability?${query({ starts_at: period.startsAt.toISOString(), ends_at: period.endsAt.toISOString() })}`;
  }, [period, quick]);

  useEffect(() => {
    api<Tariff[]>("/api/tariffs").then(setTariffs).catch(() => setTariffs([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!availabilityPath) { setAvailability(null); setAvailabilityLoading(false); return () => { cancelled = true; }; }
    setAvailability(null);
    setAvailabilityLoading(true);
    api<Availability>(availabilityPath)
      .then((result) => { if (!cancelled) setAvailability(result); })
      .catch(() => { if (!cancelled) setAvailability(null); })
      .finally(() => { if (!cancelled) setAvailabilityLoading(false); });
    return () => { cancelled = true; };
  }, [availabilityPath]);

  const selectedAvailability = availability?.[spotType];
  const selectedTariff = tariffs.find((item) => item.spot_type === spotType);
  const selectedUnavailable = selectedAvailability === 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    saveGuestIdentity(phone, plate);

    try {
      if (quick) {
        const session = await api<ParkingSession>("/api/parking/quick", { method: "POST", body: JSON.stringify({ phone, license_plate: plate, spot_type: spotType }) });
        saveParkingSession(session);
        showToast("success", `Parking started at spot ${session.spot.number}.`);
        navigate(`/sessions/${session.id}`);
      } else {
        if (!period) throw new Error("Choose an arrival time and a duration between 0.5 and 24 hours.");
        await api("/api/reservations", { method: "POST", body: JSON.stringify({ phone, license_plate: plate, spot_type: spotType, starts_at: period.startsAt.toISOString(), ends_at: period.endsAt.toISOString() }) });
        showToast("success", "Reservation confirmed.");
        navigate("/my");
      }
    } catch (error) {
      const nextMessage = (error as Error).message;
      setMessage(nextMessage);
      showToast("error", nextMessage);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page form-page">
      <section>
        <Link className="back" to="/">← Back</Link>
        <p className="eyebrow">{quick ? "Arriving now" : "Plan your visit"}</p>
        <h1>{quick ? "Let’s find your spot." : "Book in advance."}</h1>
        <p className="lead">{quick ? "Choose the type you need. Parking starts immediately after a spot is assigned." : "Reserve the right type of spot up to 30 days ahead."}</p>
        <form onSubmit={submit}>
          {!quick && <section className="booking-time" aria-labelledby="arrival-heading">
            <div className="booking-time-heading"><div><span className="step-label">01</span><h2 id="arrival-heading">When are you arriving?</h2></div><p>Choose a time, then set how long you’ll stay.</p></div>
            <div className="booking-arrival-fields"><label>Arrival date<input required type="date" min={dateValue(new Date())} max={dateValue(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000))} value={arrivalDate} onChange={(event) => setArrivalDate(event.target.value)} /></label><label>Arrival time<select value={arrivalTime} onChange={(event) => setArrivalTime(event.target.value)}>{Array.from({ length: 48 }, (_, index) => { const hours = String(Math.floor(index / 2)).padStart(2, "0"); const minutes = index % 2 ? "30" : "00"; const value = `${hours}:${minutes}`; return <option key={value} value={value}>{value}</option>; })}</select></label></div>
            <fieldset className="duration-picker"><legend>Parking duration</legend><div>{bookingDurations.map((item) => <button key={item.minutes} className={!hasCustomDuration && presetDurationMinutes === item.minutes ? "selected" : ""} type="button" onClick={() => { setPresetDurationMinutes(item.minutes); setCustomHours(""); }} aria-pressed={!hasCustomDuration && presetDurationMinutes === item.minutes}>{item.label}</button>)}</div></fieldset>
            <label className="custom-duration">Custom hours<input type="number" inputMode="decimal" min="0.5" max="24" step="0.5" value={customHours} onChange={(event) => setCustomHours(event.target.value)} placeholder="For example, 1.5" /><small>From 0.5 to 24 hours, in 30-minute steps.</small></label>
            {period && <p className="departure-preview"><span>Departure</span><strong>{period.endsAt.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} · {timeValue(period.endsAt)}</strong></p>}
            {hasCustomDuration && !customDurationIsValid && <p className="duration-error">Enter a duration from 0.5 to 24 hours in 30-minute steps.</p>}
          </section>}
          <fieldset>
            <legend>Spot type</legend>
            <div className="spot-options">
              {Object.entries(spotLabels).map(([value, label]) => {
                const currentType = value as SpotType;
                const count = availability?.[currentType];
                const tariff = tariffs.find((item) => item.spot_type === currentType);
                const unavailable = count === 0;
                const detail = availability ? `${count} available` : availabilityLoading ? <><InlineLoader label="Checking availability" />Checking availability</> : quick ? "Checking availability…" : "Choose a period to check availability";
                return <label key={value} className={`spot-option ${spotType === value ? "selected" : ""} ${unavailable ? "unavailable" : ""}`}><input disabled={unavailable} type="radio" name="spotType" value={value} checked={spotType === value} onChange={() => setSpotType(currentType)} /><span><strong>{label}</strong><small><b>{detail}</b>{tariff && <em>${tariff.price_per_30_minutes} / 30 min</em>}</small></span></label>;
              })}
            </div>
          </fieldset>
          <div className="form-grid"><IdentityFields phone={phone} plate={plate} setPhone={setPhone} setPlate={setPlate} /></div>
          {quick && <div className="notice"><strong>Four-hour limit.</strong> You can request an extension later if it does not affect upcoming reservations.</div>}
          {message && <p className="error" role="alert">{message}</p>}
          {selectedUnavailable && <p className="notice">No {spotLabels[spotType].toLowerCase()} spots are available for this period. Choose another type or time.</p>}
          <button className="button primary full" disabled={busy || selectedUnavailable || (!quick && !customDurationIsValid)}>{busy ? <ButtonLoader label={quick ? "Starting parking…" : "Confirming booking…"} /> : quick ? "Start parking" : "Confirm booking"}</button>
        </form>
      </section>
      <aside className="form-aside"><span><i className="live-dot" />{quick ? "Available now" : "Selected period"}</span><p><strong>{availability?.total ?? "—"}</strong> open spots</p><small>{availability ? `${selectedAvailability ?? 0} ${spotLabels[spotType].toLowerCase()} spots available${selectedTariff ? ` · $${selectedTariff.price_per_30_minutes} per 30 min` : ""}.` : availabilityLoading ? <><InlineLoader label="Checking availability" />Checking availability</> : quick ? "Checking live parking availability." : "Choose arrival and departure to check live availability."}</small></aside>
    </main>
  );
}
