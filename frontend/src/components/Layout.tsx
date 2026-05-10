import { BarChart3, BookOpen, Flame, Import, Library } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

const links = [
  { to: '/spark', label: 'Spark', icon: Flame },
  { to: '/library', label: 'Library', icon: Library },
  { to: '/import', label: 'Import', icon: Import },
  { to: '/insights', label: 'Insights', icon: BarChart3 }
];

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <NavLink to="/spark" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded bg-amber-500 text-slate-950">
              <BookOpen size={20} aria-hidden="true" />
            </span>
            <span>
              <span className="block text-lg font-semibold leading-tight">Synapse</span>
              <span className="block text-xs text-slate-400">Kindle highlights, local first</span>
            </span>
          </NavLink>

          <nav className="flex flex-wrap gap-2">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  [
                    'inline-flex h-10 items-center gap-2 rounded px-3 text-sm font-medium transition',
                    isActive
                      ? 'bg-slate-100 text-slate-950'
                      : 'text-slate-300 hover:bg-slate-900 hover:text-white'
                  ].join(' ')
                }
              >
                <Icon size={17} aria-hidden="true" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
