import { useState } from "react";
import { useAuth } from "../lib/auth.jsx";
import { useRoute } from "../lib/router.jsx";
import { ApiError } from "../lib/api.js";

const SAMPLE = [
  ["09:41", "Transfer · Ada O.", "₦12,500", false],
  ["09:42", "Card payment · Grocer", "₦6,380", false],
  ["09:44", "Transfer · new payee, new device", "₦850,000", true],
  ["09:45", "Airtime · MTN", "₦1,000", false],
];

export default function Login() {
  const { login } = useAuth();
  const { navigate } = useRoute();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (e) {
      // 401 from the login endpoint means wrong credentials (not an expired session).
      setError(e instanceof ApiError && e.status === 401 ? "Email or password is wrong." : e.message);
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <aside className="login-side">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><i /></span>
          Fraud Watch
        </div>
        <div>
          <h2>Every transaction is checked before the money settles.</h2>
        </div>
        <div className="ledger" aria-label="Sample transactions">
          {SAMPLE.map(([time, text, amount, flag]) => (
            <div key={time}>
              <span>{time}</span>
              <span className={flag ? "flag" : undefined}>{text}</span>
              <span className="num">{amount}</span>
            </div>
          ))}
        </div>
      </aside>

      <main className="login-main">
        <form className="login-form" onSubmit={submit}>
          <div>
            <h1>Sign in</h1>
            <p className="muted" style={{ marginTop: 6 }}>Use the email and password for your account.</p>
          </div>
          {error && <div className="notice error" role="alert">{error}</div>}
          <label className="field">
            <span>Email</span>
            <input className="input" type="email" autoComplete="username" required autoFocus
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            <span>Password</span>
            <input className="input" type="password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          {import.meta.env?.DEV && (
            <p className="demo-hint">
              After <code>python manage.py seed_demo</code>: <code>admin@example.com</code>,{" "}
              <code>analyst@example.com</code> or <code>chidi@example.com</code>, password{" "}
              <code>Demo-Passw0rd!</code>
            </p>
          )}
        </form>
      </main>
    </div>
  );
}
