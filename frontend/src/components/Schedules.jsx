import { Pause, Play, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api } from '../api/client.js';

const defaultForm = {
  name: '',
  batch_id: '',
  timezone: 'Asia/Tashkent',
  start_date: '',
  end_date: '',
  posts_per_day: '5',
  dispatch_mode: 'even',
  window_start: '09:00',
  window_end: '18:00',
  manual_times: '09:00,12:00,15:00,18:00'
};

export default function Schedules({ schedules, batches, onChanged }) {
  const [form, setForm] = useState(defaultForm);
  const readyBatches = useMemo(() => batches.filter((batch) => batch.status === 'ready'), [batches]);

  async function submit(event) {
    event.preventDefault();
    await api.createSchedule({
      ...form,
      batch_id: Number(form.batch_id),
      posts_per_day: Number(form.posts_per_day),
      manual_times: form.manual_times.split(',').map((item) => item.trim()).filter(Boolean)
    });
    setForm(defaultForm);
    onChanged();
  }

  async function toggle(schedule) {
    await api.updateSchedule(schedule.id, { is_paused: !schedule.is_paused });
    onChanged();
  }

  async function remove(id) {
    if (!window.confirm('Delete this schedule? Unpublished posts return to the batch.')) return;
    await api.deleteSchedule(id);
    onChanged();
  }

  return (
    <section className="view-grid">
      <div className="toolbar">
        <div>
          <h2>Scheduler</h2>
          <p className="toolbar-subtitle">Assign prepared vocabulary batches to concrete publish dates and times.</p>
        </div>
        <div className="actions">
          <button className="ghost-btn" onClick={async () => { await api.pauseScheduler(); onChanged(); }}><Pause size={17} /> Pause engine</button>
          <button className="primary-btn" onClick={async () => { await api.resumeScheduler(); onChanged(); }}><Play size={17} /> Resume engine</button>
        </div>
      </div>
      <form className="panel schedule-form" onSubmit={submit}>
        <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
        <label>Content type
          <select value="vocabulary" disabled>
            <option value="vocabulary">Vocabulary</option>
          </select>
        </label>
        <label>Prepared batch
          <select required value={form.batch_id} onChange={(event) => setForm({ ...form, batch_id: event.target.value })}>
            <option value="">Select batch</option>
            {readyBatches.map((batch) => (
              <option key={batch.id} value={batch.id}>{batch.name} · {batch.generated_items} posts</option>
            ))}
          </select>
        </label>
        <label>Timezone<input value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} /></label>
        <label>Start date<input required type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></label>
        <label>End date<input required type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} /></label>
        <label>Posts per day<input type="number" min="1" value={form.posts_per_day} onChange={(event) => setForm({ ...form, posts_per_day: event.target.value })} /></label>
        <label>Timing mode
          <select value={form.dispatch_mode} onChange={(event) => setForm({ ...form, dispatch_mode: event.target.value })}>
            <option value="even">Evenly spaced</option>
            <option value="manual">Specific times</option>
          </select>
        </label>
        {form.dispatch_mode === 'even' ? (
          <>
            <label>From<input type="time" value={form.window_start} onChange={(event) => setForm({ ...form, window_start: event.target.value })} /></label>
            <label>Until<input type="time" value={form.window_end} onChange={(event) => setForm({ ...form, window_end: event.target.value })} /></label>
          </>
        ) : (
          <label className="schedule-times">Specific times<input value={form.manual_times} onChange={(event) => setForm({ ...form, manual_times: event.target.value })} placeholder="09:00,12:00,15:00" /></label>
        )}
        <button className="primary-btn form-submit" type="submit"><Plus size={17} /> Create schedule</button>
      </form>
      <div className="table-panel">
        <table>
          <thead>
            <tr><th>Name</th><th>Batch</th><th>Date range</th><th>Plan</th><th>Posts</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {schedules.length === 0 ? <tr><td colSpan={7} className="muted">No schedules yet.</td></tr> : null}
            {schedules.map((schedule) => (
              <tr key={schedule.id}>
                <td>{schedule.name}</td>
                <td>{schedule.batch_name || '-'}</td>
                <td>{schedule.start_date} to {schedule.end_date}</td>
                <td>{schedule.dispatch_mode === 'manual' ? schedule.manual_times.join(', ') : `${schedule.posts_per_day}/day, ${schedule.window_start}-${schedule.window_end}`}</td>
                <td>{schedule.scheduled_post_count}</td>
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
