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

DEFAULT_SHORT_TEXTS = [
    "Всё устраивает",
    "Хорошо",
    "Нормально",
    "Доволен(а)",
    "Неплохо",
    "Без замечаний",
    "Всё в порядке",
    "Удовлетворительно",
    "Да",
    "Нет",
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

# ─── Built-in packs ───────────────────────────────────────────────────────────

BUILT_IN_PACKS: dict[str, list[str]] = {
    "names_male": [
        "Александр", "Алексей", "Андрей", "Антон", "Артём", "Борис", "Вадим",
        "Василий", "Виктор", "Владимир", "Владислав", "Геннадий", "Григорий",
        "Даниил", "Денис", "Дмитрий", "Евгений", "Иван", "Игорь", "Илья",
        "Кирилл", "Константин", "Максим", "Михаил", "Никита", "Николай",
        "Олег", "Павел", "Пётр", "Роман", "Руслан", "Сергей", "Степан",
        "Тимур", "Фёдор", "Юрий", "Ярослав",
    ],
    "names_female": [
        "Александра", "Алина", "Алиса", "Анастасия", "Анна", "Валентина",
        "Валерия", "Вера", "Виктория", "Галина", "Дарья", "Диана",
        "Екатерина", "Елена", "Елизавета", "Жанна", "Инна", "Ирина",
        "Карина", "Кристина", "Ксения", "Лариса", "Людмила", "Маргарита",
        "Марина", "Мария", "Надежда", "Наталья", "Нина", "Оксана",
        "Ольга", "Полина", "Светлана", "София", "Тамара", "Татьяна",
        "Юлия", "Яна",
    ],
    "surnames": [
        "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров",
        "Соколов", "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков",
        "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов",
        "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин",
        "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев",
    ],
    "positive": [
        "Отлично!", "Всё понравилось", "Очень доволен(а)", "Превзошло ожидания",
        "Рекомендую всем", "Замечательно!", "Супер!", "Очень здорово",
        "Буду пользоваться снова", "Всё на высшем уровне", "Великолепно!",
        "Лучше не бывает", "Прекрасный опыт", "Восхитительно",
        "Очень приятное впечатление",
    ],
    "neutral": [
        "Нормально", "Неплохо", "В целом устраивает", "Без замечаний",
        "Приемлемо", "Всё как обычно", "Стандартно", "Ничего особенного",
        "Сойдёт", "Можно и лучше", "Средний уровень", "Как и ожидалось",
        "Ни хорошо ни плохо", "Терпимо",
    ],
    "negative": [
        "Не очень понравилось", "Есть над чем работать", "Ожидал(а) большего",
        "Не лучший опыт", "Много минусов", "Разочарован(а)", "Не рекомендую",
        "Надо улучшать", "Слабо", "Оставляет желать лучшего",
        "Ниже ожиданий", "Есть серьёзные недостатки",
        "Нужно много доработок", "Плохое впечатление",
    ],
    "formal": [
        "Услуги соответствуют заявленным стандартам.",
        "Взаимодействие в рамках установленных требований.",
        "Качество на приемлемом уровне.",
        "Претензий к работе не имею.",
        "Соответствует заявленным характеристикам.",
        "Работа выполнена в установленные сроки.",
        "Уровень сервиса соответствует ожиданиям.",
        "Результат соответствует техническому заданию.",
        "Замечаний по качеству исполнения нет.",
        "Все обязательства выполнены в полном объёме.",
    ],
    "suggestions": [
        "Добавьте онлайн-оплату",
        "Хотелось бы больше акций и скидок",
        "Расширьте ассортимент товаров",
        "Улучшите навигацию на сайте",
        "Сделайте мобильное приложение",
        "Добавьте программу лояльности",
        "Хотелось бы скидки для постоянных клиентов",
        "Продлите часы работы",
        "Улучшите упаковку товаров",
        "Добавьте доставку в регионы",
        "Ускорьте обработку заказов",
        "Добавьте больше способов связи",
        "Хотелось бы больше отзывов на сайте",
        "Сделайте процесс оформления проще",
    ],
    "cities": [
        "Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск", "Казань",
        "Нижний Новгород", "Челябинск", "Красноярск", "Самара", "Уфа",
        "Ростов-на-Дону", "Омск", "Краснодар", "Воронеж", "Пермь",
        "Волгоград", "Саратов", "Тюмень", "Тольятти", "Ижевск",
        "Барнаул", "Иркутск", "Хабаровск", "Ярославль", "Владивосток",
        "Томск", "Оренбург", "Кемерово", "Новокузнецк", "Рязань",
    ],
    "job_titles": [
        "Менеджер", "Инженер", "Программист", "Бухгалтер", "Врач",
        "Учитель", "Директор", "Аналитик", "Дизайнер", "Юрист",
        "Маркетолог", "Продавец", "Логист", "HR-специалист", "Финансист",
        "Консультант", "Предприниматель", "Руководитель проекта",
        "Технолог", "Экономист", "Специалист по продажам", "Архитектор",
        "Психолог", "Системный администратор", "Переводчик",
    ],
    "ages": [
        "19", "21", "23", "24", "25", "26", "27", "28", "29", "30",
        "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
        "41", "42", "43", "44", "45", "47", "49", "51", "53", "55",
    ],
    "emails": [
        "user@mail.ru", "alex.petrov@gmail.com", "ivan.iv@yandex.ru",
        "maria.k@mail.ru", "dmitry.s@gmail.com", "natasha.v@yandex.ru",
        "andrey.m@mail.ru", "elena.b@gmail.com", "sergey.n@yandex.ru",
        "olga.zh@mail.ru", "maxim.k@gmail.com", "anna.s@yandex.ru",
        "nikolay.p@mail.ru", "svetlana.f@gmail.com", "roman.t@yandex.ru",
        "yulia.d@mail.ru", "igor.v@gmail.com", "katerina.m@yandex.ru",
        "pavel.o@mail.ru", "tatiana.l@gmail.com",
    ],
    "scale_low": [
        "Очень плохо", "Ужасный сервис", "Совсем не понравилось",
        "Крайне разочарован(а)", "Это провал", "Недопустимое качество",
        "Очень низкий уровень", "Ужасно, не рекомендую",
    ],
    "scale_mid": [
        "Средне", "Ни хорошо ни плохо", "Можно лучше",
        "Удовлетворительно", "Нейтрально", "Среднее впечатление",
        "Есть как плюсы, так и минусы", "Требует доработки",
    ],
    "scale_high": [
        "Хорошо", "Отлично", "Очень понравилось", "Замечательно",
        "Рекомендую", "Высокий уровень", "Превосходно", "Очень доволен(а)",
    ],
}

# Gender keywords for auto-detection from linked question value
_GENDER_M_KEYWORDS = ("мужск", "мужчин", " м ", "male", "муж")
_GENDER_F_KEYWORDS = ("женск", "женщин", " ж ", "female", "жен")


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

        raw_weights = self._apply_profile_weights(question)
        w_map = {o.value: w for o, w in zip(question.options, raw_weights) if o.enabled}

        # Split into exclusive (solo answers) and regular options
        excl = [(o, w_map[o.value]) for o in enabled if getattr(o, "exclusive", False)]
        reg  = [(o, w_map[o.value]) for o in enabled if not getattr(o, "exclusive", False)]

        excl_nz = [(o, w) for o, w in excl if w > 0]
        reg_nz  = [(o, w) for o, w in reg  if w > 0]

        # Fallback: if all weights are 0, treat enabled options as weight=1
        if not excl_nz and not reg_nz:
            reg_nz  = [(o, 1) for o, _ in reg]
            excl_nz = [(o, 1) for o, _ in excl]

        # Decide: exclusive option or regular multi-select?
        if excl_nz:
            total_excl = sum(w for _, w in excl_nz)
            total_reg  = sum(w for _, w in reg_nz)
            if random.random() < total_excl / (total_excl + total_reg):
                opts, ws = zip(*excl_nz)
                return [random.choices(list(opts), weights=list(ws), k=1)[0].value]

        if not reg_nz:
            return []

        # Regular multi-select: enforce min/max bounds
        min_k = max(1, question.min_select)
        max_k = max(min_k, question.max_select)
        pool  = list(reg_nz)
        k = random.randint(min(min_k, len(pool)), min(max_k, len(pool)))

        chosen: list[str] = []
        for _ in range(k):
            if not pool:
                break
            opts, ws = zip(*pool)
            sel = random.choices(list(opts), weights=list(ws), k=1)[0]
            chosen.append(sel.value)
            pool = [(o, w) for o, w in pool if o.value != sel.value]
        return chosen

    def _detect_gender(self, value: str) -> str:
        """Return 'm', 'f', or 'any' based on a gender question answer value."""
        v = value.lower()
        if any(k in v for k in _GENDER_M_KEYWORDS):
            return "m"
        if any(k in v for k in _GENDER_F_KEYWORDS):
            return "f"
        return "any"

    def _generate_text(self, question: Question, context: dict[str, str] | None = None) -> str:
        gender = "any"
        if context and question.linked_to_entry:
            linked_val = context.get(f"entry.{question.linked_to_entry}", "")
            if linked_val:
                gender = self._detect_gender(linked_val)

        pool_items = [i for i in (question.text_pool or []) if getattr(i, "enabled", True)]

        # Filter pool items by gender when a linked gender is known
        if pool_items and gender != "any":
            gendered = [i for i in pool_items if getattr(i, "gender", "any") in (gender, "any")]
            if gendered:
                pool_items = gendered

        if pool_items:
            usable = [(i, int(getattr(i, "weight", 1) or 0)) for i in pool_items]
            usable = [(i, w) for i, w in usable if w > 0]
            if usable:
                items, ws = zip(*usable)
                return random.choices(list(items), weights=list(ws), k=1)[0].value
            return random.choice(pool_items).value

        # Fall back to built-in pack
        pack_name = getattr(question, "pack", None)
        if pack_name and pack_name in BUILT_IN_PACKS:
            pack_items = BUILT_IN_PACKS[pack_name]
            # For name packs, apply gender filtering
            if pack_name == "names_male" and gender == "f":
                pack_items = BUILT_IN_PACKS.get("names_female", pack_items)
            elif pack_name == "names_female" and gender == "m":
                pack_items = BUILT_IN_PACKS.get("names_male", pack_items)
            return random.choice(pack_items)

        fallback = DEFAULT_LONG_TEXTS if question.qtype == "textarea" else DEFAULT_SHORT_TEXTS
        return random.choice(fallback)

    def generate_response(self) -> dict[str, Any]:
        """Generate one complete form response payload."""
        payload: dict[str, Any] = {}
        context: dict[str, str] = {}  # tracks single-answer values for gender linking

        for q in self.questions:
            if getattr(q, "enabled", True) is False:
                continue
            if not q.entry_id:
                continue
            try:
                if q.qtype in ("text", "textarea"):
                    if q.options:
                        val = random.choice(
                            [o.value for o in q.options if o.enabled] or DEFAULT_SHORT_TEXTS
                        )
                    else:
                        val = self._generate_text(q, context)
                    payload[f"entry.{q.entry_id}"] = val
                    context[f"entry.{q.entry_id}"] = val
                elif q.qtype == "single":
                    raw_weights = self._apply_profile_weights(q)
                    enabled_options = [o for o in q.options if o.enabled]
                    if not enabled_options or all(w == 0 for w in raw_weights):
                        continue
                    val = self._generate_single(q)
                    payload[f"entry.{q.entry_id}"] = val
                    context[f"entry.{q.entry_id}"] = val
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
