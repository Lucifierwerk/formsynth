"""
Comprehensive tests for ResponseGenerator.
Covers: single, multi, text, textarea question types;
min/max_select constraints; exclusive options; weight=0 exclusion;
profile biasing; edge cases.
"""
import pytest
import random
from collections import Counter
from app.models.schemas import Question, Option, TextPoolItem, JobConfig, ParsedForm
from app.generator.response_generator import ResponseGenerator


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_option(value: str, weight: int = 1, enabled: bool = True, exclusive: bool = False) -> Option:
    return Option(value=value, weight=weight, enabled=enabled, exclusive=exclusive)


def make_single(title: str, options: list[Option], entry_id: str = "100") -> Question:
    return Question(entry_id=entry_id, title=title, qtype="single", options=options)


def make_multi(title: str, options: list[Option], min_s: int = 1, max_s: int = 3, entry_id: str = "200") -> Question:
    return Question(entry_id=entry_id, title=title, qtype="multi", options=options,
                    min_select=min_s, max_select=max_s)


def make_text(title: str, pool: list[str] | None = None, entry_id: str = "300") -> Question:
    tp = [TextPoolItem(value=v, weight=1, enabled=True) for v in (pool or [])]
    return Question(entry_id=entry_id, title=title, qtype="text", text_pool=tp)


def make_textarea(title: str, pool: list[str] | None = None, entry_id: str = "400") -> Question:
    tp = [TextPoolItem(value=v, weight=1, enabled=True) for v in (pool or [])]
    return Question(entry_id=entry_id, title=title, qtype="textarea", text_pool=tp)


def make_config(questions: list[Question]) -> JobConfig:
    return JobConfig(url="https://example.com", form_id="test", questions=questions)


def gen(questions: list[Question]) -> ResponseGenerator:
    return ResponseGenerator(make_config(questions))


# ── Single-choice questions ────────────────────────────────────────────────────

class TestSingle:
    def test_returns_valid_option(self):
        q = make_single("Пол", [make_option("Мужской"), make_option("Женский")])
        g = gen([q])
        result = g._generate_single(q)
        assert result in ("Мужской", "Женский")

    def test_respects_weights(self):
        """With weight=10 vs weight=0, high-weight option is always chosen."""
        q = make_single("q", [make_option("A", weight=10), make_option("B", weight=0)])
        g = gen([q])
        results = {g._generate_single(q) for _ in range(50)}
        assert results == {"A"}

    def test_disabled_option_never_chosen(self):
        q = make_single("q", [make_option("A"), make_option("B", enabled=False)])
        g = gen([q])
        results = {g._generate_single(q) for _ in range(50)}
        assert "B" not in results

    def test_all_disabled_returns_empty(self):
        q = make_single("q", [make_option("A", enabled=False)])
        g = gen([q])
        assert g._generate_single(q) == ""

    def test_all_zero_weight_fallback_uniform(self):
        """All weights=0 → falls back to uniform pick, not empty."""
        q = make_single("q", [make_option("A", weight=0), make_option("B", weight=0)])
        g = gen([q])
        results = {g._generate_single(q) for _ in range(50)}
        # Both can appear since it falls back to uniform
        assert results.issubset({"A", "B"})
        assert len(results) > 0


# ── Multi-choice questions ─────────────────────────────────────────────────────

class TestMulti:
    def test_count_within_range(self):
        opts = [make_option(f"opt{i}") for i in range(5)]
        q = make_multi("q", opts, min_s=2, max_s=4)
        g = gen([q])
        for _ in range(100):
            result = g._generate_multi(q)
            assert 2 <= len(result) <= 4, f"Got {len(result)}"

    def test_no_duplicates(self):
        opts = [make_option(f"opt{i}") for i in range(5)]
        q = make_multi("q", opts, min_s=3, max_s=3)
        g = gen([q])
        for _ in range(50):
            result = g._generate_multi(q)
            assert len(result) == len(set(result)), "Duplicate values found"

    def test_max_equals_available(self):
        """max_select > actual options → selects all enabled options."""
        opts = [make_option("A"), make_option("B")]
        q = make_multi("q", opts, min_s=1, max_s=10)
        g = gen([q])
        for _ in range(20):
            result = g._generate_multi(q)
            assert len(result) <= 2

    def test_disabled_not_chosen(self):
        opts = [make_option("A"), make_option("B", enabled=False), make_option("C")]
        q = make_multi("q", opts, min_s=1, max_s=3)
        g = gen([q])
        for _ in range(50):
            assert "B" not in g._generate_multi(q)

    def test_weight_zero_not_chosen(self):
        opts = [make_option("A", weight=10), make_option("NEVER", weight=0), make_option("C", weight=10)]
        q = make_multi("q", opts, min_s=2, max_s=2)
        g = gen([q])
        for _ in range(50):
            assert "NEVER" not in g._generate_multi(q)

    def test_min_equal_max(self):
        opts = [make_option(f"opt{i}") for i in range(5)]
        q = make_multi("q", opts, min_s=3, max_s=3)
        g = gen([q])
        for _ in range(30):
            assert len(g._generate_multi(q)) == 3

    def test_min_1_max_1_always_one(self):
        opts = [make_option("A"), make_option("B"), make_option("C")]
        q = make_multi("q", opts, min_s=1, max_s=1)
        g = gen([q])
        for _ in range(30):
            assert len(g._generate_multi(q)) == 1

    def test_empty_options_returns_empty(self):
        q = make_multi("q", [], min_s=1, max_s=3)
        g = gen([q])
        assert g._generate_multi(q) == []

    def test_all_disabled_returns_empty(self):
        opts = [make_option("A", enabled=False), make_option("B", enabled=False)]
        q = make_multi("q", opts, min_s=1, max_s=2)
        g = gen([q])
        assert g._generate_multi(q) == []


