export function cloudAccessSaveBody(apiKey: string, model: string): {api_key?: string; model: string} {
  const key = apiKey.trim();
  return key ? {api_key: key, model: model.trim()} : {model: model.trim()};
}
