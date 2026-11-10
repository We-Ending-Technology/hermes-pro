from dataclasses import dataclass
from typing import Any

from .ebook_validation import validate_ebook

@dataclass(frozen=True)
class QualityReport:
    score: int
    decision: str
    dimensions: dict[str, int]
    findings: list[str]
    safe_fixes: list[str]

class QualityService:
    def evaluate(self, product: dict[str, Any]) -> QualityReport:
        content_data = product.get("content_data")
        if not isinstance(content_data, dict):
            content_data = product.get("content") if isinstance(product.get("content"), dict) else {}
        validation = validate_ebook(content_data)
        title = str(product.get("title", "")).strip()
        audience = str(product.get("audience", "")).strip()
        chapter_words = sum(item["words"] for item in validation["chapter_word_counts"])
        dimensions = {
            "content_length": min(100, round(validation["word_count"] / validation["minimums"]["minimum_words"] * 100)),
            "chapter_structure": min(100, round(validation["chapter_count"] / validation["minimums"]["minimum_chapters"] * 100)),
            "chapter_depth": min(100, round(chapter_words / max(1, validation["chapter_count"]) / validation["minimums"]["minimum_chapter_words"] * 100)) if validation["chapter_count"] else 0,
            "offer_clarity": 100 if title and audience else 45,
        }
        findings = list(validation["findings"])
        fixes = ["Expand the content with original explanations, examples and actionable steps."] if findings else []
        if not title:
            findings.append("Título do produto ausente.")
            fixes.append("Definir um título específico e claro.")
        if not audience:
            findings.append("Público-alvo não definido.")
            fixes.append("Definir o leitor e o problema que o ebook resolve.")
        score = min(validation["score"], 100 if title and audience else 70)
        approved = validation["approved"] and bool(title) and bool(audience) and score >= 80
        if approved:
            findings.append("Conteúdo passou pelos critérios mínimos determinísticos; revisão editorial humana continua recomendada.")
        return QualityReport(score, "approved" if approved else "revision_required", dimensions, findings, fixes)

quality_service = QualityService()