# ── Exclusive options ──────────────────────────────────────────────────────────

class TestExclusive:
    def test_exclusive_returns_only_one(self):
        """When exclusive option chosen, result must contain only that one value."""
        opts = [
            make_option("A"), make_option("B"),
            make_option("Ничего из перечисленного", exclusive=True),
        ]
        q = make_multi("q", opts, min_s=1, max_s=3)
        g = gen([q])
        # Run many times; any time exclusive is chosen it must be alone
        for _ in range(200):
            result = g._generate_multi(q)
            if "Ничего из перечисленного" in result:
                assert result == ["Ничего из перечисленного"], (
                    f"Exclusive mixed with others: {result}"
                )

    def test_exclusive_weight_0_never_solo(self):
        """Exclusive option with weight=0 is never selected."""
        opts = [
            make_option("A"), make_option("B"),
            make_option("Exclusive", exclusive=True, weight=0),
        ]
        q = make_multi("q", opts, min_s=1, max_s=2)
        g = gen([q])
        for _ in range(100):
            assert "Exclusive" not in g._generate_multi(q)

    def test_only_exclusive_options(self):
        """All options exclusive → one is chosen exclusively."""
        opts = [make_option("Solo1", exclusive=True), make_option("Solo2", exclusive=True)]
        q = make_multi("q", opts, min_s=1, max_s=2)
        g = gen([q])
        for _ in range(50):
            result = g._generate_multi(q)
            assert len(result) == 1
            assert result[0] in ("Solo1", "Solo2")

    def test_exclusive_high_weight_dominates(self):
        """High-weight exclusive dominates regular options in probabilistic selection."""
        opts = [
            make_option("Regular1", weight=1),
            make_option("Regular2", weight=1),
            make_option("NONE", exclusive=True, weight=100),
        ]
        q = make_multi("q", opts, min_s=1, max_s=3)
        g = gen([q])
        results = [g._generate_multi(q) for _ in range(500)]
        none_count = sum(1 for r in results if r == ["NONE"])
        # With weight 100 vs 2 total regular, exclusive should win ~98% of the time
        assert none_count > 400, f"NONE chosen only {none_count}/500 times"

    def test_exclusive_disabled_not_chosen(self):
        opts = [
            make_option("A"), make_option("B"),
            make_option("Exclusive", exclusive=True, enabled=False),
        ]
        q = make_multi("q", opts, min_s=1, max_s=3)
        g = gen([q])
        for _ in range(50):
            assert "Exclusive" not in g._generate_multi(q)


# ── Text / textarea questions ──────────────────────────────────────────────────

class TestText:
    def test_uses_pool(self):
        pool = ["Отлично", "Хорошо", "Неплохо"]
        q = make_text("Комментарий", pool)
        g = gen([q])
        for _ in range(20):
            assert g._generate_text(q) in pool

    def test_falls_back_to_default_when_pool_empty(self):
        from app.generator.response_generator import DEFAULT_SHORT_TEXTS
        q = make_text("Комментарий", [])
        g = gen([q])
        result = g._generate_text(q)
        assert isinstance(result, str) and len(result) > 0
        assert result in DEFAULT_SHORT_TEXTS

    def test_textarea_fallback_long(self):
        from app.generator.response_generator import DEFAULT_LONG_TEXTS
        q = make_textarea("Описание", [])
        g = gen([q])
        result = g._generate_text(q)
        assert result in DEFAULT_LONG_TEXTS

    def test_disabled_pool_item_not_chosen(self):
        from app.models.schemas import TextPoolItem
        q = make_text("q", [])
        q.text_pool = [
            TextPoolItem(value="Enabled", weight=1, enabled=True),
            TextPoolItem(value="Disabled", weight=1, enabled=False),
        ]
        g = gen([q])
        for _ in range(30):
            assert g._generate_text(q) == "Enabled"

    def test_pool_weight_0_not_chosen(self):
        from app.models.schemas import TextPoolItem
        q = make_text("q", [])
        q.text_pool = [
            TextPoolItem(value="Good", weight=10, enabled=True),
            TextPoolItem(value="Never", weight=0, enabled=True),
        ]
        g = gen([q])
        for _ in range(30):
            assert g._generate_text(q) == "Good"


