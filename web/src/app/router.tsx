import { Navigate, Route, Routes } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { ComingSoonPage } from "../pages/ComingSoonPage";
import { Layout } from "./Layout";

export function AppRouter() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/knowledge-bases" replace />} />
        <Route
          path="/knowledge-bases"
          element={<EmptyState title="知识库管理" description="知识库列表与创建功能将在下一任务中提供。" />}
        />
        <Route
          path="/knowledge-bases/new"
          element={<EmptyState title="新建知识库" description="知识库创建表单将在下一任务中提供。" />}
        />
        <Route
          path="/knowledge-bases/:id"
          element={<EmptyState title="知识库详情" description="知识库编辑与归档功能将在下一任务中提供。" />}
        />
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
