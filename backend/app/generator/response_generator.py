"""
Synthetic response generator.
Produces realistic random form payloads based on question configs and profiles.
"""
from __future__ import annotations
import random
from typing import Any
from loguru import logger

from app.models.schemas import Question, ParsedForm, JobConfig

# ─── Built-in profiles ────────────────────────────────────────────────────────

PROFILES: dict[str, dict] = {
    "young_male": {
        "age_bias": ["18-25", "26-35"],
        "gender_bias": ["Мужской"],
        "budget_bias_low": True,
    },
    "young_female": {
        "age_bias": ["18-25", "26-35"],
        "gender_bias": ["Женская"],
        "budget_bias_low": True,
    },
    "premium_customer": {
        "budget_bias_high": True,
        "quality_weight_boost": 2,
    },
    "budget_buyer": {
        "budget_bias_low": True,
        "price_weight_boost": 2,
    },
    "event_customer": {
        "purpose_bias": ["Оформление мероприятия"],
    },
}

# ─── Text pools ───────────────────────────────────────────────────────────────
# Используются только как запасной вариант, если пользователь
# не заполнил пул ответов в интерфейсе. Добавьте свои варианты
# через UI на вкладке «Настройки» → карточка вопроса.

DEFAULT_SHORT_TEXTS = [
    #"Всё устраивает",
    #"Хорошо",
    #"Нормально",
    #"Доволен(а)",
    #"Неплохо",
    #"Без замечаний",
    #"Всё в порядке",
    #"Удовлетворительно",
    #"Да",
    #"Нет",
    "Детство",

"чаепитие",

"чай",

"радость",

"хруст",

"угощение"
]

DEFAULT_LONG_TEXTS = [
    "В целом всё нравится, замечаний нет.",
    "Хороший продукт/сервис, буду рекомендовать другим.",
    "Всё устраивает, продолжайте в том же духе.",
    "Пользуюсь давно, очень доволен(а).",
    "Качество на уровне, претензий нет.",
    "Иногда есть небольшие недостатки, но в целом всё хорошо.",
    "Доволен(а) результатом, спасибо.",
    "Работает как ожидалось.",
]


# ─── Core generator ───────────────────────────────────────────────────────────

class ResponseGenerator:
    def __init__(self, config: JobConfig):
        self.config = config
        self.questions = config.questions
        self.active_profiles = [
            PROFILES[p] for p in config.profiles if p in PROFILES
        ]

    def _apply_profile_weights(self, question: Question) -> list[int]:
        """Return weights list, optionally modified by active profiles."""
        weights = [
            o.weight if o.enabled else 0
            for o in question.options
        ]
        if not self.active_profiles:
            return weights

        title_lower = question.title.lower()
        for profile in self.active_profiles:
            # Budget biasing
            if "budget_bias_low" in profile and "бюджет" in title_lower:
                for i, opt in enumerate(question.options):
                    if any(k in opt.value for k in ["До", "1000"]):
                        weights[i] = min(weights[i] * 2, 100)
            if "budget_bias_high" in profile and "бюджет" in title_lower:
                for i, opt in enumerate(question.options):
                    if any(k in opt.value for k in ["5000", "3500"]):
                        weights[i] = min(weights[i] * 2, 100)
        return weights

    def _generate_single(self, question: Question) -> str:
        enabled = [o for o in question.options if o.enabled]
        if not enabled:
            return ""
        raw_weights = self._apply_profile_weights(question)
        enabled_weights = [w for o, w in zip(question.options, raw_weights) if o.enabled]

        # Exclude weight=0 options from selection (user intent: "never pick this")
        nonzero = [(o, w) for o, w in zip(enabled, enabled_weights) if w > 0]
        if nonzero:
            opts, ws = zip(*nonzero)
            chosen = random.choices(list(opts), weights=list(ws), k=1)[0]
        else:
            # All weights are 0 — pick uniformly so the form can still be submitted
            chosen = random.choice(enabled)
        return chosen.value

    def _generate_multi(self, question: Question) -> list[str]:
        enabled = [o for o in question.options if o.enabled]
        if not enabled:
            return []

        raw_weights = [
            w for o, w in zip(question.options, self._apply_profile_weights(question))
            if o.enabled
        ]

        # Exclude weight=0 options; fall back to uniform only if all are zero
        pool_with_w = [(o, w) for o, w in zip(enabled, raw_weights) if w > 0]
        if not pool_with_w:
            pool_with_w = [(o, 1) for o in enabled]

        k = random.randint(
            min(question.min_select, len(pool_with_w)),
            min(question.max_select, len(pool_with_w)),
        )

        # Weighted sample without replacement
        chosen: list[str] = []
        pool = list(pool_with_w)
        for _ in range(k):
            if not pool:
                break
            opts, ws = zip(*pool)
            sel = random.choices(list(opts), weights=list(ws), k=1)[0]
            chosen.append(sel.value)
            pool = [(o, w) for o, w in pool if o.value != sel.value]
        return chosen

    def _generate_text(self, question: Question) -> str:
        pool_items = [i for i in (question.text_pool or []) if getattr(i, "enabled", True)]
        if pool_items:
            # Weighted choice (treat weight<=0 as excluded)
            usable = [(i, int(getattr(i, "weight", 1) or 0)) for i in pool_items]
            usable = [(i, w) for i, w in usable if w > 0]
            if usable:
                items, ws = zip(*usable)
                return random.choices(list(items), weights=list(ws), k=1)[0].value
            return random.choice(pool_items).value

        fallback = DEFAULT_LONG_TEXTS if question.qtype == "textarea" else DEFAULT_SHORT_TEXTS
        return random.choice(fallback)

    def generate_response(self) -> dict[str, Any]:
        """Generate one complete form response payload."""
        payload: dict[str, Any] = {}
        for q in self.questions:
            if getattr(q, "enabled", True) is False:
                continue
            if not q.entry_id:
                continue
            try:
                if q.qtype in ("text", "textarea"):
                    # Text questions often have no `options`; their values come from `text_pool`.
                    # Do not apply "enabled options / weights" gating here, otherwise text answers
                    # never make it into the payload.
                    if q.options:
                        # treat options as a text pool
                        payload[f"entry.{q.entry_id}"] = random.choice(
                            [o.value for o in q.options if o.enabled] or DEFAULT_SHORT_TEXTS
                        )
                    else:
                        payload[f"entry.{q.entry_id}"] = self._generate_text(q)
                elif q.qtype == "single":
                    raw_weights = self._apply_profile_weights(q)
                    enabled_options = [o for o in q.options if o.enabled]
                    if not enabled_options or all(w == 0 for w in raw_weights):
                        continue
                    payload[f"entry.{q.entry_id}"] = self._generate_single(q)
                elif q.qtype == "multi":
                    raw_weights = self._apply_profile_weights(q)
                    enabled_options = [o for o in q.options if o.enabled]
                    if not enabled_options or all(w == 0 for w in raw_weights):
                        continue
                    vals = self._generate_multi(q)
                    payload[f"entry.{q.entry_id}"] = vals
            except Exception as exc:
                logger.warning(f"Error generating answer for '{q.title}': {exc}")
                payload[f"entry.{q.entry_id}"] = ""
        return payload
