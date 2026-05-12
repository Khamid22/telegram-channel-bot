import { BarChart3, BookOpen, CheckCircle2, Clock3, FileWarning, LayoutTemplate, RefreshCw } from 'lucide-react';

const metricIcons = {
  words: BarChart3,
  queued: Clock3,
  published: CheckCircle2,
  failed: FileWarning,
  templates: LayoutTemplate
};

export default function Dashboard({ analytics, onRefresh, onSync, onOpenGenerator }) {
  const metrics = ['words', 'queued', 'published', 'failed', 'templates'];

  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Dashboard</h2>
        <div className="actions">
          <button className="ghost-btn" onClick={onRefresh}><RefreshCw size={17} /> Refresh</button>
          <button className="primary-btn" onClick={onSync}><RefreshCw size={17} /> Sync Sheets</button>
        </div>
      </div>
      <div className="metrics-grid">
        {metrics.map((name) => {
          const Icon = metricIcons[name];
          return (
            <article className="metric-tile" key={name}>
              <div className="metric-label"><Icon size={18} /> {name}</div>
              <strong>{analytics?.[name] ?? 0}</strong>
            </article>
          );
        })}
      </div>
      <button className="generator-cta panel" onClick={onOpenGenerator}>
        <span>
          <BookOpen size={22} />
          <strong>Open Card Generator</strong>
        </span>
        <small>Preview the Multilevel Essays template and export PNG cards.</small>
      </button>
      <div className="panel">
        <div className="panel-title">Recent Logs</div>
        <div className="log-list">
          {(analytics?.recent_logs || []).map((log) => (
            <div className="log-row" key={log.id}>
              <span className={`status-dot ${log.level}`}></span>
              <span>{log.event}</span>
              <small>{log.message}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
