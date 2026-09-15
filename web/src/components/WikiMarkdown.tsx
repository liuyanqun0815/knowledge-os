import React, { Children, isValidElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type WikiMarkdownProps = {
  markdown: string;
  pageIds: Set<string>;
  highlightQuery?: string;
  onNavigate: (pageId: string) => void;
};

const WIKILINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightPlainText(text: string, highlightQuery?: string): ReactNode[] {
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

function renderTextWithWikilinks(
  text: string,
  pageIds: Set<string>,
  onNavigate: (pageId: string) => void,
  highlightQuery?: string,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const re = new RegExp(WIKILINK_RE.source, "g");
  let key = 0;

  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(...highlightPlainText(text.slice(lastIndex, match.index), highlightQuery));
    }
    const target = match[1].trim();
    const label = (match[2] ?? match[1]).trim();
    if (pageIds.has(target)) {
      nodes.push(
        <a
          key={`wikilink-${key++}`}
          href={`#${encodeURIComponent(target)}`}
          className="wiki-wikilink"
          role="link"
          onClick={(event) => {
            event.preventDefault();
            onNavigate(target);
          }}
        >
          {highlightPlainText(label, highlightQuery)}
        </a>,
      );
    } else {
      nodes.push(...highlightPlainText(label, highlightQuery));
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(...highlightPlainText(text.slice(lastIndex), highlightQuery));
  }

  return nodes;
}

function transformChildren(
  children: ReactNode,
  pageIds: Set<string>,
  onNavigate: (pageId: string) => void,
  highlightQuery?: string,
): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child === "string") {
      return renderTextWithWikilinks(child, pageIds, onNavigate, highlightQuery);
    }
    if (isValidElement<{ children?: ReactNode }>(child) && child.props.children != null) {
      return React.cloneElement(child, {
        ...child.props,
        children: transformChildren(child.props.children, pageIds, onNavigate, highlightQuery),
      });
    }
    return child;
  });
}

type MarkdownElementProps = {
  children?: ReactNode;
} & Record<string, unknown>;

function makeElement(
  Tag: keyof JSX.IntrinsicElements,
  pageIds: Set<string>,
  onNavigate: (pageId: string) => void,
  highlightQuery?: string,
) {
  return function WikiElement({ children, ...props }: MarkdownElementProps) {
    const Component = Tag as React.ElementType;
    return (
      <Component {...props}>
        {transformChildren(children, pageIds, onNavigate, highlightQuery)}
      </Component>
    );
  };
}

export function WikiMarkdown({ markdown, pageIds, highlightQuery, onNavigate }: WikiMarkdownProps) {
  const wrap = (Tag: keyof JSX.IntrinsicElements) =>
    makeElement(Tag, pageIds, onNavigate, highlightQuery);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: wrap("p"),
        li: wrap("li"),
        td: wrap("td"),
        th: wrap("th"),
        h1: wrap("h1"),
        h2: wrap("h2"),
        h3: wrap("h3"),
        h4: wrap("h4"),
        h5: wrap("h5"),
        h6: wrap("h6"),
        strong: wrap("strong"),
        em: wrap("em"),
        blockquote: wrap("blockquote"),
        a: wrap("a"),
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}
