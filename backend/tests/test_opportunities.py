from app.services.opportunities import OpportunityEngine, OpportunityInput


def test_stronger_economics_raise_opportunity_score():
    engine = OpportunityEngine()
    weak = engine.score(OpportunityInput(demand=40, margin=40, ease=40, conversion=40, competition=70, cost=70, risk=70))
    strong = engine.score(OpportunityInput(demand=90, margin=90, ease=90, conversion=90, competition=20, cost=20, risk=20))
    assert strong.score > weak.score
    assert strong.action == "prioritize"


def test_missing_evidence_reduces_confidence_without_fabricating_values():
    result = OpportunityEngine().score(OpportunityInput(demand=80))
    assert result.confidence < 100
    assert result.dimensions["margin"] is None
    assert result.action == "research"


def test_low_confidence_cannot_be_produced_even_with_high_score():
    result = OpportunityEngine().score(OpportunityInput(demand=100, margin=100))
    assert OpportunityEngine().decide(result) == "research"
