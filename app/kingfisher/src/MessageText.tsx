import {Fragment, type ReactNode} from 'react';

// Deliberately small Markdown subset. React escapes every text fragment; no HTML or URL evaluation.
function inline(text: string): ReactNode[] {
  return text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g).map((part, index) =>
    part.startsWith('`') && part.endsWith('`') ? <code key={index}>{part.slice(1, -1)}</code>
      : part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong>
      : <Fragment key={index}>{part}</Fragment>);
}
export function MessageText({content}: {content: string}) {
  const lines = content.replace(/\r\n?/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    if (!lines[index].trim()) { index++; continue; }
    if (/^\s*```/.test(lines[index])) {
      const code: string[] = []; index++;
      while (index < lines.length && !/^\s*```/.test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index++;
      blocks.push(<pre key={blocks.length}><code>{code.join('\n')}</code></pre>); continue;
    }
    const ordered = /^\s*\d+[.)]\s+/.test(lines[index]);
    const list = ordered ? /^\s*\d+[.)]\s+(.*)$/ : /^\s*[-*]\s+(.*)$/;
    if (list.test(lines[index])) {
      const items: ReactNode[] = [];
      while (index < lines.length) {
        const match = lines[index].match(list); if (!match) break;
        items.push(<li key={items.length}>{inline(match[1])}</li>); index++;
      }
      blocks.push(ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>); continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim() && !/^\s*(```|[-*]\s+|\d+[.)]\s+)/.test(lines[index])) paragraph.push(lines[index++]);
    blocks.push(<p key={blocks.length}>{inline(paragraph.join('\n'))}</p>);
  }
  return <div className="message-text">{blocks}</div>;
}
