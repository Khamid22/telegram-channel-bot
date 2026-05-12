import { BookOpen, CalendarDays, LayoutDashboard, LayoutTemplate, ListTodo, LogOut, Timer, TriangleAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client.js';
import Calendar from './components/Calendar.jsx';
import Dashboard from './components/Dashboard.jsx';
import FailedJobs from './components/FailedJobs.jsx';
import Login from './components/Login.jsx';
import Queue from './components/Queue.jsx';
import Schedules from './components/Schedules.jsx';
import Templates from './components/Templates.jsx';
import VocabPostGenerator from './components/VocabPostGenerator.jsx';

const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'generator', label: 'Generator', icon: BookOpen },
  { id: 'schedules', label: 'Scheduler', icon: Timer },
  { id: 'queue', label: 'Queue', icon: ListTodo },
  { id: 'calendar', label: 'Calendar', icon: CalendarDays },
  { id: 'templates', label: 'Templates', icon: LayoutTemplate },
  { id: 'failed', label: 'Failed', icon: TriangleAlert }
];

function tabFromHash() {
  const id = window.location.hash.replace('#', '');
  return tabs.some((tab) => tab.id === id) ? id : 'dashboard';
}

export default function App() {
  const [user, setUser] = useState(null);
  const [active, setActive] = useState(tabFromHash);
  const [analytics, setAnalytics] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [queue, setQueue] = useState([]);
  const [calendar, setCalendar] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [failed, setFailed] = useState([]);
  const [notice, setNotice] = useState('');

  const activeTab = useMemo(() => tabs.find((tab) => tab.id === active), [active]);

  async function loadAll() {
    // allSettled so one failing endpoint doesn't wipe all other state
    const [analyticsRes, schedulesRes, queueRes, calendarRes, templatesRes, failedRes] = await Promise.allSettled([
      api.analytics(),
      api.schedules(),
      api.queue(),
      api.calendar(),
      api.templates(),
      api.failedJobs()
    ]);
    if (analyticsRes.status === 'fulfilled') setAnalytics(analyticsRes.value);
    if (schedulesRes.status === 'fulfilled') setSchedules(schedulesRes.value.items ?? []);
    if (queueRes.status === 'fulfilled') setQueue(queueRes.value.items ?? []);
    if (calendarRes.status === 'fulfilled') setCalendar(calendarRes.value.items ?? []);
    if (templatesRes.status === 'fulfilled') setTemplates(templatesRes.value.items ?? []);
    if (failedRes.status === 'fulfilled') setFailed(failedRes.value.items ?? []);
  }

  async function boot() {
    try {
      const data = await api.me();
      setUser(data.user);
    } catch {
      // api.me() failed — not logged in
      setUser(null);
      return;
    }
    await loadAll();
  }

  useEffect(() => {
    boot();
  }, []);

  useEffect(() => {
    function syncHash() {
      setActive(tabFromHash());
    }
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  function openTab(tabId) {
    setActive(tabId);
    window.location.hash = tabId;
  }

  async function syncSheets() {
    const data = await api.syncSheets();
    setNotice(`Synced ${data.synced} rows`);
    await loadAll();
  }

  async function logout() {
    await api.logout();
    setUser(null);
  }

  if (!user) {
    return <Login onLogin={async (loggedInUser) => { setUser(loggedInUser); await loadAll(); }} />;
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row compact">
          <span className="brand-mark">M</span>
          <div>
            <h1>Multilevel Essays</h1>
            <p>{user.username}</p>
          </div>
        </div>
        <nav className="tab-list" aria-label="Admin sections">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button className={active === tab.id ? 'active' : ''} key={tab.id} onClick={() => openTab(tab.id)}>
                <Icon size={18} />
                {tab.label}
              </button>
            );
          })}
        </nav>
        <button className="logout-btn" onClick={logout}><LogOut size={17} /> Sign out</button>
      </aside>
      <section className="content-shell">
        <header className="topbar">
          <div>
            <span>{activeTab?.label}</span>
            {notice ? <small>{notice}</small> : null}
          </div>
          <button className="primary-btn" onClick={() => openTab('generator')}>
            <BookOpen size={17} /> Generator
          </button>
        </header>
        {active === 'dashboard' ? <Dashboard analytics={analytics} onRefresh={loadAll} onSync={syncSheets} onOpenGenerator={() => openTab('generator')} /> : null}
        {active === 'schedules' ? <Schedules schedules={schedules} onChanged={loadAll} /> : null}
        {active === 'queue' ? <Queue items={queue} onChanged={loadAll} /> : null}
        {active === 'calendar' ? <Calendar items={calendar} /> : null}
        {active === 'generator' ? <VocabPostGenerator /> : null}
        {active === 'templates' ? <Templates templates={templates} onChanged={loadAll} /> : null}
        {active === 'failed' ? <FailedJobs items={failed} onChanged={loadAll} /> : null}
      </section>
    </main>
  );
}
