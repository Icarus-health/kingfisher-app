"""Datierte Anbieterangaben; keine rechtliche Freigabe oder DSGVO-Zusicherung."""
FACTS = {
    'anthropic': {
        'checked_at': '2026-10-19',
        'region': 'Direkte Claude API: globaler Zugang, nicht ausschließlich auf die EU begrenzt.',
        'training': 'API-Inhalte werden standardmäßig nicht für Training verwendet; Ausnahmen gelten etwa bei ausdrücklicher Freigabe und Sicherheitsprüfungen.',
        'retention': 'Standardmäßig Löschung innerhalb von 30 Tagen; vertragliche und Sicherheitsausnahmen sind möglich.',
        'billing': 'Vorausbezahltes API-Guthaben. Anfrage- und Tokenlimits sind keine garantierte Euro-Obergrenze. Keine Batch-Verarbeitung in Kingfisher.',
        'sources': [
            {'label': 'API-Guthaben', 'url': 'https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage'},
            {'label': 'Training', 'url': 'https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training'},
            {'label': 'Aufbewahrung', 'url': 'https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data'},
        ],
    },
    'openai': {
        'checked_at': '2026-10-19',
        'region': 'Dieser Standardzugang ist global. EU-Verarbeitung setzt passende Berechtigung, Projekteinstellung und Endpunkte voraus.',
        'training': 'API-Inhalte werden standardmäßig nicht für Training verwendet; freiwillige Datenfreigaben sind gesondert zu prüfen.',
        'retention': 'Aufbewahrung und Ausnahmen hängen von Endpunkt und Vertrag ab. Dieser gespeicherte Zugang weist keine Zero-Data-Retention-Freigabe nach.',
        'billing': 'API-Nutzung wird separat abgerechnet. Dieser Zugang ist noch kein zusätzlicher Anbieter für die Cloud-Einordnung.',
        'sources': [{'label': 'API-Datenkontrollen', 'url': 'https://developers.openai.com/api/docs/guides/your-data'}],
    },
    'mistral': {
        'checked_at': '2026-10-19',
        'region': 'Dieser regionale Endpunkt verarbeitet Inferenz in EU/EFTA. Das bedeutet nicht, dass sämtliche Metadaten dort verbleiben.',
        'training': 'Trainingsverwendung und Aufbewahrung sind anhand des eigenen Vertrags und der Kontoeinstellungen zu prüfen.',
        'retention': 'Regionale Inferenz allein garantiert weder vollständige Datenresidenz noch DSGVO-Konformität.',
        'billing': 'Separat abgerechneter API-Zugang; keine automatische Freigabe durch Speichern.',
        'sources': [{'label': 'Regionale Inferenz', 'url': 'https://docs.mistral.ai/inference/regional-inference'}],
    },
    'openrouter': {
        'checked_at': '2026-10-19',
        'region': 'Regionaler Zugang für Business/Enterprise: EU/EWR, UK und Schweiz. Kein strikt EU-exklusiver Zugang. BYOK kann die tatsächliche Cloud-Ressourcenregion verändern.',
        'training': 'Die vorhandenen Anfragekontrollen verlangen ZDR und untersagen Datensammlung; die konkrete Anbieterkette und der Vertrag bleiben relevant.',
        'retention': 'Der regionale Endpunkt belegt keine pauschale DSGVO-Konformität. Kein Ausweichen auf globale Endpunkte.',
        'billing': 'Separat abgerechneter API-Zugang; regionale Berechtigung muss im eigenen Konto vorhanden sein.',
        'sources': [{'label': 'Regionale Weiterleitung', 'url': 'https://openrouter.ai/docs/guides/features/in-region-routing'}],
    },
}
