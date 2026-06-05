// Renders a card body as GitHub-flavored Markdown in the calm reading column (Inter 15/1.65),
// selectable - mirrors Flet's ft.Markdown. The reading column never glows.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownBody({ source }: { source: string }) {
  return (
    <div className="prose-hud" style={{ userSelect: "text" }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ ...props }) => <a target="_blank" rel="noreferrer noopener" {...props} />,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
