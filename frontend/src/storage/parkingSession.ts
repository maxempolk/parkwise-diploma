import type { ParkingSession } from "../types";

const parkingSessionStorageKey = "parkwise.parkingSession";

function getStorage() {
  return typeof window === "undefined" ? undefined : window.localStorage;
}

export function saveParkingSession(session: ParkingSession) {
  getStorage()?.setItem(parkingSessionStorageKey, JSON.stringify(session));
}

export function getGuestIdentity() {
  const storage = getStorage();
  return {
    phone: storage?.getItem("phone") ?? "",
    plate: storage?.getItem("licensePlate") ?? "",
  };
}

export function saveGuestIdentity(phone: string, plate: string) {
  const storage = getStorage();
  storage?.setItem("phone", phone);
  storage?.setItem("licensePlate", plate);
}
