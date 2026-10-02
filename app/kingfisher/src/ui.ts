export const ASSET = {
  media: "/03_Media/Approved/",
  icon: "/02_Icons/Approved/",
  brand: "/01_Brand/Approved/kingfisher-logo-dark-approved-v1.png",
};

export const icon = (name: string, variant: "Outline" | "Filled" = "Filled") =>
  `${ASSET.icon}${variant}/${name}.svg`;

export const NAV = [
  ["Heute", "house"],
  ["Gespräche", "message-circle"],
  ["Aufgaben", "folder"],
  ["Gedächtnis", "brain"],
  ["Nachrichten", "mail"],
  ["Kalender", "calendar-days"],
] as const;

export type NavigationLabel = typeof NAV[number][0];

export function navigate(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
