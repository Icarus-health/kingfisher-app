type Dated = {due?: string | null};
type BoardTask = {status?: string; wartet_auf?: string | null};

export function groupTasks<T extends Dated>(tasks: T[], now = new Date()) {
  const groups: Array<{label: string; items: T[]}> = [
    {label:'Überfällig',items:[]}, {label:'Heute',items:[]},
    {label:'Demnächst',items:[]}, {label:'Ohne Termin',items:[]},
  ];
  const start = new Date(now.getFullYear(),now.getMonth(),now.getDate()).getTime();
  const end = new Date(now.getFullYear(),now.getMonth(),now.getDate()+1).getTime();
  for (const task of tasks) {
    const time = task.due ? new Date(task.due).getTime() : NaN;
    groups[Number.isNaN(time) ? 3 : time < start ? 0 : time < end ? 1 : 2].items.push(task);
  }
  return groups;
}

/** Was die Liste zeigt: nur Gruppen mit Aufgaben. Eine leere Gruppe ist Lärm, keine Auskunft. */
export function visibleTaskGroups<T extends Dated>(tasks: T[], now = new Date()) {
  return groupTasks(tasks, now).filter(group => group.items.length > 0);
}

export function projectColumns<T extends BoardTask>(tasks: T[]) {
  return [
    {label:'Offen',items:tasks.filter(t=>t.status==='open' && !t.wartet_auf)},
    {label:'Wartend',items:tasks.filter(t=>t.status==='open' && Boolean(t.wartet_auf))},
    {label:'Erledigt',items:tasks.filter(t=>t.status==='done')},
  ];
}
