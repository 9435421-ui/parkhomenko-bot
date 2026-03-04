import logging
import os
import re
from utils import router_ai

logger = logging.getLogger(__name__)

# =============================================================================
# ПРИОРИТЕТНЫЕ ЖК — «Открытая охота»
# Если сообщение упоминает любой из этих ЖК И содержит проблемный контекст
# (закон, штраф, ремонт, согласование) — немедленно горячий лид без ожидания ИИ.
# =============================================================================

# =============================================================================
# ПРИОРИТЕТНЫЕ ЖК (9 ЖК из ТЗ)
# Если сообщение упоминает любой из этих ЖК — лид помечается как ⭐ ПРИОРИТЕТНЫЙ
# =============================================================================
PRIORITY_ZHK = [
    "зиларт",
    "символ",
    "сердце столицы",
    "династия",
    "пресня сити",
    "некрасовка",
    "люблинский парк",
    "фили град",
    "волжский парк",
    "саларьево",
    "митино",
    "сколково",
    "братеево",
]

# =============================================================================
# TRIGGER WORDS — Ключевые фразы для определения горячих лидов
# Если в тексте есть эти фразы — лид автоматически помечается как горячий
# =============================================================================
TRIGGER_WORDS = [
    # Критические запросы
    "можно ли сносить",
    "можно сносить",
    "где заказать проект",
    "заказать проект перепланировки",
    "штраф бти",
    "штраф от бти",
    "красные линии",
    "красная линия",
    "объединение кухни",
    "объединить кухню",
    "перенос мокрой зоны",
    "перенести мокрую зону",
    "снос стены",
    "сносить стену",
    "узаконить перепланировку",
    "как узаконить",
    "согласовать перепланировку",
    "нужен проект",
    "кто делал проект",
    "кто согласовывал",
    # Расширенные паттерны для реальных лидов
    "нужен проект перепланировки",
    "узаконить перепланировку в новостройке",
    "объединить кухню и комнату",
    "перенос мокрой зоны",
    "разрешение на перепланировку",
    "узаконить перепланировку без проекта",
    "сделали проем в несущей стене",
    "несущая стена",
    "проектировщик",
    "согласование перепланировки",
    "жилищная инспекция",
    "смежная стена",
    "проектная организация",
    "акты скрытых работ",
    "к кому обратиться",
    "сколько стоит",
    "сделаете",
    "делали ли кто-то",
    "подскажите компанию",
    "есть контакт",
    "ищу исполнителя",
    "готов заплатить",
    "срочно",
]

# Контекст проблемы: правовые вопросы и ремонт/перепланировка
ZHK_PROBLEM_KEYWORDS = [
    "перепланировк",
    "согласовани",
    "узакони",
    "предписание",
    "мжи",
    "штраф",
    "инспекция",
    "суд",
    "проект",
    "снос стен",
    "снести стену",
    "мокрая зона",
    "объединить",
    "объединение",
    "санузел",
    "бти",
    "акт скрытых",
    "сро",
    "переустройство",
    "реконструкция",
    "кто делал",
    "кто согласовывал",
    "помогите",
    "посоветуйте",
    "как оформить",
]


# Гео-маркеры для фильтрации (только Москва и МО)
GEO_MOSCOW_MARKERS = [
    "москва", "московск", "мск", "мкд", "московская область", "мо",
    "химки", "красногорск", "мытищи", "балашиха", "люберцы",
    "подмосковье", "новая москва", "нао", "зао", "сао", "свао", "вао", "ювао", "юао", "сзао", "цао",
    "юго-восток", "юго-запад", "северо-восток", "северо-запад",
]


