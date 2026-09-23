import { fetchSource } from "../api/sources";
import type { SourceItem } from "../api/types";

export const UPLOAD_POLL_INTERVAL_MS = 2000;
export const UPLOAD_POLL_MAX_MS = 5 * 60 * 1000;

const TERMINAL_STATUSES: ReadonlySet<SourceItem["compile_status"]> = new Set([
  "succeeded",
  "succeeded_partial",
  "failed",
  "ready",
]);

export function isTerminalCompileStatus(status: SourceItem["compile_status"]): boolean {
  return TERMINAL_STATUSES.has(status);
}

export function mergeSourceItems(prev: SourceItem[], updates: SourceItem[]): SourceItem[] {
  const validUpdates = updates.filter((item): item is SourceItem => Boolean(item?.id));
  if (validUpdates.length === 0) {
    return prev;
  }
  const byId = new Map(validUpdates.map((item) => [item.id, item]));
  const seen = new Set<string>();
  const merged = prev.map((item) => {
    const next = byId.get(item.id);
    if (next) {
      seen.add(item.id);
      return next;
    }
    return item;
  });
  for (const item of validUpdates) {
    if (!seen.has(item.id)) {
      merged.push(item);
    }
  }
  return merged;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** 仅轮询本次上传的 source_id，2s 一次，终态或 5 分钟超时后结束。 */
export const COMPILE_STATUS_LABELS: Record<string, string> = {
  pending: "等待处理",
  chunking: "切分中",
  extracting_claims: "抽取 Claim",
  enriching_chunks: "补全 Chunk",
  compiling_wiki: "编译 Wiki",
  running: "处理中",
  enriching: "处理中",
  ready: "已完成",
  succeeded: "已完成",
  succeeded_partial: "部分完成",
  failed: "失败",
};

export async function pollUploadedSources(
  kbId: string,
  sourceIds: string[],
  options: {
    isActive: () => boolean;
    onUpdate: (items: SourceItem[]) => void;
  },
): Promise<void> {
  const uniqueIds = [...new Set(sourceIds.filter(Boolean))];
  if (uniqueIds.length === 0) {
    return;
  }

  const deadline = Date.now() + UPLOAD_POLL_MAX_MS;
  while (Date.now() < deadline && options.isActive()) {
    const fetched = await Promise.all(
      uniqueIds.map(async (sourceId) => {
        try {
          return await fetchSource(kbId, sourceId);
        } catch {
          return null;
        }
      }),
    );
    const items = fetched.filter((item): item is SourceItem => item !== null);
    if (items.length > 0 && options.isActive()) {
      options.onUpdate(items);
    }
    const tracked = items.filter((item) => uniqueIds.includes(item.id));
    if (
      tracked.length === uniqueIds.length &&
      tracked.every((item) => isTerminalCompileStatus(item.compile_status))
    ) {
      return;
    }
    await sleep(UPLOAD_POLL_INTERVAL_MS);
  }
}
