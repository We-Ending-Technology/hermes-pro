from dataclasses import dataclass

@dataclass(frozen=True)
class RadarScore:
    score: int
    confidence: int
    dimensions: dict[str, int]
    findings: list[str]

class RadarService:
    weights = {
        "demand": 0.22,
        "competition": 0.14,
        "differentiation": 0.18,
        "production_difficulty": 0.14,
        "pricing_potential": 0.17,
        "audience_clarity": 0.15,
    }

    def score(self, signals: dict[str, float]) -> RadarScore:
        dimensions = {k: round(max(0, min(100, float(signals.get(k, 0))))) for k in self.weights}
        adjusted = dict(dimensions)
        adjusted["competition"] = 100 - adjusted["competition"]
        adjusted["production_difficulty"] = 100 - adjusted["production_difficulty"]
        score = round(sum(adjusted[k] * w for k, w in self.weights.items()))
        provided = sum(k in signals for k in self.weights)
        confidence = round(100 * provided / len(self.weights))
        findings: list[str] = []
        if dimensions["demand"] < 50: findings.append("Demanda informada abaixo de 50; valide a hipótese antes de produzir em escala.")
        if dimensions["competition"] > 70: findings.append("Competição informada alta; aumente diferenciação ou escolha um recorte mais específico.")
        if dimensions["audience_clarity"] < 60: findings.append("Público pouco definido; refine problema, perfil e promessa do produto.")
        if dimensions["pricing_potential"] < 50: findings.append("Potencial de preço baixo; considere aumentar valor percebido sem prometer resultados.")
        if not findings: findings.append("Sinais equilibrados; transforme a hipótese em um experimento mensurável.")
        return RadarScore(score, confidence, dimensions, findings)

radar_service = RadarService()
