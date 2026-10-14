import {useEffect,useRef,useState} from 'react';
export type PlaceMapPoint={id:string;name:string;lat:number;lng:number};
export type PlacesMapFactory=(container:HTMLElement,callbacks:{select:(id:string)=>void;pin:(lat:number,lng:number)=>void})=>{update:(points:PlaceMapPoint[],selected:string|null,pinning:boolean)=>void;destroy:()=>void};
let mapFactory:PlacesMapFactory|null=null;
// Root installs the bundled Leaflet factory. Disabled views never call it or load tiles.
export function installPlacesMapFactory(factory:PlacesMapFactory) {mapFactory=factory;}
export function PlacesMap({enabled,points,selected,pinning,onSelect,onPin}: {enabled:boolean;points:PlaceMapPoint[];selected:string|null;pinning:boolean;onSelect:(id:string)=>void;onPin:(lat:number,lng:number)=>void}) {
  const container=useRef<HTMLDivElement>(null);
  const callbacks=useRef({onSelect,onPin});callbacks.current={onSelect,onPin};
  const instance=useRef<ReturnType<PlacesMapFactory>|null>(null);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    setFailed(false);
    if(!enabled||!container.current||!mapFactory)return;
    try {instance.current=mapFactory(container.current,{select:id=>callbacks.current.onSelect(id),pin:(lat,lng)=>callbacks.current.onPin(lat,lng)});}
    catch{setFailed(true);}
    return()=>{instance.current?.destroy();instance.current=null;};
  },[enabled]);
  useEffect(()=>{instance.current?.update(points,selected,pinning);},[enabled,points,selected,pinning]);
  if(!enabled)return <p>Onlinekarte ausgeschaltet. Bestätigte Koordinaten lassen sich in der Liste pflegen. <a href="/settings#workspace-online">Karteneinstellung öffnen</a></p>;
  if(!mapFactory)return <p role="status">Die Kartenansicht ist noch nicht verfügbar. Die Ortsliste und Koordinaten bleiben erreichbar.</p>;
  return <><div className="memory-place-map" ref={container} role="region" aria-label="Karte der bestätigten Orte"/>{failed&&<p role="alert">Karte nicht erreichbar. Koordinaten können weiterhin in der Liste geändert werden.</p>}<small>Kartendaten © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap-Mitwirkende</a></small></>;
}
