import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import StudioLayout from './layouts/StudioLayout';

const ContentManagerPage = lazy(() => import('./pages/ContentManagerPage'));
const CreateProjectPage = lazy(() => import('./pages/CreateProjectPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const DouyinDownloadPage = lazy(() => import('./pages/DouyinDownloadPage'));
const DouyinReupPage = lazy(() => import('./pages/DouyinReupPage'));
const HelpPage = lazy(() => import('./pages/HelpPage'));
const ImportInboxPage = lazy(() => import('./pages/ImportInboxPage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));
const OutputReviewPage = lazy(() => import('./pages/OutputReviewPage'));
const ProjectAssetsPage = lazy(() => import('./pages/ProjectAssetsPage'));
const PromptPackPage = lazy(() => import('./pages/PromptPackPage'));
const RenderQueuePage = lazy(() => import('./pages/RenderQueuePage'));
const RecoveryCenterPage = lazy(() => import('./pages/RecoveryCenterPage'));
const RenderSettingsPage = lazy(() => import('./pages/RenderSettingsPage'));
const ResultPage = lazy(() => import('./pages/ResultPage'));
const ResultsPage = lazy(() => import('./pages/ResultsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const SilentModePage = lazy(() => import('./pages/SilentModePage'));
const SourceMediaManagerPage = lazy(() => import('./pages/SourceMediaManagerPage'));
const SubtitleReviewPage = lazy(() => import('./pages/SubtitleReviewPage'));
const FleetPage = lazy(() => import('./pages/FleetPage'));

function screen(page: ReactNode) {
  return (
    <Suspense fallback={<div className="px-6 py-8 text-sm text-slate-400">Đang tải màn hình...</div>}>
      {page}
    </Suspense>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<StudioLayout />}>
        <Route index element={screen(<DashboardPage />)} />
        <Route path="dashboard" element={screen(<DashboardPage />)} />
        <Route path="projects/new" element={screen(<CreateProjectPage />)} />
        <Route path="settings/:projectId" element={screen(<RenderSettingsPage />)} />
        <Route path="projects/:projectId" element={screen(<RenderSettingsPage />)} />
        <Route path="queue/:projectId/:jobId" element={screen(<RenderQueuePage />)} />
        <Route path="results" element={screen(<ResultsPage />)} />
        <Route path="recovery" element={screen(<RecoveryCenterPage />)} />
        <Route path="results/:projectId/:jobId" element={screen(<ResultPage />)} />
        <Route path="results/:jobId" element={screen(<ResultPage />)} />
        <Route path="projects/:projectId/review" element={screen(<OutputReviewPage />)} />
        <Route path="projects/:projectId/source-media" element={screen(<SourceMediaManagerPage />)} />
        <Route path="projects/:projectId/assets" element={screen(<ProjectAssetsPage />)} />
        <Route path="projects/:projectId/prompt-pack" element={screen(<PromptPackPage />)} />
        <Route path="projects/:projectId/content" element={screen(<ContentManagerPage />)} />
        <Route path="import-inbox" element={screen(<ImportInboxPage />)} />
        <Route path="douyin-download" element={screen(<DouyinDownloadPage />)} />
        <Route path="douyin-reup" element={screen(<DouyinReupPage initialWorkflow="douyin" />)} />
        <Route path="silent-mode" element={screen(<SilentModePage />)} />
        <Route path="subtitle-review" element={screen(<SubtitleReviewPage />)} />
        <Route path="subtitle-review/:documentId" element={screen(<SubtitleReviewPage />)} />
        <Route path="fleet" element={screen(<FleetPage />)} />
        <Route path="settings" element={screen(<SettingsPage />)} />
        <Route path="help" element={screen(<HelpPage />)} />
        <Route path="onboarding" element={screen(<OnboardingPage />)} />
        <Route path="app-settings" element={<Navigate replace to="/settings" />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}
