interface ExtensionDurationPickerProps {
  presetMinutes: number;
  customHours: string;
  maxHours: number;
  onPresetChange: (minutes: number) => void;
  onCustomHoursChange: (value: string) => void;
}

const durationOptions = [
  { minutes: 30, label: "30 min" },
  { minutes: 60, label: "1 hour" },
  { minutes: 120, label: "2 hours" },
  { minutes: 180, label: "3 hours" },
  { minutes: 240, label: "4 hours" },
];

export function ExtensionDurationPicker({ presetMinutes, customHours, maxHours, onPresetChange, onCustomHoursChange }: ExtensionDurationPickerProps) {
  const hasCustomDuration = customHours.trim() !== "";
  const customHoursNumber = Number(customHours);
  const customDurationIsValid = !hasCustomDuration || (
    Number.isFinite(customHoursNumber)
    && customHoursNumber >= 0.5
    && customHoursNumber <= maxHours
    && Number.isInteger(customHoursNumber * 2)
  );

  return <>
    <fieldset className="duration-picker extension-duration-picker"><legend>Extend by</legend><div>{durationOptions.filter((option) => option.minutes <= maxHours * 60).map((option) => <button key={option.minutes} className={!hasCustomDuration && presetMinutes === option.minutes ? "selected" : ""} type="button" aria-pressed={!hasCustomDuration && presetMinutes === option.minutes} onClick={() => { onPresetChange(option.minutes); onCustomHoursChange(""); }}>{option.label}</button>)}</div></fieldset>
    <label className="custom-duration">Custom hours<input type="number" inputMode="decimal" min="0.5" max={maxHours} step="0.5" value={customHours} onChange={(event) => onCustomHoursChange(event.target.value)} placeholder="For example, 1.5" /><small>From 0.5 to {maxHours} hours, in 30-minute steps.</small></label>
    {hasCustomDuration && !customDurationIsValid && <p className="duration-error">Enter a duration from 0.5 to {maxHours} hours in 30-minute steps.</p>}
  </>;
}
