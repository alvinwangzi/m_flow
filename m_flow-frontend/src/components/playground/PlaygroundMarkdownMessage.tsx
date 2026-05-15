"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import rehypeRaw from "rehype-raw";

interface PlaygroundMarkdownMessageProps {
  content: string;
}

function normalizeMarkdownContent(content: string): string {
  return content
    .replace(/<br\s*\/?>/gi, "  \n")
    // Normalize common LLM output where bold markers appear in contexts markdown parsers may not re-tokenize well
    .replace(/\*\*([^*\n]+)\*\*/g, (_match, inner) => `<strong>${inner.trim()}</strong>`)
    .replace(/\r\n/g, "\n");
}

export function PlaygroundMarkdownMessage({ content }: PlaygroundMarkdownMessageProps) {
  const normalizedContent = normalizeMarkdownContent(content);
  const components: Components = {
    p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="mb-3 ml-5 list-disc space-y-1 last:mb-0">{children}</ul>,
    ol: ({ children }) => <ol className="mb-3 ml-5 list-decimal space-y-1 last:mb-0">{children}</ol>,
    li: ({ children }) => <li className="marker:text-[#808080]">{children}</li>,
    a: ({ href, children }) => (
      <a
        href={href || "#"}
        target="_blank"
        rel="noreferrer"
        className="text-[#8ab4ff] underline underline-offset-2 hover:text-[#a8c7ff]"
      >
        {children}
      </a>
    ),
    code: ({ children, className, ...props }) => {
      const isInline = !className?.includes("language-");
      return isInline ? (
        <code
          {...props}
          className="rounded bg-[#111318] px-1.5 py-0.5 font-mono text-[0.9em] text-[#d6e2ff]"
        >
          {children}
        </code>
      ) : (
        <code {...props} className="font-mono text-[13px] text-[#e8e8e8]">
          {children}
        </code>
      );
    },
    pre: ({ children }) => (
      <pre className="mb-3 overflow-x-auto rounded-lg border border-[#2a2a2a] bg-[#0f1115] p-3 last:mb-0">
        {children}
      </pre>
    ),
    blockquote: ({ children }) => (
      <blockquote className="mb-3 border-l-2 border-[#3a3f4b] pl-3 text-[#b8c0d4] italic last:mb-0">
        {children}
      </blockquote>
    ),
    table: ({ children }) => (
      <div className="mb-3 overflow-x-auto last:mb-0">
        <table className="min-w-full border-collapse text-left text-[13px]">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="border-b border-[#2a2a2a]">{children}</thead>,
    th: ({ children }) => <th className="px-3 py-2 font-medium text-[#f0f0f0]">{children}</th>,
    td: ({ children }) => <td className="border-b border-[#1f1f1f] px-3 py-2 text-[#d5d5d5]">{children}</td>,
  };

  return (
    <div className="playground-markdown text-sm leading-relaxed text-inherit">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[rehypeRaw]}
        components={components}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
}
