## Packages
react-markdown | Rendering AI responses with markdown support
remark-gfm | GitHub Flavored Markdown support for react-markdown
clsx | Utility for constructing className strings conditionally
tailwind-merge | Utility for merging Tailwind CSS classes
date-fns | Date formatting for thread history

## Notes
- The chat endpoint /api/chat returns a stream. The frontend implements a custom stream reader in use-chat-stream.ts.
- Images are primarily icon-based using Lucide React.
- Sidebar logo uses @assets/logo.svg