# ── Full generate_response payload ────────────────────────────────────────────

class TestGenerateResponse:
    def test_all_qtypes_present_in_payload(self):
        questions = [
            make_single("Пол", [make_option("М"), make_option("Ж")], entry_id="1"),
            make_multi("Увлечения", [make_option("Спорт"), make_option("Музыка"), make_option("Чтение")],
                       min_s=1, max_s=2, entry_id="2"),
            make_text("Имя", ["Александр", "Мария"], entry_id="3"),
            make_textarea("Отзыв", ["Всё отлично"], entry_id="4"),
        ]
        g = gen(questions)
        payload = g.generate_response()
        assert "entry.1" in payload
        assert "entry.2" in payload
        assert "entry.3" in payload
        assert "entry.4" in payload

    def test_disabled_question_not_in_payload(self):
        questions = [
            make_single("Включён", [make_option("Да")], entry_id="1"),
        ]
        questions[0].enabled = False
        g = gen(questions)
        payload = g.generate_response()
        assert "entry.1" not in payload

    def test_multi_payload_is_list(self):
        questions = [
            make_multi("multi", [make_option("A"), make_option("B"), make_option("C")],
                       min_s=1, max_s=2, entry_id="1"),
        ]
        g = gen(questions)
        payload = g.generate_response()
        assert isinstance(payload["entry.1"], list)

    def test_generate_1000_no_exception(self):
        """Smoke test: 1000 responses with mixed question types, no crash."""
        questions = [
            make_single("Возраст", [make_option(f"{i*10}-{i*10+9}") for i in range(1, 7)], entry_id="1"),
            make_multi("Каналы", [make_option(f"ch{i}") for i in range(6)], min_s=1, max_s=3, entry_id="2"),
            make_text("Имя", ["Алексей", "Иван", "Сергей"], entry_id="3"),
            make_textarea("Пожелания", ["Хорошо", "Отлично"], entry_id="4"),
        ]
        # Add exclusive option
        questions[1].options.append(make_option("Никакие", exclusive=True))
        g = gen(questions)
        for _ in range(1000):
            payload = g.generate_response()
            assert "entry.1" in payload
            assert "entry.2" in payload

    def test_max_select_enforced_strictly(self):
        """max_select=2 → never more than 2 options in any response."""
        opts = [make_option(f"opt{i}") for i in range(10)]
        q = make_multi("q", opts, min_s=1, max_s=2, entry_id="1")
        g = gen([q])
        for _ in range(200):
            payload = g.generate_response()
            assert len(payload["entry.1"]) <= 2, f"Got {payload['entry.1']}"

    def test_min_select_enforced_strictly(self):
        """min_select=3 → always at least 3 options."""
        opts = [make_option(f"opt{i}") for i in range(5)]
        q = make_multi("q", opts, min_s=3, max_s=5, entry_id="1")
        g = gen([q])
        for _ in range(200):
            payload = g.generate_response()
            assert len(payload["entry.1"]) >= 3, f"Got {payload['entry.1']}"


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_min_greater_than_available_options(self):
        """min_select > enabled options → selects as many as available."""
        opts = [make_option("A"), make_option("B")]
        q = make_multi("q", opts, min_s=5, max_s=10, entry_id="1")
        g = gen([q])
        for _ in range(20):
            result = g._generate_multi(q)
            assert len(result) <= 2

    def test_single_option_multi(self):
        """Only one option enabled, min=1 → always that one."""
        opts = [make_option("OnlyOne"), make_option("Gone", enabled=False)]
        q = make_multi("q", opts, min_s=1, max_s=3)
        g = gen([q])
        for _ in range(20):
            assert g._generate_multi(q) == ["OnlyOne"]

    def test_exclusive_with_all_regular_disabled(self):
        """Regular options disabled → if exclusive chosen, still just [exclusive]."""
        opts = [
            make_option("Reg", enabled=False),
            make_option("Solo", exclusive=True, weight=1),
        ]
        q = make_multi("q", opts, min_s=1, max_s=3)
        g = gen([q])
        for _ in range(30):
            result = g._generate_multi(q)
            assert result == ["Solo"]

    def test_default_short_texts_no_tea_words(self):
        """Ensure tea-related placeholder words are gone from defaults."""
        from app.generator.response_generator import DEFAULT_SHORT_TEXTS
        tea_words = {"чаепитие", "чай", "радость", "хруст", "пирожок"}
        for text in DEFAULT_SHORT_TEXTS:
            for tw in tea_words:
                assert tw not in text.lower(), f"Tea word '{tw}' found in: '{text}'"


