export function displayLabel(label: string) {
  // Display only: navigation and identity continue to use the original node.
  const match = label.match(/^(.*?)\s*<([^<>]+)>$/);
  const name = (match?.[1]?.trim() || match?.[2] || label).trim().replace(/^"(.*)"$/, "$1");
  return { name, detail: match?.[2] !== name ? match?.[2] || "" : "" };
}

