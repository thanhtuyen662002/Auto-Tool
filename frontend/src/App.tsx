import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import CreateProjectPage from './pages/CreateProjectPage';
import RenderQueuePage from './pages/RenderQueuePage';
import RenderSettingsPage from './pages/RenderSettingsPage';
import ResultPage from './pages/ResultPage';
import OutputReviewPage from './pages/OutputReviewPage';
import AppSettingsPage from './pages/AppSettingsPage';
import ContentManagerPage from './pages/ContentManagerPage';
import SourceMediaManagerPage from './pages/SourceMediaManagerPage';
import ImportInboxPage from './pages/ImportInboxPage';
import ProjectAssetsPage from './pages/ProjectAssetsPage';
import PromptPackPage from './pages/PromptPackPage';
import DouyinReupPage from './pages/DouyinReupPage';
import SubtitleReviewPage from './pages/SubtitleReviewPage';

const FALLBACK_VERSION = '0.2.0-rc1';

async function fetchVersion(): Promise<string> {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return FALLBACK_VERSION;
    const data = await res.json();
    return data.version ?? FALLBACK_VERSION;
  } catch {
    return FALLBACK_VERSION;
  }
}

export default function App() {
  const [version, setVersion] = useState<string>(FALLBACK_VERSION);

  useEffect(() => {
    fetchVersion().then(setVersion);
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
          <div>
            <div className="text-lg font-semibold text-ink">Auto Tool</div>
            <div className="text-xs text-muted">Bảng điều khiển render video local</div>
          </div>
          <nav className="flex items-center gap-2 text-sm">
            <NavLink
              className={({ isActive }) =>
                `rounded-md px-3 py-2 font-medium ${
                  isActive ? 'bg-blue-50 text-brand' : 'text-muted hover:bg-surface hover:text-ink'
                }`
              }
              to="/"
            >
              Tạo dự án
            </NavLink>
            <NavLink
              className={({ isActive }) =>
                `rounded-md px-3 py-2 font-medium ${
                  isActive ? 'bg-blue-50 text-brand' : 'text-muted hover:bg-surface hover:text-ink'
                }`
              }
              to="/import-inbox"
            >
              Import Inbox
            </NavLink>
            <NavLink
              className={({ isActive }) =>
                `rounded-md px-3 py-2 font-medium ${
                  isActive ? 'bg-blue-50 text-brand' : 'text-muted hover:bg-surface hover:text-ink'
                }`
              }
              to="/douyin-reup"
            >
              Douyin Reup
            </NavLink>
            <NavLink
              className={({ isActive }) =>
                `rounded-md px-3 py-2 font-medium ${
                  isActive ? 'bg-blue-50 text-brand' : 'text-muted hover:bg-surface hover:text-ink'
                }`
              }
              to="/subtitle-review"
            >
              Subtitle Review
            </NavLink>
            <NavLink
              className={({ isActive }) =>
                `rounded-md px-3 py-2 font-medium ${
                  isActive ? 'bg-blue-50 text-brand' : 'text-muted hover:bg-surface hover:text-ink'
                }`
              }
              to="/app-settings"
            >
              Cài đặt chung
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<CreateProjectPage />} />
          <Route path="/settings/:projectId" element={<RenderSettingsPage />} />
          <Route path="/queue/:projectId/:jobId" element={<RenderQueuePage />} />
          <Route path="/results/:projectId/:jobId" element={<ResultPage />} />
          <Route path="/results/:jobId" element={<ResultPage />} />
          <Route path="/projects/:projectId/review" element={<OutputReviewPage />} />
          <Route path="/projects/:projectId/source-media" element={<SourceMediaManagerPage />} />
          <Route path="/projects/:projectId/assets" element={<ProjectAssetsPage />} />
          <Route path="/projects/:projectId/prompt-pack" element={<PromptPackPage />} />
          <Route path="/projects/:projectId/content" element={<ContentManagerPage />} />
          <Route path="/import-inbox" element={<ImportInboxPage />} />
          <Route path="/douyin-reup" element={<DouyinReupPage />} />
          <Route path="/subtitle-review" element={<SubtitleReviewPage />} />
          <Route path="/subtitle-review/:documentId" element={<SubtitleReviewPage />} />
          <Route path="/app-settings" element={<AppSettingsPage />} />
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </main>

      <footer className="border-t border-line bg-white py-3">
        <div className="mx-auto max-w-7xl px-6 text-center text-xs text-muted">
          Auto Tool{' '}
          <span id="app-version" className="font-mono">
            v{version}
          </span>
        </div>
      </footer>
    </div>
  );
}
