import React from 'react';
import {createRoot} from 'react-dom/client';
import {MailIntake} from '/@fs//Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/MailIntake.tsx';
import '/@fs//Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/theme.css';
import '/@fs//Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/styles.css';
const accounts=[{id:'a',label:'Künstlich Aktiv'},{id:'b',label:'Künstlich Pausiert'},{id:'c',label:'Künstlich Neu'}];
createRoot(document.getElementById('root')!).render(<main style={{padding:'24px',maxWidth:850,margin:'auto'}}><h1>Speicherreserve</h1><p>Künstliche Daten; keine echte Mailverbindung.</p><MailIntake active={true} accounts={accounts as any} onChanged={()=>{}} /></main>);
