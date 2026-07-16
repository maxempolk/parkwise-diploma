export type SpotType = "standard" | "ev" | "accessible";

export interface Spot {
  id: number;
  number: number;
  spot_type: SpotType;
  is_active: boolean;
  is_blocked: boolean;
  block_reason: string | null;
}

export interface Reservation {
  id: number;
  phone: string;
  license_plate: string;
  spot_type: SpotType;
  starts_at: string;
  ends_at: string;
  status: string;
}

export interface ParkingSession {
  id: number;
  reservation_id: number | null;
  spot_id: number;
  phone: string;
  license_plate: string;
  started_at: string;
  expected_end_at: string;
  ended_at: string | null;
  status: string;
  rate_per_30_minutes: string | null;
  total_cost: string | null;
  spot: Spot;
}

export interface GuestOverview {
  reservations: Reservation[];
  sessions: ParkingSession[];
}

export interface Availability {
  standard: number;
  ev: number;
  accessible: number;
  total: number;
}

export interface Tariff {
  id: number;
  spot_type: SpotType;
  price_per_30_minutes: string;
}

export interface SessionEstimate {
  estimated_cost: string;
}
