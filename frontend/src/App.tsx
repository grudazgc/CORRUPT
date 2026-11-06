import { NavLink, Route, Routes } from "react-router-dom";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";

import Home from "./pages/Home";
import SubmitReport from "./pages/SubmitReport";
import MyReports from "./pages/MyReports";
import ReportDetail from "./pages/ReportDetail";
import Transparency from "./pages/Transparency";
import Verifier from "./pages/Verifier";
import Admin from "./pages/Admin";

export default function App() {
  return (
    <div className="layout">
      <header className="site">
        <div className="brand">
          CORRUPT <small>anti-corruption reporting</small>
        </div>
        <nav className="site">
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/submit">Submit a report</NavLink>
          <NavLink to="/reports">My reports</NavLink>
          <NavLink to="/transparency">Transparency</NavLink>
          <NavLink to="/verifier">Verifier</NavLink>
          <NavLink to="/admin">Admin</NavLink>
          <WalletMultiButton />
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/submit" element={<SubmitReport />} />
          <Route path="/reports" element={<MyReports />} />
          <Route path="/reports/:id" element={<ReportDetail />} />
          <Route path="/transparency" element={<Transparency />} />
          <Route path="/verifier" element={<Verifier />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </main>

      <footer className="site">
        <p>
          Reports are anchored on Solana as content hashes. Verified reporters
          receive CORRUPT tokens from the on-chain reward pool.
        </p>
        <p className="muted">
          Submitting a report never costs you tokens. Only you can decrypt the
          evidence you upload.
        </p>
      </footer>
    </div>
  );
}
