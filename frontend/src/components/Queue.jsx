import { Play, Volume2 } from 'lucide-react';
import { api } from '../api/client.js';

export default function Queue({ items, onChanged }) {
  async function publish(id) {
    await api.publishPost(id);
    onChanged();
  }

  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Queue</h2>
        <div className="actions">
          <button className="primary-btn" onClick={async () => { await api.publishManual(); onChanged(); }}><Play size={17} /> Manual publish</button>
        </div>
      </div>
      <div className="queue-list">
        {items.length === 0 ? <p className="muted">Queue is empty.</p> : null}
        {items.map((post) => (
          <article className="queue-item" key={post.id}>
            <div>
              <h3>{post.word.word}</h3>
              <p>{post.word.phonetic}</p>
              <span className={`pill ${post.status}`}>{post.status}</span>
            </div>
            <div className="queue-meta">
              {post.image_url ? <img src={post.image_url} alt={post.word.word} /> : null}
              <div className="audio-stack">
                {post.audio.map((audio) => (
                  <audio key={audio.id} controls src={audio.url} aria-label="pronunciation audio" />
                ))}
                {!post.audio.length ? <span className="muted"><Volume2 size={15} /> audio after publish</span> : null}
              </div>
              <button className="primary-btn" onClick={() => publish(post.id)}><Play size={17} /> Publish</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
