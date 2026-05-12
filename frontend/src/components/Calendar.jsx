export default function Calendar({ items }) {
  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Calendar</h2>
      </div>
      <div className="table-panel">
        <table>
          <thead>
            <tr><th>Word</th><th>Status</th><th>Scheduled</th><th>Published</th></tr>
          </thead>
          <tbody>
            {items.length === 0 ? <tr><td colSpan={4} className="muted">No posts yet.</td></tr> : null}
            {items.map((post) => (
              <tr key={post.id}>
                <td>{post.word.word}</td>
                <td><span className={`pill ${post.status}`}>{post.status}</span></td>
                <td>{post.scheduled_at ? new Date(post.scheduled_at).toLocaleString() : 'unscheduled'}</td>
                <td>{post.published_at ? new Date(post.published_at).toLocaleString() : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
