import './ProcedureChoice.css';

export type ProcedureOption = {id:string; label:string; version?:number; name?:string};
export type ProcedureChoicePrompt = {token:string; options:ProcedureOption[]};
export type ProcedureChoiceValue = {token:string; id:string};

export function ProcedureChoice({prompt,busy,onChoose,onCancel}: {
  prompt:ProcedureChoicePrompt; busy?:boolean;
  onChoose:(option:ProcedureOption)=>void|Promise<void>; onCancel?:()=>void;
}) {
  return <div className="procedure-choice" role="group" aria-label="Ablauf auswählen">
    <div className="procedure-choice-options">{prompt.options.map(option=><button
      className="g-knopf-schlicht" type="button" key={option.id} disabled={busy}
      onClick={()=>void onChoose(option)}>{option.label}</button>)}</div>
    <details><summary>Warum diese Auswahl?</summary>
      <p>Mehrere bestätigte Abläufe passen zu deinem Auftrag. Die Wahl gilt nur für diese Antwort und ändert keine dauerhaften Einstellungen.</p>
      <ul>{prompt.options.filter(option=>option.version!==undefined).map(option=><li key={option.id}>
        {option.label} · Fassung {option.version}{option.name?` · ${option.name}`:''}
      </li>)}</ul>
    </details>
    {onCancel?<button className="g-knopf-schlicht" type="button" disabled={busy} onClick={onCancel}>Abbrechen</button>:null}
  </div>;
}
