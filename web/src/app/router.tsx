import { Navigate, Route, Routes } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { AskPage } from "../pages/AskPage";
import { KnowledgeBaseDetailPage } from "../pages/KnowledgeBaseDetailPage";
import { KnowledgeBaseListPage } from "../pages/KnowledgeBaseListPage";
import { KnowledgeBaseNewPage } from "../pages/KnowledgeBaseNewPage";
import { ClaimsPage } from "../pages/ClaimsPage";
import { QuarantinePage } from "../pages/QuarantinePage";
import { SourcesPage } from "../pages/SourcesPage";
import { Layout } from "./Layout";

export function AppRouter() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/knowledge-bases" replace />} />
        <Route path="/knowledge-bases" element={<KnowledgeBaseListPage />} />
        <Route path="/knowledge-bases/new" element={<KnowledgeBaseNewPage />} />
        <Route path="/knowledge-bases/:id" element={<KnowledgeBaseDetailPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/claims" element={<ClaimsPage />} />
        <Route path="/quarantine" element={<QuarantinePage />} />
        <Route path="*" element={<EmptyState title="页面不存在" description="请通过顶部导航访问管理功能。" />} />
      </Route>
    </Routes>
  );
}
