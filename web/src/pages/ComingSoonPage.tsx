import { EmptyState } from "../components/EmptyState";

export function ComingSoonPage({ title }: { title: string }) {
  return <EmptyState title={title} description="该功能随 2.2+ API 解锁。" />;
}
