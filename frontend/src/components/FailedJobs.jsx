import { Play } from 'lucide-react';
import { api } from '../api/client.js';

export default function FailedJobs({ items, onChanged }) {
  async function retry(id) {
    await api.publishPost(id);
    onChanged();
  }

  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Failed Jobs</h2>
      </div>
      <div className="queue-list">
        {items.length === 0 ? <p className="muted">No failed jobs.</p> : null}
        {items.map((post) => (
          <article className="queue-item failed" key={post.id}>
            <div>
              <h3>{post.word.word}</h3>
              <p>{post.error_message}</p>
            </div>
            <div className="actions">
              <span className="pill failed">failed</span>
              <button className="primary-btn" onClick={() => retry(post.id)}><Play size={17} /> Retry</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
