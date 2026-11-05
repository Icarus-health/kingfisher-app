import type {TaskStatusLink} from './api';
import {taskHref} from './taskWorkflow';
import {navigate} from './ui';

export function TaskStatusAnswer({content, link, messageId}: {content: string; link?: TaskStatusLink; messageId: string}) {
  const href = link && `${taskHref(link)}&history=${encodeURIComponent(link.sequence)}&from=conversation`;
  return <>
    <div className="message-text"><p>{content}</p></div>
    {href && <div className="beleg-links"><a className="text-action" href={href} onClick={event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const back = new URL(window.location.href);
      back.hash = `message-${encodeURIComponent(messageId)}`;
      window.history.replaceState(window.history.state, '', back);
      navigate(href);
    }}>Aufgabe und Verlauf ansehen</a></div>}
  </>;
}
