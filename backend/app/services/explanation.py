"""'Why this journey?' — explanations generated from structured scoring output.

The rule-based explainer is always available. The AI explainer (Anthropic Messages API) only rephrases a
fact sheet built from the engine output, and its text is rejected unless every number it contains appears
in that fact sheet.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.result import Explanation, Itinerary, MissionSummary, Tradeoff
from app.utils.format import fmt_clock, fmt_money, fmt_minutes, mission_noun

log = get_logger(__name__)

_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


# --------------------------------------------------------------------------- facts
MODE_NAME = {"flight": "flight", "train": "train", "bus": "bus", "transit": "public transport", "ground": "road trip"}


def build_fact_sheet(mission: MissionSummary, best: Itinerary, alternatives: dict[str, Itinerary],
                     tradeoff: Tradeoff | None = None) -> dict[str, Any]:
    main = best.main
    facts: dict[str, Any] = {
        "mission": {
            "type": mission_noun(mission.mission_type),
            "venue": mission.venue.name,
            "deadline": mission.arrival_deadline,
            "budget": fmt_money(mission.budget, mission.currency),
            "required_buffer": f"{mission.min_buffer_minutes} minutes",
            "travelers": mission.travelers,
            "priority": mission.priority.replace("_", " "),
        },
        "recommended": {
            "mode": MODE_NAME.get(best.mode, best.mode),
            "strategy": "travel the day before and stay overnight" if best.strategy == "night_before"
            else "travel on the mission day",
            "service": main.title,
            "departs": fmt_clock(main.departure_time),
            "arrives": fmt_clock(main.arrival_time),
            "changes": main.transfers,
            "total_trip_cost": fmt_money(best.cost.total, best.cost.currency) if best.cost.total is not None else "unknown",
            "budget_remaining": fmt_money(best.cost.budget_remaining, best.cost.currency)
            if best.cost.budget_remaining is not None else "unknown",
            "within_budget": bool(best.constraints and best.constraints.within_budget),
            "ticket_price_is": best.cost.ticket_source,
            "arrive_at_venue": fmt_clock(best.arrival.venue_arrival),
            "arrival_buffer": f"{best.arrival.buffer_minutes} minutes",
            "risk_level": best.risk.level if best.risk else None,
            "mission_score": best.scores.overall if best.scores else None,
        },
    }
    if best.arrival.leave_hotel_at:
        facts["recommended"]["leave_hotel_at"] = fmt_clock(best.arrival.leave_hotel_at)
    if best.hotel:
        facts["recommended"]["hotel"] = {
            "name": best.hotel.name,
            "distance_to_venue": f"{best.hotel.distance_km:.1f} km" if best.hotel.distance_km is not None else None,
            "rating": best.hotel.rating,
            "review_count": best.hotel.reviews,
        }
    if best.risk:
        facts["recommended"]["main_risks"] = [f.title for f in best.risk.factors if f.severity != "low"][:2]
        facts["recommended"]["strengths"] = best.risk.strengths[:4]
    others = {}
    for name, itin in alternatives.items():
        if itin.id == best.id:
            continue
        others[name] = {
            "mode": MODE_NAME.get(itin.mode, itin.mode),
            "total_trip_cost": fmt_money(itin.cost.total, itin.cost.currency) if itin.cost.total is not None else "unknown",
            "arrival_buffer": f"{itin.arrival.buffer_minutes} minutes",
            "travel_time": fmt_minutes(itin.total_travel_minutes),
            "risk_level": itin.risk.level if itin.risk else None,
            "mission_score": itin.scores.overall if itin.scores else None,
        }
    if others:
        facts["alternatives"] = others
    comparison = _comparison(best, alternatives.get("cheapest"))
    if comparison:
        facts["vs_cheapest"] = comparison
    if tradeoff:
        facts["time_vs_money"] = tradeoff.sentence
    return facts


def _comparison(best: Itinerary, cheapest: Itinerary | None) -> str | None:
    """Computed sentence: what the recommendation costs extra versus the cheapest, and what it buys."""
    if cheapest is None or cheapest.id == best.id or best.cost.total is None or cheapest.cost.total is None:
        return None
    extra = best.cost.total - cheapest.cost.total
    if extra <= 0:
        return None
    saved = cheapest.total_travel_minutes - best.total_travel_minutes
    gains = []
    if saved >= 90:
        hours = round(saved / 60)
        gains.append(f"save about {hours} hour{'s' if hours != 1 else ''} of travel")
    elif saved > 0:
        gains.append(f"save {saved} minutes of travel")
    if best.risk and cheapest.risk and _RISK_ORDER[cheapest.risk.level] > _RISK_ORDER[best.risk.level]:
        gains.append(f"cut the risk from {cheapest.risk.level} to {best.risk.level}")
    gains.append(f"arrive with a {best.arrival.buffer_minutes}-minute buffer")
    return (f"You spend {fmt_money(extra, best.cost.currency)} more than the cheapest option, but "
            + ", ".join(gains[:-1]) + (" and " if len(gains) > 1 else "") + gains[-1] + ".")


# --------------------------------------------------------------------------- rules
_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _tradeoff(best: Itinerary, other: Itinerary) -> str:
    """The most important way `other` is worse than `best`, stated from the data."""
    if best.risk and other.risk and _RISK_ORDER[other.risk.level] > _RISK_ORDER[best.risk.level]:
        return f"carries {other.risk.level} risk"
    if other.arrival.buffer_minutes < best.arrival.buffer_minutes - 10:
        return f"leaves only {other.arrival.buffer_minutes} minutes of buffer"
    if other.total_travel_minutes > best.total_travel_minutes + 120:
        return f"takes {fmt_minutes(other.total_travel_minutes)} of travel"
    if other.main.transfers > best.main.transfers:
        return f"adds {other.main.transfers} change{'s' if other.main.transfers > 1 else ''}"
    if best.hotel and other.hotel:
        if (other.hotel.distance_km or 0) > (best.hotel.distance_km or 0) + 1:
            return f"puts you {other.hotel.distance_km:.1f} km from the venue"
        if other.hotel.rating and best.hotel.rating and other.hotel.rating < best.hotel.rating - 0.2:
            return f"uses a lower-rated hotel ({other.hotel.rating:.1f})"
    if best.scores and other.scores:
        return f"scores lower overall ({other.scores.overall} vs {best.scores.overall})"
    return "is a weaker fit overall"


class RuleExplainer:
    def explain(self, mission: MissionSummary, best: Itinerary, alternatives: dict[str, Itinerary],
                tradeoff: Tradeoff | None = None) -> Explanation:
        main = best.main
        noun = mission_noun(mission.mission_type)
        parts: list[str] = []
        comparison = _comparison(best, alternatives.get("cheapest"))
        if comparison:
            parts.append(comparison)

        if best.mode == "flight":
            service = f"{main.provider} {main.references[0]}" if main.references else main.title
            if best.strategy == "night_before":
                when = "the evening before" if main.arrival_time.hour >= 17 else "the day before"
                parts.append(f"Flying in {when} on {service} (lands {fmt_clock(main.arrival_time)}) takes flight "
                             f"delays out of the equation for your {noun}.")
            else:
                stop_text = "a direct flight" if main.stops == 0 else f"a {main.stops}-stop flight"
                parts.append(f"{service} is {stop_text} landing at {fmt_clock(main.arrival_time)} on the morning of "
                             f"your {noun}.")
        elif best.mode in ("train", "bus", "transit"):
            word = MODE_NAME[best.mode]
            changes = f" with {main.transfers} change{'s' if main.transfers != 1 else ''}" if main.transfers else ""
            parts.append(f"The {word} ({main.title}){changes} leaves {main.departure_label} at "
                         f"{fmt_clock(main.departure_time)} and arrives at {fmt_clock(main.arrival_time)}"
                         + (" the day before, so delays can't make you late." if best.strategy == "night_before" else "."))
        else:
            parts.append(f"Driving {main.distance_km:,.0f} km door to door, leaving at {fmt_clock(main.departure_time)}.")

        buffer_text = f"a {best.arrival.buffer_minutes}-minute buffer before your {mission.arrival_deadline} start"
        if best.cost.total is not None and best.constraints:
            if best.constraints.within_budget:
                parts.append(f"At {fmt_money(best.cost.total, best.cost.currency)} all-in it leaves "
                             f"{fmt_money(mission.budget - best.cost.total, best.cost.currency)} of your budget and gets "
                             f"you to {mission.venue.name} by {fmt_clock(best.arrival.venue_arrival)}, {buffer_text}.")
            else:
                parts.append(f"It costs {fmt_money(best.cost.total, best.cost.currency)}, "
                             f"{fmt_money(best.cost.total - mission.budget, best.cost.currency)} over budget, but gets you "
                             f"to {mission.venue.name} by {fmt_clock(best.arrival.venue_arrival)}, {buffer_text}.")

        if best.hotel and best.hotel.distance_km is not None:
            rating = f", rated {best.hotel.rating:.1f}" if best.hotel.rating else ""
            leave = f" — leave at {fmt_clock(best.arrival.leave_hotel_at)}" if best.arrival.leave_hotel_at else ""
            parts.append(f"{best.hotel.name} is {best.hotel.distance_km:.1f} km from the venue{rating}{leave}.")

        cheapest = alternatives.get("cheapest")
        if not comparison and cheapest and cheapest.id != best.id and cheapest.cost.total is not None \
                and best.cost.total is not None and best.cost.total > cheapest.cost.total:
            saving = best.cost.total - cheapest.cost.total
            parts.append(f"The cheapest option saves {fmt_money(saving, cheapest.cost.currency)} but "
                         f"{_tradeoff(best, cheapest)}.")

        if best.risk:
            concern = next((f for f in best.risk.factors if f.severity != "low"), None)
            if concern:
                parts.append(f"Watch out for: {concern.title.lower()}.")
        return Explanation(text=" ".join(parts), source="rules")


# --------------------------------------------------------------------------- fact check
def _normalise_numbers(text: str) -> set[str]:
    found: set[str] = set()
    for h, m in _TIME.findall(text):
        found.add(f"{int(h)}:{m}")
    stripped = _TIME.sub(" ", text)
    for raw in _NUMBER.findall(stripped):
        value = raw.replace(",", "")
        try:
            number = float(value)
        except ValueError:
            continue
        found.add(f"{number:g}")
    return found


def fact_check(text: str, facts: dict[str, Any]) -> list[str]:
    """Returns numbers present in `text` that do not appear anywhere in `facts`."""
    allowed = _normalise_numbers(json.dumps(facts, ensure_ascii=False))
    return sorted(n for n in _normalise_numbers(text) if n not in allowed)


# --------------------------------------------------------------------------- AI
_SYSTEM = (
    "You explain a travel recommendation that a deterministic scoring engine has already made. "
    "Write 2 to 4 plain sentences (no markdown, no lists, no greeting) telling the traveller why the "
    "recommended journey is the best fit for their mission, and what to watch out for. "
    "Use ONLY the facts in the JSON you are given. Copy prices, times, distances, ratings and durations "
    "exactly as written there; never compute, round, convert or invent any number, and do not mention "
    "anything (traffic levels, weather, amenities, reviews) that is not in the JSON. "
    "If `vs_cheapest` is present, start with that sentence. Only if `ticket_price_is` is \"estimated\", say "
    "the ticket price is an estimate; otherwise do not mention where data came from."
)


class AIExplainer:
    def __init__(self, settings: Settings) -> None:
        from anthropic import AsyncAnthropic

        self.model = settings.ai_model
        self._client = AsyncAnthropic(api_key=settings.ai_api_key, timeout=settings.ai_timeout_seconds, max_retries=1)

    async def explain(self, facts: dict[str, Any]) -> str | None:
        import anthropic

        try:
            response = await self._client.beta.messages.create(
                model=self.model,
                max_tokens=2000,
                system=_SYSTEM,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": json.dumps(facts, ensure_ascii=False, indent=2)}],
            )
        except anthropic.RateLimitError:
            log.warning("ai explanation rate limited")
            return None
        except anthropic.APIStatusError as exc:
            log.warning("ai explanation failed", extra={"context": {"status": exc.status_code}})
            return None
        except anthropic.APIConnectionError as exc:
            log.warning("ai explanation connection error", extra={"context": {"error": type(exc).__name__}})
            return None
        if response.stop_reason == "refusal":
            return None
        text = " ".join(block.text for block in response.content if block.type == "text").strip()
        return text or None


class ChatCompletionsExplainer:
    """OpenAI-compatible chat completions (OpenRouter, EURI, ...). Tries AI_MODEL, then AI_MODEL_FAST."""

    def __init__(self, settings: Settings) -> None:
        self.models = [m for m in (settings.ai_model, settings.ai_model_fast) if m]
        self.model = self.models[0]
        self._url = settings.ai_base_url.rstrip("/") + "/chat/completions"
        self._key = settings.ai_api_key
        self._timeout = settings.ai_timeout_seconds

    async def explain(self, facts: dict[str, Any]) -> str | None:
        import httpx

        payload_messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(facts, ensure_ascii=False, indent=2)},
        ]
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for model in self.models:
                try:
                    response = await client.post(
                        self._url,
                        headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                        json={"model": model, "messages": payload_messages, "max_tokens": 400},
                    )
                except httpx.HTTPError as exc:
                    log.warning("ai request failed", extra={"context": {"model": model, "error": type(exc).__name__}})
                    continue
                if response.status_code != 200:
                    log.warning("ai provider error", extra={"context": {"model": model, "status": response.status_code}})
                    continue
                try:
                    text = response.json()["choices"][0]["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError):
                    log.warning("ai malformed response", extra={"context": {"model": model}})
                    continue
                if isinstance(text, str) and text.strip():
                    self.model = model
                    return text.strip()
        return None


def make_ai_explainer(settings: Settings) -> AIExplainer | ChatCompletionsExplainer:
    if settings.ai_provider.lower() in ("openrouter", "euri"):
        return ChatCompletionsExplainer(settings)
    return AIExplainer(settings)


async def explain_recommendation(settings: Settings, mission: MissionSummary, best: Itinerary,
                                 alternatives: dict[str, Itinerary], *,
                                 ai: AIExplainer | ChatCompletionsExplainer | None = None,
                                 tradeoff: Tradeoff | None = None) -> Explanation:
    rules = RuleExplainer().explain(mission, best, alternatives, tradeoff)
    if ai is None and not settings.ai_configured:
        return rules
    try:
        ai = ai or make_ai_explainer(settings)
        facts = build_fact_sheet(mission, best, alternatives, tradeoff)
        text = await ai.explain(facts)
    except Exception as exc:  # the explanation is optional — never fail the mission
        log.warning("ai explainer error", extra={"context": {"error": type(exc).__name__}})
        text = None
    if not text:
        rules.note = "AI explanation unavailable — generated from the scoring factors."
        return rules
    invented = fact_check(text, facts)
    if invented:
        log.warning("ai explanation rejected by fact check", extra={"context": {"numbers": invented}})
        rules.note = "AI text failed the fact check — showing the rule-based explanation."
        return rules
    return Explanation(text=text, source="ai", model=ai.model)
