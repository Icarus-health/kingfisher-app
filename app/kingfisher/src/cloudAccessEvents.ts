export const CLOUD_ACCESS_CHANGED = "kingfisher:cloud-access-changed";

export function announceCloudAccessChange(target: EventTarget = window): void {
  target.dispatchEvent(new Event(CLOUD_ACCESS_CHANGED));
}

export function listenForCloudAccessChange(listener: () => void, target: EventTarget = window): () => void {
  const handler = () => listener();
  target.addEventListener(CLOUD_ACCESS_CHANGED, handler);
  return () => target.removeEventListener(CLOUD_ACCESS_CHANGED, handler);
}
