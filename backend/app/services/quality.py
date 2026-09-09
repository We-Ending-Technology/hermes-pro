from dataclasses import dataclass

@dataclass(frozen=True)
class QualityReport:
    score: int
    decision: str
    dimensions: dict[str, int]
    findings: list[str]
    safe_fixes: list[str]

class QualityService:
    def evaluate(self, product: dict) -> QualityReport:
        text = str(product.get("content", ""))
        title = str(product.get("title", "")).strip()
        dimensions = {
            "structure": 100 if product.get("chapters") else 45,
            "readability": 85 if len(text) >= 500 else 45,
            "coherence": 80 if len(text.split()) >= 100 else 50,
            "originality_risk_signal": 85 if len(text) >= 1000 else 65,
            "formatting": 90 if product.get("format", "pdf") in {"pdf", "docx"} else 60,
            "offer_clarity": 85 if title and product.get("audience") else 50,
        }
        score = round(sum(dimensions.values()) / len(dimensions))
        findings: list[str] = []
        fixes: list[str] = []
        if not product.get("chapters"):
            findings.append("Estrutura sem capítulos detectáveis."); fixes.append("Gerar ou revisar sumário e títulos de capítulos.")
        if len(text) < 500:
            findings.append("Conteúdo curto para uma avaliação editorial robusta."); fixes.append("Expandir exemplos e explicações sem repetir ideias.")
        if not product.get("audience"):
            findings.append("Público-alvo não está definido."); fixes.append("Preencher público e problema principal.")
        if not findings:
            findings.append("Nenhum bloqueio determinístico encontrado nos campos avaliados.")
        return QualityReport(score, "approved" if score >= 80 else "revision_required", dimensions, findings, fixes)

quality_service = QualityService()
