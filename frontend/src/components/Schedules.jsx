import { Pause, Play, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api/client.js';

const defaultForm = {
  name: '',
  timezone: 'Asia/Tashkent',
  days: 'mon,tue,wed,thu,fri',
  times: '09:00,18:00',
  random_interval_minutes: ''
};

export default function Schedules({ schedules, onChanged }) {
  const [form, setForm] = useState(defaultForm);

  async function submit(event) {
    event.preventDefault();
    await api.createSchedule({
      name: form.name,
      timezone: form.timezone,
      days: form.days.split(',').map((item) => item.trim()).filter(Boolean),
      times: form.times.split(',').map((item) => item.trim()).filter(Boolean),
      random_interval_minutes: form.random_interval_minutes ? Number(form.random_interval_minutes) : null
    });
    setForm(defaultForm);
    onChanged();
  }

  async function toggle(schedule) {
    await api.updateSchedule(schedule.id, { is_paused: !schedule.is_paused });
    onChanged();
  }

  async function remove(id) {
    if (!window.confirm('Delete this schedule?')) return;
    await api.deleteSchedule(id);
    onChanged();
  }

  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Scheduler</h2>
        <div className="actions">
          <button className="ghost-btn" onClick={async () => { await api.pauseScheduler(); onChanged(); }}><Pause size={17} /> Pause</button>
          <button className="primary-btn" onClick={async () => { await api.resumeScheduler(); onChanged(); }}><Play size={17} /> Resume</button>
        </div>
      </div>
      <form className="panel form-grid" onSubmit={submit}>
        <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
        <label>Timezone<input value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} /></label>
        <label>Days<input value={form.days} onChange={(event) => setForm({ ...form, days: event.target.value })} /></label>
        <label>Times<input value={form.times} onChange={(event) => setForm({ ...form, times: event.target.value })} /></label>
        <label>Random minutes<input type="number" min="0" value={form.random_interval_minutes} onChange={(event) => setForm({ ...form, random_interval_minutes: event.target.value })} /></label>
        <button className="primary-btn form-submit" type="submit"><Plus size={17} /> Add schedule</button>
      </form>
      <div className="table-panel">
        <table>
          <thead>
            <tr><th>Name</th><th>Days</th><th>Times</th><th>Timezone</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {schedules.length === 0 ? <tr><td colSpan={6} className="muted">No schedules yet.</td></tr> : null}
            {schedules.map((schedule) => (
              <tr key={schedule.id}>
                <td>{schedule.name}</td>
                <td>{schedule.days.join(', ')}</td>
                <td>{schedule.times.join(', ')}</td>
                <td>{schedule.timezone}</td>
                <td><span className={`pill ${schedule.is_paused ? 'warn' : 'ok'}`}>{schedule.is_paused ? 'Paused' : 'Active'}</span></td>
                <td className="actions">
                  <button className="icon-btn" onClick={() => toggle(schedule)} title={schedule.is_paused ? 'Resume' : 'Pause'}>{schedule.is_paused ? <Play size={16} /> : <Pause size={16} />}</button>
                  <button className="icon-btn danger" onClick={() => remove(schedule.id)} title="Delete schedule"><Trash2 size={16} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
