// Ein eigener Vite-Zwischenspeicher je Testdatei, der beim Ende des Prozesses wieder verschwindet.
// Ohne das Aufräumen blieben je Lauf über 20 Ordner liegen; nach einigen Hundert Läufen war die Platte voll.
import {rmSync} from 'node:fs';

export function testCache(name) {
  const pfad = `/private/tmp/kingfisher-ui-test-cache-${process.pid}-${name}`;
  process.once('exit', () => rmSync(pfad, {recursive: true, force: true}));
  return pfad;
}
