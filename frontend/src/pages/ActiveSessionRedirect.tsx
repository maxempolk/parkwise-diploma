import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { api, query } from "../api";
import { getGuestIdentity } from "../storage/parkingSession";
import { PageLoader } from "../components/LoadingIndicator";
import type { GuestOverview } from "../types";

export function ActiveSessionRedirect() {
  const navigate = useNavigate();

  useEffect(() => {
    const { phone, plate } = getGuestIdentity();
    if (!phone || !plate) { navigate("/my", { replace: true }); return; }
    api<GuestOverview>(`/api/me?${query({ phone, license_plate: plate })}`)
      .then((overview) => {
        const active = overview.sessions.find((session) => session.status === "active" || session.status === "overdue");
        navigate(active ? `/sessions/${active.id}` : "/my", { replace: true });
      })
      .catch(() => navigate("/my", { replace: true }));
  }, [navigate]);

  return <PageLoader label="Opening active parking" />;
}
