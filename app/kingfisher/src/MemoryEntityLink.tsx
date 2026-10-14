import type {AnchorHTMLAttributes,MouseEvent} from 'react';
import {memoryProfileHref} from './MemoryViewState';
import {navigate} from './ui';
export function followMemoryEntity(event:MouseEvent<HTMLAnchorElement>,href:string) {
  if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey||event.currentTarget.target==='_blank')return;
  event.preventDefault();navigate(href);
}
export function MemoryEntityLink({href,kind='person',...props}:Omit<AnchorHTMLAttributes<HTMLAnchorElement>,'href'|'onClick'> & {href:string;kind?:'person'|'project'}) {
  const path=memoryProfileHref(href,kind);
  return <a {...props} href={path} onClick={event=>followMemoryEntity(event,path)}/>;
}
