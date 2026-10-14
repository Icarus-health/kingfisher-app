import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {installPlacesMapFactory} from './PlacesMap';

installPlacesMapFactory((container,callbacks)=>{
  // This factory is invoked only after the explicit online.maps switch.
  const map=L.map(container,{scrollWheelZoom:false}).setView([50,10],5);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
  }).addTo(map);
  const layers=L.layerGroup().addTo(map);
  let pinning=false;
  let initial=true;
  let preview:L.CircleMarker|null=null;
  map.on('click',(event:L.LeafletMouseEvent)=>{
    if(!pinning) return;
    preview?.remove();preview=L.circleMarker(event.latlng,{color:'#317c91',radius:9}).addTo(map);
    callbacks.pin(event.latlng.lat,event.latlng.lng);
  });
  return {
    update(points,selected,canPin){
      pinning=canPin;layers.clearLayers();
      if(!pinning){preview?.remove();preview=null;}
      points.forEach(point=>{
        const marker=L.circleMarker([point.lat,point.lng],{radius:point.id===selected?10:7,color:point.id===selected?'#1e6577':'#427c8b',fillOpacity:.8}).addTo(layers);
        const text=document.createElement('span');text.textContent=point.name;
        marker.bindTooltip(text);marker.on('click',event=>{L.DomEvent.stopPropagation(event);callbacks.select(point.id);});
        const path=marker.getElement();
        path?.setAttribute('tabindex','0');path?.setAttribute('role','button');path?.setAttribute('aria-label',point.name);
        path?.addEventListener('keydown',event=>{if(event instanceof KeyboardEvent && (event.key==='Enter'||event.key===' ')){event.preventDefault();callbacks.select(point.id);}});
      });
      if(initial&&points.length){map.fitBounds(L.latLngBounds(points.map(p=>L.latLng(p.lat,p.lng))),{maxZoom:13,padding:[28,28]});initial=false;}
      map.invalidateSize();
    },
    destroy(){map.remove();},
  };
});