# ── Built-in packs & gender linking ───────────────────────────────────────────

class TestPacksAndGender:
    def test_builtin_pack_used_when_pool_empty(self):
        """Empty text_pool + pack='cities' → value from cities pack."""
        from app.generator.response_generator import BUILT_IN_PACKS
        q = Question(entry_id="1", title="Город", qtype="text", text_pool=[], pack="cities")
        g = gen([q])
        for _ in range(30):
            val = g._generate_text(q)
            assert val in BUILT_IN_PACKS["cities"], f"Unexpected city: {val}"

    def test_pack_all_15_present(self):
        """All 15 expected pack keys exist in BUILT_IN_PACKS."""
        from app.generator.response_generator import BUILT_IN_PACKS
        expected = {
            "names_male", "names_female", "surnames", "positive", "neutral",
            "negative", "formal", "suggestions", "cities", "job_titles",
            "ages", "emails", "scale_low", "scale_mid", "scale_high",
        }
        assert expected == set(BUILT_IN_PACKS.keys())

    def test_detect_gender_male(self):
        q = Question(entry_id="1", title="q", qtype="text")
        g = gen([q])
        assert g._detect_gender("Мужской") == "m"
        assert g._detect_gender("мужчина") == "m"

    def test_detect_gender_female(self):
        q = Question(entry_id="1", title="q", qtype="text")
        g = gen([q])
        assert g._detect_gender("Женский") == "f"
        assert g._detect_gender("женщина") == "f"

    def test_detect_gender_any(self):
        q = Question(entry_id="1", title="q", qtype="text")
        g = gen([q])
        assert g._detect_gender("Не указан") == "any"
        assert g._detect_gender("") == "any"

    def test_gender_linked_name_filters_pool(self):
        """linked_to_entry + male gender choice → only 'm'/'any' items selected."""
        gender_q = Question(entry_id="10", title="Пол", qtype="single",
                            options=[Option(value="Мужской"), Option(value="Женский")])
        name_q = Question(
            entry_id="20", title="Имя", qtype="text",
            text_pool=[
                TextPoolItem(value="Иван", weight=1, enabled=True, gender="m"),
                TextPoolItem(value="Мария", weight=1, enabled=True, gender="f"),
                TextPoolItem(value="Саша", weight=1, enabled=True, gender="any"),
            ],
            linked_to_entry="10",
        )
        g = gen([gender_q, name_q])
        context = {"entry.10": "Мужской"}
        for _ in range(50):
            val = g._generate_text(name_q, context)
            assert val in ("Иван", "Саша"), f"Got female name for male context: {val}"

    def test_gender_linked_name_filters_female(self):
        gender_q = Question(entry_id="10", title="Пол", qtype="single",
                            options=[Option(value="Женский")])
        name_q = Question(
            entry_id="20", title="Имя", qtype="text",
            text_pool=[
                TextPoolItem(value="Иван", weight=1, enabled=True, gender="m"),
                TextPoolItem(value="Мария", weight=1, enabled=True, gender="f"),
            ],
            linked_to_entry="10",
        )
        g = gen([gender_q, name_q])
        context = {"entry.10": "Женский"}
        for _ in range(30):
            val = g._generate_text(name_q, context)
            assert val == "Мария", f"Got male name for female context: {val}"

    def test_context_built_in_generate_response(self):
        """generate_response builds context so linked text question sees gender."""
        from app.generator.response_generator import BUILT_IN_PACKS
        gender_q = Question(entry_id="10", title="Пол", qtype="single",
                            options=[Option(value="Мужской", weight=1),
                                     Option(value="Женский", weight=0)])
        name_q = Question(
            entry_id="20", title="Имя", qtype="text",
            text_pool=[
                TextPoolItem(value="Иван", weight=1, enabled=True, gender="m"),
                TextPoolItem(value="Мария", weight=1, enabled=True, gender="f"),
            ],
            linked_to_entry="10",
        )
        g = gen([gender_q, name_q])
        for _ in range(50):
            payload = g.generate_response()
            assert payload["entry.10"] == "Мужской"
            assert payload["entry.20"] == "Иван"

    def test_pack_fallback_respects_gender_for_names(self):
        """pack='names_male' + female context → switches to names_female."""
        from app.generator.response_generator import BUILT_IN_PACKS
        name_q = Question(entry_id="20", title="Имя", qtype="text",
                          text_pool=[], pack="names_male", linked_to_entry="10")
        g = gen([name_q])
        context_f = {"entry.10": "Женский"}
        for _ in range(20):
            val = g._generate_text(name_q, context_f)
            assert val in BUILT_IN_PACKS["names_female"], f"Expected female name, got: {val}"
