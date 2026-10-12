import React from 'react';
import {createRoot} from 'react-dom/client';
import {DocumentImport} from '/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/DocumentImport.tsx';
import '/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/theme.css';
import '/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/styles.css';
import "/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/CalmUI.css";
import "/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/Seitenbreite.css";
import {TodayOverview} from "/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/TodayOverview.tsx";
import {api} from "/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/api.ts";
import {TodaySourceStatus} from "/@fs/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/app/kingfisher/src/TodaySourceStatus.tsx";
function Flow(){const [briefing,setBriefing]=React.useState<any>(null);React.useEffect(()=>{api.morning(false).then(setBriefing)},[]);return briefing?<><TodaySourceStatus briefing={briefing} refreshing={false} refreshError={false} onRefresh={()=>{}}/><TodayOverview briefing={briefing} onChange={()=>{}} taskNotice="" onTaskDone={()=>{}} correctionSaved={false} onOpenMail={()=>{}}/></>:<p>Lädt</p>;}
createRoot(document.getElementById("root")!).render(<Flow/>);
