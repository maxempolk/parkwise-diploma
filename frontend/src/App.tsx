import { Link, Route, Routes } from "react-router-dom";

import { ActiveSession } from "./pages/ActiveSession";
import { ActiveSessionRedirect } from "./pages/ActiveSessionRedirect";
import { Admin } from "./pages/Admin";
import { Home } from "./pages/Home";
import { MyParking } from "./pages/MyParking";
import { ParkingForm } from "./pages/ParkingForm";
import { ReservationDetails } from "./pages/ReservationDetails";
import { ToastProvider } from "./components/ToastProvider";

function App() {
  return (
    <ToastProvider>
      <header className="header">
        <Link className="brand" to="/"><span className="brand-mark">P</span><span>Parkwise</span></Link>
      </header>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/quick" element={<ParkingForm quick />} />
        <Route path="/book" element={<ParkingForm />} />
        <Route path="/my" element={<MyParking />} />
        <Route path="/active" element={<ActiveSessionRedirect />} />
        <Route path="/sessions/:sessionId" element={<ActiveSession />} />
        <Route path="/reservations/:reservationId" element={<ReservationDetails />} />
        <Route path="/admin/*" element={<Admin />} />
      </Routes>
    </ToastProvider>
  );
}

export default App;
