from backend.app.domain.opportunities import score_opportunity


def test_opportunity_score_uses_commercial_signals_and_confidence():
    result = score_opportunity(
        {
            "demand": 90,
            "margin": 80,
            "ease": 70,
            "conversion_probability": 60,
            "capacity": 90,
            "competition": 20,
            "cost": 10,
            "risk": 10,
        }
    )

    assert result["score"] == 79.0
    assert result["confidence"] == 1.0
    assert set(result["dimensions"]) == {
        "demand",
        "margin",
        "ease",
        "conversion_probability",
        "capacity",
        "competition",
        "cost",
        "risk",
    }
