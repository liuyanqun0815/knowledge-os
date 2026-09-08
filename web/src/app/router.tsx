import { Navigate, Route, Routes } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { ComingSoonPage } from "../pages/ComingSoonPage";
import { KnowledgeBaseDetailPage } from "../pages/KnowledgeBaseDetailPage";
import { KnowledgeBaseListPage } from "../pages/KnowledgeBaseListPage";
import { KnowledgeBaseNewPage } from "../pages/KnowledgeBaseNewPage";
import { Layout } from "./Layout";

export function AppRouter() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/knowledge-bases" replace />} />
        <Route path="/knowledge-bases" element={<KnowledgeBaseListPage />} />
        <Route path="/knowledge-bases/new" element={<KnowledgeBaseNewPage />} />
        <Route path="/knowledge-bases/:id" element={<KnowledgeBaseDetailPage />} />
        <Route
          path="/sources"
          element={<EmptyState title="文档管理" description="文档上传与编译状态功能即将提供。" />}
        />
        <Route path="/ask" element={<EmptyState title="知识问答" description="问答、证据与 Agent 轨迹功能即将提供。" />} />
        <Route path="/claims" element={<ComingSoonPage title="Claim 浏览" />} />
        <Route path="/quarantine" element={<ComingSoonPage title="隔离审批" />} />
        <Route path="*" element={<EmptyState title="页面不存在" description="请通过顶部导航访问管理功能。" />} />
      </Route>
    </Routes>
  );
}
