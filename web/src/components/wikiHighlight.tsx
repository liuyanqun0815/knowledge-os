import React, { type ReactNode } from "react";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function highlightPlainText(text: string, highlightQuery?: string): ReactNode[] {
  const query = highlightQuery?.trim();
  if (!query) {
    return [text];
  }
  const pattern = new RegExp(`(${escapeRegExp(query)})`, "gi");
  const parts = text.split(pattern);
  const needle = query.toLowerCase();
  return parts.map((part, index) => {
    if (part.toLowerCase() === needle) {
      return <mark key={`mark-${index}`}>{part}</mark>;
    }
    return <React.Fragment key={`text-${index}`}>{part}</React.Fragment>;
  });
}
