import { KeyRound, LogIn } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api/client.js';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = await api.login({ username, password });
      onLogin(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={submit}>
        <div className="brand-row">
          <span className="brand-mark"><KeyRound size={22} /></span>
          <div>
            <h1>Multilevel Essays</h1>
            <p>Telegram publishing console</p>
          </div>
        </div>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
        </label>
        {error ? <div className="error-line">{error}</div> : null}
        <button className="primary-btn" type="submit" disabled={loading}>
          <LogIn size={18} />
          {loading ? 'Signing in' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}
