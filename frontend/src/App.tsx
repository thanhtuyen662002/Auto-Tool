import { Navigate, Route, Routes } from 'react-router-dom';
import StudioLayout from './layouts/StudioLayout';
import ContentManagerPage from './pages/ContentManagerPage';
import CreateProjectPage from './pages/CreateProjectPage';
import DashboardPage from './pages/DashboardPage';
import DouyinDownloadPage from './pages/DouyinDownloadPage';
import DouyinReupPage from './pages/DouyinReupPage';
import HelpPage from './pages/HelpPage';
import ImportInboxPage from './pages/ImportInboxPage';
import OnboardingPage from './pages/OnboardingPage';
import OutputReviewPage from './pages/OutputReviewPage';
import ProjectAssetsPage from './pages/ProjectAssetsPage';
import PromptPackPage from './pages/PromptPackPage';
import RenderQueuePage from './pages/RenderQueuePage';
import RecoveryCenterPage from './pages/RecoveryCenterPage';
import RenderSettingsPage from './pages/RenderSettingsPage';
import ResultPage from './pages/ResultPage';
import ResultsPage from './pages/ResultsPage';
import SettingsPage from './pages/SettingsPage';
import SilentModePage from './pages/SilentModePage';
import SourceMediaManagerPage from './pages/SourceMediaManagerPage';
import SubtitleReviewPage from './pages/SubtitleReviewPage';

export default function App() {
  return (
    <Routes>
      <Route element={<StudioLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="projects/new" element={<CreateProjectPage />} />
        <Route path="settings/:projectId" element={<RenderSettingsPage />} />
        <Route path="projects/:projectId" element={<RenderSettingsPage />} />
        <Route path="queue/:projectId/:jobId" element={<RenderQueuePage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route path="recovery" element={<RecoveryCenterPage />} />
        <Route path="results/:projectId/:jobId" element={<ResultPage />} />
        <Route path="results/:jobId" element={<ResultPage />} />
        <Route path="projects/:projectId/review" element={<OutputReviewPage />} />
        <Route path="projects/:projectId/source-media" element={<SourceMediaManagerPage />} />
        <Route path="projects/:projectId/assets" element={<ProjectAssetsPage />} />
        <Route path="projects/:projectId/prompt-pack" element={<PromptPackPage />} />
        <Route path="projects/:projectId/content" element={<ContentManagerPage />} />
        <Route path="import-inbox" element={<ImportInboxPage />} />
        <Route path="douyin-download" element={<DouyinDownloadPage />} />
        <Route path="douyin-reup" element={<DouyinReupPage initialWorkflow="douyin" />} />
        <Route path="silent-mode" element={<SilentModePage />} />
        <Route path="subtitle-review" element={<SubtitleReviewPage />} />
        <Route path="subtitle-review/:documentId" element={<SubtitleReviewPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="onboarding" element={<OnboardingPage />} />
        <Route path="app-settings" element={<Navigate replace to="/settings" />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}