def _is_moscow_geo(text: str, source_name: str = "") -> bool:
    """
    Проверяет, относится ли пост к Москве или Московской области.
    Фильтрует лиды из других регионов.
    
    Returns:
        True если гео = Москва/МО, False если другой регион
    """
    if not text and not source_name:
        return True  # Если нет данных — пропускаем (не фильтруем)
    
    combined = f"{text} {source_name}".lower()
    
    # Проверяем маркеры Москвы/МО
    has_moscow = any(marker in combined for marker in GEO_MOSCOW_MARKERS)
    
    # Проверяем маркеры других регионов (отсеиваем)
    other_regions = [
        "санкт-петербург", "спб", "питер", "ленинград",
        "казань", "нижний новгород", "екатеринбург", "новосибирск",
        "ростов", "краснодар", "сочи", "крым",
    ]
    has_other_region = any(region in combined for region in other_regions)
    
    # Если есть маркер другого региона И нет маркера Москвы — отсеиваем
    if has_other_region and not has_moscow:
        return False
    
    # Если есть маркер Москвы — пропускаем
    if has_moscow:
        return True
    
    # Если нет явных маркеров — пропускаем (не фильтруем строго)
    return True


def _detect_priority_zhk_hot(text: str) -> tuple[bool, str]:
    """
    Возвращает (True, название_жк) если в тексте упоминается приоритетный ЖК
    вместе с проблемным контекстом. Быстрая проверка без ИИ — используется
    как немедленный триггер горячего лида.
    """
    if not text:
        return False, ""
    t = text.lower()
    found_zhk = next((zhk for zhk in PRIORITY_ZHK if zhk in t), None)
    if not found_zhk:
        return False, ""
    has_problem = any(kw in t for kw in ZHK_PROBLEM_KEYWORDS)
    if has_problem:
        return True, found_zhk
    return False, ""


