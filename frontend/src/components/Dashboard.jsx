import { BarChart3, BookOpen, CheckCircle2, Clock3, FileWarning, HardDrive, LayoutTemplate, Link2, RefreshCw } from 'lucide-react';

const metricIcons = {
  words: BarChart3,
  queued: Clock3,
  published: CheckCircle2,
  failed: FileWarning,
  templates: LayoutTemplate
};

export default function Dashboard({ analytics, driveStatus, onRefresh, onDriveConnect, onDriveRefresh, onOpenGenerator }) {
  const metrics = ['words', 'queued', 'published', 'failed', 'templates'];
  const driveReady = Boolean(driveStatus?.configured && driveStatus?.connected);

  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Dashboard</h2>
        <div className="actions">
          <button className="ghost-btn" onClick={onRefresh}><RefreshCw size={17} /> Refresh</button>
          {driveReady ? (
            <button className="primary-btn" onClick={onDriveRefresh}><RefreshCw size={17} /> Refresh Drive</button>
          ) : (
            <button className="primary-btn" onClick={onDriveConnect}><Link2 size={17} /> Connect Drive</button>
          )}
        </div>
      </div>
      <div className="panel drive-status-panel">
        <div className="panel-title"><HardDrive size={17} /> Google Drive</div>
        <strong>{driveReady ? 'Connected' : driveStatus?.configured ? 'Not connected' : 'OAuth credentials needed'}</strong>
        <span>{driveStatus?.account_email || driveStatus?.root_folder_name || 'writing-telegram-channel'}</span>
        {driveStatus?.redirect_uri ? <small>{driveStatus.redirect_uri}</small> : null}
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
        <small>Prepare Drive-backed vocabulary batches with saved templates, audio, and captions.</small>
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
