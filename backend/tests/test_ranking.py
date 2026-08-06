from datetime import datetime, timedelta

from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.price_history import PriceHistory
from app.services.ranking import (
    _edge_score,
    _information_score,
    _liquidity_score,
    risk_score,
    _stars_for_score,
    _time_advantage_score,
    compute_opportunity,
)


def make_market(volume=0, minutes_to_expiration=None, yes_price=0.5) -> Market:
    expiration = (
        datetime.utcnow() + timedelta(minutes=minutes_to_expiration)
        if minutes_to_expiration is not None
        else None
    )
    return Market(
        id=1,
        ticker="TEST",
        title="Test market",
        yes_price=yes_price,
        no_price=round(1 - yes_price, 4),
        volume=volume,
        open_interest=100,
        liquidity=0.0,
        expiration_date=expiration,
    )


def make_history(prices) -> list:
    base = datetime.utcnow() - timedelta(minutes=len(prices))
    return [
        PriceHistory(market_id=1, timestamp=base + timedelta(minutes=i), yes_price=p, no_price=1 - p, volume=1)
        for i, p in enumerate(prices)
    ]


def make_analysis(edge=0.16, confidence=8, risks=None, data_sources=None) -> MarketAnalysisRecord:
    return MarketAnalysisRecord(
        market_id=1,
        market_implied_probability=0.42,
        ai_estimated_probability=0.42 + edge,
        edge=edge,
        reasoning=["Reason one"],
        risks=risks if risks is not None else ["Risk one", "Risk two"],
        confidence=confidence,
        recommendation="Consider YES",
        suggested_allocation_pct=5.0,
        data_sources=data_sources if data_sources is not None else ["Reuters: some article"],
    )


def test_liquidity_score_tiers():
    assert _liquidity_score(make_market(volume=0))[0] == 0.0
    assert _liquidity_score(make_market(volume=100))[0] == 5.0
    assert _liquidity_score(make_market(volume=1_000))[0] == 12.0
    assert _liquidity_score(make_market(volume=10_000))[0] == 20.0
    assert _liquidity_score(make_market(volume=50_000))[0] == 25.0


def test_time_advantage_score_tiers():
    assert _time_advantage_score(make_market(minutes_to_expiration=5))[0] == 0.0
    assert _time_advantage_score(make_market(minutes_to_expiration=60))[0] == 25.0
    assert _time_advantage_score(make_market(minutes_to_expiration=60 * 24 * 3))[0] == 18.0
    assert _time_advantage_score(make_market(minutes_to_expiration=60 * 24 * 15))[0] == 10.0
    assert _time_advantage_score(make_market(minutes_to_expiration=60 * 24 * 60))[0] == 5.0
    assert _time_advantage_score(make_market(minutes_to_expiration=None))[0] == 5.0


def test_edge_score_requires_cached_analysis():
    assert _edge_score(None)[0] == 0.0

    small_edge = _edge_score(make_analysis(edge=0.10))[0]
    large_edge = _edge_score(make_analysis(edge=0.30))[0]
    assert small_edge == 10.0
    assert large_edge == 25.0  # capped

    # sign doesn't matter, only magnitude
    assert _edge_score(make_analysis(edge=-0.10))[0] == small_edge


def test_information_score_rewards_real_sources_and_confidence():
    assert _information_score(None)[0] == 0.0

    with_sources = _information_score(make_analysis(confidence=10, data_sources=["Reuters: X"]))[0]
    no_sources = _information_score(
        make_analysis(confidence=10, data_sources=["No relevant live web sources found — reasoning based on general knowledge only"])
    )[0]
    assert with_sources == 25.0  # 15 base + 10 confidence bonus
    assert no_sources == 10.0  # 0 base + 10 confidence bonus


def test_risk_score_uses_cached_confidence_and_risk_count():
    high_confidence_few_risks = risk_score(make_market(), [], make_analysis(confidence=10, risks=["one"]))[0]
    low_confidence_many_risks = risk_score(
        make_market(), [], make_analysis(confidence=2, risks=["a", "b", "c", "d", "e", "f"])
    )[0]
    assert high_confidence_few_risks == 2.0  # (10-10)/10*15=0 + min(10, 1*2)=2
    assert low_confidence_many_risks == 22.0  # (10-2)/10*15=12 + min(10, 6*2)=10
    assert high_confidence_few_risks < low_confidence_many_risks


def test_risk_score_falls_back_to_price_volatility_without_analysis():
    market = make_market()
    assert risk_score(market, [], None)[0] == 0.0  # no history at all
    assert risk_score(market, make_history([0.5]), None)[0] == 0.0  # single point

    stable = risk_score(market, make_history([0.50, 0.50, 0.51, 0.50]), None)[0]
    volatile = risk_score(market, make_history([0.20, 0.60, 0.30, 0.70]), None)[0]
    assert stable < volatile


def test_stars_for_score_tiers():
    assert _stars_for_score(90)[0] == 5
    assert _stars_for_score(65)[0] == 5
    assert _stars_for_score(55)[0] == 4
    assert _stars_for_score(40)[0] == 3
    assert _stars_for_score(25)[0] == 2
    assert _stars_for_score(5)[0] == 1


def test_compute_opportunity_unresearched_market():
    market = make_market(volume=50_000, minutes_to_expiration=60)
    history = make_history([0.50, 0.50, 0.50])

    result = compute_opportunity(market, history, None)

    assert result.researched is False
    by_label = {c.label: c.score for c in result.components}
    assert by_label["Liquidity"] == 25.0
    assert by_label["Time Advantage"] == 25.0
    assert by_label["Probability Edge"] == 0.0
    assert by_label["Information Advantage"] == 0.0
    # 25 + 25 + 0 + 0 - ~0 (stable prices) = ~50 -> 4 stars
    assert result.total >= 49
    assert result.stars == 4


def test_compute_opportunity_researched_market_scores_higher_with_strong_edge():
    market = make_market(volume=50_000, minutes_to_expiration=60)
    history = make_history([0.42, 0.42, 0.42])
    analysis = make_analysis(edge=0.30, confidence=9, risks=["one"], data_sources=["Reuters: X"])

    result = compute_opportunity(market, history, analysis)

    assert result.researched is True
    by_label = {c.label: c.score for c in result.components}
    assert by_label["Probability Edge"] == 25.0
    assert by_label["Information Advantage"] > 0
    assert result.stars == 5
    assert result.total > 65