class LeadAnalyzer:
    """AI-анализ постов на основе Базы Знаний 'Друга-эксперта'"""

    def __init__(self):
        self.kb_path = "knowledge_base/sales/hunter_manual.md"

    async def analyze_post(self, text: str, source_name: str = "") -> dict:
        """
        Анализирует пост, сверяясь с базой знаний продаж.
        Возвращает dict с оценкой (1-10) и стадией боли (ST-1…ST-4).

        Гео-фильтрация: отсеивает лиды из регионов, кроме Москвы и МО.
        
        Быстрый путь: если упомянут приоритетный ЖК + проблемный контекст —
        немедленно возвращаем ST-4 без ожидания ИИ.
        """
        if text is None:
            text = ""
        text = (text or "").strip()

        if len(text) < 10:
            return {"priority_score": 0, "pain_stage": "ST-1", "is_lead": False}
        
        # ── ФИЛЬТР ПО ДЛИНЕ: Статьи (> 500 символов) — это не лид ────────────────
        if len(text) > 500:
            logger.debug(f"🚫 Фильтр длины: сообщение слишком длинное ({len(text)} символов) — пропущено (это статья, не лид)")
            return {"priority_score": 0, "pain_stage": "ST-1", "is_lead": False, "length_filtered": True}
        
        # ── ФИЛЬТР СПАМА И РЕКЛАМЫ: Отсеиваем рекламу других бригад ─────────────
        spam_patterns = [
            r"\+?\d{10,}",  # Номера телефонов (10+ цифр)
            r"звоните|звон.*те|тел\.|телефон",  # Призывы звонить
            r"пишите в лс|напишите в лс|в личку|в директ",  # Призывы писать в ЛС
            r"наша бригада|наша команда|мы делаем|мы выполняем",  # Реклама услуг
            r"портфолио|примеры работ|смотрите работы",  # Ссылки на портфолио
            r"для сметы|для консультации|для расчета",  # Призывы к действию без вопроса
        ]
        
        text_lower = text.lower()
        is_spam = False
        for pattern in spam_patterns:
            if re.search(pattern, text_lower):
                is_spam = True
                logger.debug(f"🚫 Фильтр спама: обнаружен паттерн '{pattern}' — пропущено")
                break
        
        # Проверка: только эмодзи или приветствия без контекста
        text_without_emoji = re.sub(r'[^\w\s]', '', text_lower).strip()
        if len(text_without_emoji) < 10 and not any(kw in text_lower for kw in ["перепланировк", "согласован", "узакони", "бти", "мжи"]):
            is_spam = True
            logger.debug("🚫 Фильтр спама: сообщение состоит только из эмодзи/приветствий без контекста — пропущено")
        
        if is_spam:
            return {"priority_score": 0, "pain_stage": "ST-1", "is_lead": False, "spam_filtered": True}
        
        # ── ФИЛЬТР ПО ТИПУ КОНТЕНТА: Только вопросы и запросы помощи ─────────────
        QUESTION_KEYWORDS = [
            "посоветуйте", "подскажите", "подскажите пожалуйста",
            "сколько стоит", "сколько будет стоить", "какая цена",
            "можно ли", "можно", "можно?", "можно?",
            "как", "как сделать", "как узаконить", "как согласовать",
            "где", "где заказать", "где сделать", "где купить",
            "кто", "кто делал", "кто делал проект", "кто согласовывал",
            "что", "что нужно", "что требуется", "что делать",
            "?", "?", "?",  # Вопросительные знаки
        ]
        
        has_question_mark = "?" in text
        has_question_keywords = any(keyword in text_lower for keyword in QUESTION_KEYWORDS)
        
        if not (has_question_mark or has_question_keywords):
            logger.debug("🚫 Фильтр типа контента: нет вопросов или запросов помощи — пропущено")
            return {"priority_score": 0, "pain_stage": "ST-1", "is_lead": False, "content_type_filtered": True}
        
        # ── ПРИОРИТЕТНЫЕ ЖК: Проверяем, является ли источник приоритетным ЖК ────────────
        # Если источник — приоритетный ЖК из БД (is_high_priority), пропускаем гео-фильтр
        is_priority_zhk_source = False
        if source_name:
            source_lower = source_name.lower()
            # Проверяем, содержит ли название источника приоритетный ЖК
            for zhk in PRIORITY_ZHK:
                if zhk in source_lower:
                    is_priority_zhk_source = True
                    logger.debug(f"⭐ Источник является приоритетным ЖК: {source_name}")
                    break
        
        # Гео-фильтрация: отсеиваем лиды не из Москвы/МО (кроме приоритетных ЖК)
        if not is_priority_zhk_source and not _is_moscow_geo(text, source_name):
            logger.debug("🚫 Гео-фильтр: пост не из Москвы/МО и не из приоритетного ЖК — пропущен")
            return {"priority_score": 0, "pain_stage": "ST-1", "is_lead": False, "geo_filtered": True}

        result = {}

        # ── Проверка TRIGGER WORDS (горячие фразы) ──────────────────────────────
        found_triggers = [trigger for trigger in TRIGGER_WORDS if trigger in text_lower]
        
        # ── ПРИОРИТЕТНЫЕ КЛЮЧЕВЫЕ СЛОВА: максимальный boost для core-терминов ────
        PRIORITY_KEYWORDS = {
            "перепланировк": 2,  # +2 к priority_score
            "узакони": 2,        # +2 к priority_score
            "бти": 2,            # +2 к priority_score
            "проект проема": 2,  # +2 к priority_score
            "проект перепланировки": 2,  # +2 к priority_score
        }
        
        keyword_boost = 0
        found_priority_keywords = []
        for keyword, boost in PRIORITY_KEYWORDS.items():
            if keyword in text_lower:
                keyword_boost += boost
                found_priority_keywords.append(keyword)
        
        if found_triggers:
            base_score = 8
            # Применяем boost от приоритетных ключевых слов
            final_score = min(10, base_score + keyword_boost)
            logger.info(f"🔥 Trigger words обнаружены: {found_triggers} → ГОРЯЧИЙ ЛИД (score: {final_score}, boost: +{keyword_boost} от {found_priority_keywords})")
            result.update({
                "priority_score": final_score,
                "pain_stage": "ST-3",  # Высокая стадия боли
                "is_lead": True,
                "trigger_words": found_triggers,
                "priority_keywords": found_priority_keywords,
                "keyword_boost": keyword_boost,
                "justification": f"Обнаружены ключевые фразы: {', '.join(found_triggers)}" + (f" + boost от приоритетных слов: {', '.join(found_priority_keywords)}" if found_priority_keywords else ""),
            })

        # ── Проверка приоритетных ЖК (для пометки ⭐ ПРИОРИТЕТНЫЙ) ───────────────
        found_zhk = next((zhk for zhk in PRIORITY_ZHK if zhk in text_lower), None)
        if found_zhk:
            result["is_priority_zhk"] = True
            result["zhk_name"] = found_zhk
            result["priority_marker"] = "⭐ ПРИОРИТЕТНЫЙ"
            logger.info(f"⭐ Приоритетный ЖК обнаружен: {found_zhk}")

        # ── Быстрый триггер: приоритетный ЖК + проблема ─────────────────────
        is_zhk_hot, zhk_name = _detect_priority_zhk_hot(text)
        if is_zhk_hot:
            logger.info(
                "🚨 Быстрый триггер: ЖК '%s' + проблемный контекст → ГОРЯЧИЙ ЛИД ST-4",
                zhk_name,
            )
            return {
                "priority_score": 9,
                "pain_stage": "ST-4",
                "is_lead": True,
                "justification": f"Приоритетный ЖК '{zhk_name}' упомянут в контексте правовых/ремонтных проблем",
                "zhk_name": zhk_name,
                "is_priority_zhk": True,
                "priority_marker": "⭐ ПРИОРИТЕТНЫЙ",
            }
        
        # Если уже есть результат от trigger words — возвращаем его
        if result.get("is_lead"):
            return result

        logger.info("🧠 LeadAnalyzer: глубокий анализ через Базу Знаний...")

        # ── Читаем инструкцию ────────────────────────────────────────────────
        manual = ""
        if os.path.exists(self.kb_path):
            with open(self.kb_path, "r", encoding="utf-8") as f:
                manual = f.read()

        priority_zhk_hint = (
            "Особое внимание: если в сообщении упоминается один из ЖК — "
            "Зиларт, Символ, Сердце Столицы, Династия, Пресня Сити — "
            "и речь идёт о проблемах с законом, ремонтом или согласованием, "
            "автоматически присваивай pain_stage ST-4 и priority_score не ниже 8."
        )

        system_prompt = f"""
Ты — эксперт по анализу лидов для компании TERION (согласование перепланировок в Москве).

Инструкция для оценки: {manual}

{priority_zhk_hint}

КРИТИЧЕСКИ ВАЖНО — ФИЛЬТРАЦИЯ СПАМА И РЕКЛАМЫ:
1. Если сообщение содержит явную рекламу услуг (номера телефонов для заказа ремонта, ссылки на портфолио, призывы "пишите в ЛС для сметы", "звоните для консультации", "наша бригада"), присваивай priority_score=0 и помечай как SPAM (is_lead=false).
2. Игнорируй сообщения, состоящие только из эмодзи или приветствий без контекста недвижимости/перепланировок.
3. Если сообщение содержит только контакты (телефон, WhatsApp, Telegram) без вопроса о перепланировке — это спам (is_lead=false, priority_score=0).

Твоя задача:
Проанализируй сообщение и классифицируй его по шкале приоритета (1-10) и стадии боли:

СТАДИИ БОЛИ:
- ST-1 (Интерес): Просто интересуется теорией, общими вопросами. Нет срочности.
- ST-2 (Планирование): Собирается делать ремонт, ищет варианты, изучает возможности. Есть время на принятие решения.
- ST-3 (Актив): Уже делает ремонт, боится штрафов, нужен проект для согласования. Есть срочность.
- ST-4 (Критично): Получил предписание МЖИ, пришла инспекция, суд, блокировка сделки, штраф БТИ. КРИТИЧЕСКАЯ СИТУАЦИЯ.

ПРИОРИТЕТ (priority_score):
- 0: СПАМ/РЕКЛАМА (не лид)
- 1-10: Шкала приоритета.

ВАЖНО: Верни ответ ТОЛЬКО в формате JSON.
"""
        # Лимит системного промпта — 2500 символов
        if len(system_prompt) > 2500:
            logger.warning(f"⚠️ System prompt too long ({len(system_prompt)}), truncating...")
            system_prompt = system_prompt[:2500]

        user_prompt = f"""Текст сообщения из чата: "{text}"

Верни ответ в формате:
{{
    "priority_score": число от 0 до 10,
    "pain_stage": "ST-1" | "ST-2" | "ST-3" | "ST-4",
    "justification": "краткое пояснение",
    "is_lead": true | false
}}"""

        try:
            # Основная модель — gpt-4o-mini
            response = await router_ai.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                model="gpt-4o-mini"
            )
            
            # ── ОБРАБОТКА ОШИБКИ 401 (Unauthorized) ──────────────────────────────────
            # Проверяем, если response содержит информацию об ошибке 401
            if response is None:
                # Router AI вернул None - возможно, ошибка авторизации при fallback на Yandex
                logger.warning("⚠️ Router AI вернул None - возможно, проблема с авторизацией")
                # Продолжаем с дефолтным результатом
                response = ""
            elif isinstance(response, str):
                response_upper = response.upper()
                if any(keyword in response_upper for keyword in ["401", "UNAUTHORIZED", "YANDEX_API_KEY", "AUTHENTICATION"]):
                    logger.error("=" * 60)
                    logger.error("❌ ОШИБКА АВТОРИЗАЦИИ YANDEX API (401 Unauthorized)")
                    logger.error("")
                    logger.error("💡 ИНСТРУКЦИЯ: Обновите YANDEX_API_KEY в .env")
                    logger.error("")
                    logger.error("Проверьте:")
                    logger.error("  1. YANDEX_API_KEY установлен в .env")
                    logger.error("  2. Ключ действителен и не истек")
                    logger.error("  3. FOLDER_ID указан корректно")
                    logger.error("  4. У ключа есть права на использование YandexGPT API")
                    logger.error("=" * 60)
                    # Возвращаем дефолтный результат вместо падения
                    return {
                        "priority_score": 3,
                        "pain_stage": "ST-1",
                        "is_lead": False,
                        "justification": "Ошибка авторизации Yandex API - требуется обновление YANDEX_API_KEY",
                        "error": "yandex_401"
                    }
            
            if not str(response).strip():
                raise ValueError("Router AI вернул пустой ответ")

            import json
            # Ищем JSON в ответе (может быть обёрнут в markdown или текст)
            match = re.search(r"\{[^{}]*\"priority_score\"[^{}]*\}", response, re.DOTALL)
            if not match:
                # Пробуем найти любой JSON объект
                match = re.search(r"\{.*\}", response, re.DOTALL)
            
            if not match:
                logger.error(f"❌ Не удалось найти JSON в ответе Router AI: {response[:200]}")
                raise ValueError(f"Не удалось найти JSON в ответе: {response[:200]}")

            json_str = match.group(0)
            # Очищаем от markdown code blocks если есть
            json_str = re.sub(r"```json\s*", "", json_str)
            json_str = re.sub(r"```\s*", "", json_str)
            
            data = json.loads(json_str)
            
            # Валидация данных
            priority_score = int(data.get("priority_score", 0))
            pain_stage = data.get("pain_stage", "ST-1")
            
            # Ограничиваем priority_score в диапазоне 1-10
            priority_score = max(1, min(10, priority_score))
            
            # Валидация pain_stage
            if pain_stage not in ["ST-1", "ST-2", "ST-3", "ST-4"]:
                # Определяем по priority_score если pain_stage некорректен
                if priority_score <= 3:
                    pain_stage = "ST-1"
                elif priority_score <= 5:
                    pain_stage = "ST-2"
                elif priority_score <= 7:
                    pain_stage = "ST-3"
                else:
                    pain_stage = "ST-4"
            
            # ── ПРИМЕНЯЕМ BOOST ОТ ПРИОРИТЕТНЫХ КЛЮЧЕВЫХ СЛОВ ────────────────────
            # Проверяем наличие приоритетных ключевых слов в тексте
            PRIORITY_KEYWORDS = {
                "перепланировк": 2,  # +2 к priority_score
                "узакони": 2,        # +2 к priority_score
                "бти": 2,            # +2 к priority_score
                "проект проема": 2,  # +2 к priority_score
                "проект перепланировки": 2,  # +2 к priority_score
            }
            
            keyword_boost = 0
            found_priority_keywords = []
            t_lower = text.lower()
            for keyword, boost in PRIORITY_KEYWORDS.items():
                if keyword in t_lower:
                    keyword_boost += boost
                    found_priority_keywords.append(keyword)
            
            # Применяем boost к priority_score (максимум 10)
            priority_score_with_boost = min(10, priority_score + keyword_boost)
            
            if keyword_boost > 0:
                logger.info(f"📈 Приоритетные ключевые слова обнаружены: {found_priority_keywords} → boost +{keyword_boost} (score: {priority_score} → {priority_score_with_boost})")
            
            data.update({
                "priority_score": priority_score_with_boost,
                "pain_stage": pain_stage,
                "is_lead": data.get("is_lead", priority_score_with_boost >= 5),
                "priority_keywords": found_priority_keywords if keyword_boost > 0 else None,
                "keyword_boost": keyword_boost if keyword_boost > 0 else None,
            })

            # Дополнительная проверка: если ИИ не заметил ЖК, но он есть — повышаем
            t_lower = text.lower()
            found_zhk_after = next((zhk for zhk in PRIORITY_ZHK if zhk in t_lower), None)
            if found_zhk_after and not data["is_lead"]:
                has_problem = any(kw in t_lower for kw in ZHK_PROBLEM_KEYWORDS)
                if has_problem:
                    data["priority_score"] = max(data.get("priority_score", 0), 8)
                    data["pain_stage"] = "ST-4"
                    data["is_lead"] = True
                    data["zhk_name"] = found_zhk_after
                    data["justification"] = (
                        data.get("justification", "")
                        + f" [Повышено: обнаружен приоритетный ЖК '{found_zhk_after}']"
                    )

            logger.info("🎯 Оценка лида: %s", data)
            return data

        except Exception as e:
            logger.error("❌ Ошибка анализатора: %s", e)
            # ── Fallback: ручной поиск по ключевым словам ───────────────────
            t_lower = text.lower() if text else ""

            # Приоритетный ЖК + проблема (повторная проверка на случай сбоя ИИ)
            is_zhk_hot_fb, zhk_name_fb = _detect_priority_zhk_hot(text)
            if is_zhk_hot_fb:
                return {
                    "priority_score": 9,
                    "pain_stage": "ST-4",
                    "is_lead": True,
                    "justification": f"Fallback: ЖК '{zhk_name_fb}' + проблемный контекст",
                    "zhk_name": zhk_name_fb,
                }

            triggers_critical = ["предписание", "суд", "инспекция", "мжи", "штраф"]
            if any(word in t_lower for word in triggers_critical):
                return {
                    "priority_score": 9,
                    "pain_stage": "ST-4",
                    "is_lead": True,
                    "justification": "Fallback: найдены критические ключевые слова",
                }

            triggers_med = ["мокрая зона", "узаконить", "перепланиров", "согласовани"]
            if any(word in t_lower for word in triggers_med):
                return {
                    "priority_score": 7,
                    "pain_stage": "ST-3",
                    "is_lead": True,
                    "justification": "Fallback: найдены технические ключевые слова",
                }

            return {
                "priority_score": 1,
                "pain_stage": "ST-1",
                "is_lead": False,
                "justification": "Fallback: низкий приоритет по умолчанию",
            }
