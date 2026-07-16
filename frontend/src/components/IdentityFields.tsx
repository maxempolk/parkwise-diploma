interface IdentityFieldsProps {
  phone: string;
  plate: string;
  setPhone: (value: string) => void;
  setPlate: (value: string) => void;
}

export function IdentityFields({ phone, plate, setPhone, setPlate }: IdentityFieldsProps) {
  return (
    <>
      <label>
        Phone number
        <input required value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+1 555 0100" />
      </label>
      <label>
        License plate
        <input required value={plate} onChange={(event) => setPlate(event.target.value.toUpperCase())} placeholder="ABC 123" />
      </label>
    </>
  );
}
