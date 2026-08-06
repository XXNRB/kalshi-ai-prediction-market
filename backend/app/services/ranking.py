import statistics
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.price_history import PriceHistory
from app.schemas.ranking import OpportunityScore, ScoreComponent

MAX_COMPONENT = 25.0


def _liquidity_score(market: Market) -> Tuple[float, str]:
    volume = market.volume
    if volume >= 50_000:
        score = 25.0
    elif volume >= 10_000:
        score = 20.0
    elif volume >= 1_000:
        score = 12.0
    elif volume >= 100:
        score = 5.0
    else:
        score = 0.0
    return score, f"{volume:,} contracts traded — {'easy' if score >= 12 else 'hard'} to enter/exit without moving the price."


def _time_advantage_score(market: Market) -> Tuple[float, str]:
    if market.expiration_date is None:
        return 5.0, "Unknown expiration — treated as neutral."

    time_left = market.expiration_date - datetime.utcnow()
    if time_left < timedelta(minutes=10):
        return 0.0, "Resolves in under 10 minutes — too late to act on new research."
    if time_left < timedelta(hours=24):
        return 25.0, "Resolves within 24 hours — fast feedback on your thesis."
    if time_left < timedelta(days=7):
        return 18.0, "Resolves within a week — good runway to act."
    if time_left < timedelta(days=30):
        return 10.0, "Resolves within a month — moderate runway."
    return 5.0, "Resolves over a month out — capital tied up a long time."


def _has_real_sources(data_sources: List[str]) -> bool:
    if not data_sources:
        return False
    lowered = " ".join(s.lower() for s in data_sources)
    return "no relevant" not in lowered and "general knowledge only" not in lowered


def _edge_score(cached: Optional[MarketAnalysisRecord]) -> Tuple[float, str]:
    if cached is None:
        return 0.0, "Not yet researched — generate an AI analysis to score this."
    score = min(MAX_COMPONENT, abs(cached.edge) * 100)
    return score, f"AI research puts the edge at {cached.edge * 100:+.0f} points vs. the market price."


def _information_score(cached: Optional[MarketAnalysisRecord]) -> Tuple[float, str]:
    if cached is None:
        return 0.0, "Not yet researched — generate an AI analysis to score this."
    base = 15.0 if _has_real_sources(cached.data_sources) else 0.0
    confidence_bonus = (cached.confidence / 10) * 10
    score = min(MAX_COMPONENT, base + confidence_bonus)
    source_note = "real cited sources" if base else "no live sources found"
    return score, f"Backed by {source_note}, confidence {cached.confidence}/10."


def risk_score(
    market: Market, recent_history: List[PriceHistory], cached: Optional[MarketAnalysisRecord]
) -> Tuple[float, str]:
    if cached is not None:
        confidence_risk = (10 - cached.confidence) / 10 * 15
        risk_count_penalty = min(10.0, len(cached.risks) * 2)
        score = min(MAX_COMPONENT, confidence_risk + risk_count_penalty)
        return score, f"AI confidence {cached.confidence}/10 with {len(cached.risks)} named risk(s)."

    prices = [p.yes_price for p in recent_history]
    if len(prices) < 2:
        return 0.0, "Not enough price history yet to gauge volatility."
    volatility = statistics.pstdev(prices)
    score = min(MAX_COMPONENT, volatility * 100)
    return score, f"Recent price swings of ~{volatility * 100:.1f}pts (no AI risk assessment yet)."


def _stars_for_score(total: float) -> Tuple[int, str]:
    if total >= 65:
        return 5, "Best opportunity"
    if total >= 50:
        return 4, "Good"
    if total >= 35:
        return 3, "Neutral"
    if total >= 20:
        return 2, "Avoid"
    return 1, "Poor"


def compute_opportunity(
    market: Market,
    recent_history: List[PriceHistory],
    cached: Optional[MarketAnalysisRecord],
) -> OpportunityScore:
    liquidity, liquidity_note = _liquidity_score(market)
    time_advantage, time_note = _time_advantage_score(market)
    edge, edge_note = _edge_score(cached)
    information, info_note = _information_score(cached)
    risk, risk_note = risk_score(market, recent_history, cached)

    total = max(0.0, min(100.0, liquidity + time_advantage + edge + information - risk))
    stars, tier_label = _stars_for_score(total)

    return OpportunityScore(
        total=round(total, 1),
        stars=stars,
        tier_label=tier_label,
        researched=cached is not None,
        components=[
            ScoreComponent(label="Liquidity", score=liquidity, max_score=MAX_COMPONENT, explanation=liquidity_note),
            ScoreComponent(label="Time Advantage", score=time_advantage, max_score=MAX_COMPONENT, explanation=time_note),
            ScoreComponent(label="Probability Edge", score=edge, max_score=MAX_COMPONENT, explanation=edge_note),
            ScoreComponent(label="Information Advantage", score=information, max_score=MAX_COMPONENT, explanation=info_note),
            ScoreComponent(label="Risk", score=-risk, max_score=MAX_COMPONENT, explanation=risk_note),
        ],
    )
