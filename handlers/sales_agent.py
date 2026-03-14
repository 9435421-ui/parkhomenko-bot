"""
ИИ-Продавец (Sales Agent) — 5-шаговый скрипт продаж для Антона.

Алгоритм общения:
1. Приветствие + Квалификация (квартира/коммерция, район, что менять)
2. Продажа ценности (бесплатный разбор плана на риски)
3. Захват документа (фото БТИ или эскиз)
4. Презентация УТП (прозрачность через бота 24/7, оплата по факту)
5. Дожим → переход к квизу

Интеграция: Автоматически запускается при обнаружении лида в комментариях.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import db
from config import VK_QUIZ_LINK

logger = logging.getLogger(__name__)


class SalesStates(StatesGroup):
    """Состояния 5-шагового скрипта продаж"""
    step1_qualification = State()      # Шаг 1: Приветствие + Квалификация
    step2_value_prop = State()         # Шаг 2: Продажа ценности
    step3_document_capture = State()   # Шаг 3: Захват документа
    step4_utp = State()                # Шаг 4: УТП и снятие возражений
    step5_quiz_transition = State()    # Шаг 5: Переход к квизу


# === ШАБЛОНЫ СООБЩЕНИЙ (5 шагов) ===

STEP1_GREETING_TEMPLATE = (
    "Здравствуйте! Я Антон, ИИ-помощник эксперта Юлии Пархоменко (компания TERION). "
    "Увидел ваш вопрос по поводу {keyword}. "
    "Подскажите, вы планируете перепланировку в жилой квартире или это коммерческое помещение?"
)

STEP2_VALUE_PROP_RESIDENTIAL = (
    "Понял вас. Чтобы не допустить юридических ошибок, которые потом сложно и дорого исправлять, "
    "Юлия предлагает сделать бесплатный разбор вашего плана. "
    "Мы проверим его на технические риски и скажем точно: можно ли это узаконить в Москве "
    "по текущим нормам 2026 года."
)

STEP2_VALUE_PROP_COMMERCIAL = (
    "Понял, коммерческое помещение. Для коммерции в Москве действуют другие нормы перепланировки "
    "(СанПиН, требования к входам, пожарная безопасность). "
    "Юлия предлагает бесплатный разбор вашего плана с учётом всех норм для коммерции. "
    "Это поможет избежать дорогостоящих ошибок при согласовании."
)

STEP3_DOCUMENT_CAPTURE = (
    "Для такого разбора мне понадобится фото или скан плана БТИ (можно в черных линиях) "
    "или просто ваш эскиз «как хочется сделать». "
    "Можете прислать файл прямо сюда? Юлия посмотрит его и я вернусь к вам с обратной связью."
)

STEP4_UTP = (
    "Мы в TERION работаем официально. Главное удобство — наш бот-монитор: "
    "вы будете видеть каждый шаг по вашему делу в режиме 24/7. "
    "И главное — оплата у нас поэтапная, по факту выполненных работ. "
    "Никаких «котов в мешке»."
)

STEP5_QUIZ_TRANSITION = (
    "План получил, передаю эксперту! Чтобы я мог подготовить для вас точный расчёт "
    "по срокам и этапам, ответьте, пожалуйста, на 7 коротких вопросов в нашем квизе: "
    "{quiz_link}. Это займёт 2 минуты."
)

REMINDER_24H = (
    "Добрый день! Удалось найти план БТИ? Наш эксперт готов его посмотреть "
    "и ответить на ваши вопросы."
)

REMINDER_3DAYS = (
    "Добрый день! Если у вас всё ещё есть вопросы по перепланировке, "
    "я готов помочь. Можете прислать план или просто описать, что хотите изменить."
)


class SalesAgent:
    """ИИ-Продавец: управление 5-шаговым скриптом продаж"""
    
    def __init__(self):
        self.quiz_link = VK_QUIZ_LINK
    
    async def start_sales_flow(
        self,
        user_id: int,
        source_type: str,  # "telegram" или "vk"
        source_id: str,
        post_id: str,
        keyword: str,
        context: str = ""
    ) -> Dict:
        """
        Запускает скрипт продаж для нового лида.
        
        Returns:
            {
                "step": 1,
                "message": "текст сообщения для отправки",
                "next_step": "step1_qualification"
            }
        """
        # Сохраняем контекст лида в БД
        lead_data = {
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "post_id": post_id,
            "keyword": keyword,
            "context": context,
            "sales_step": 1,
            "sales_started_at": datetime.now(),
            "last_interaction_at": datetime.now(),
        }
        
        # Проверяем, есть ли уже активный диалог с этим пользователем
        existing = await db.get_sales_conversation(user_id, source_type, source_id, post_id)
        if existing:
            # Возобновляем с того шага, где остановились
            current_step = existing.get("sales_step", 1)
            return await self._get_step_message(current_step, existing)
        
        # Создаём новую запись
        conversation_id = await db.save_sales_conversation(lead_data)
        
        # Шаг 1: Приветствие + Квалификация
        message = STEP1_GREETING_TEMPLATE.format(keyword=keyword)
        return {
            "step": 1,
            "message": message,
            "next_step": "step1_qualification",
            "conversation_id": conversation_id,
        }
    
    async def process_user_response(
        self,
        user_id: int,
        source_type: str,
        source_id: str,
        post_id: str,
        user_message: str
    ) -> Optional[Dict]:
        """
        Обрабатывает ответ пользователя и переводит на следующий шаг.
        
        Returns:
            {
                "step": 2,
                "message": "текст следующего шага",
                "next_step": "step2_value_prop",
                "completed": False
            }
            или None, если нужно пропустить шаги (клиент просит квиз)
        """
        conversation = await db.get_sales_conversation(user_id, source_type, source_id, post_id)
        if not conversation:
            logger.warning(f"Conversation not found for user {user_id}")
            return None
        
        current_step = conversation.get("sales_step", 1)
        user_msg_lower = user_message.lower()
        
        # Проверка: клиент просит квиз сразу → пропускаем шаги 2-4
        if any(phrase in user_msg_lower for phrase in ["квиз", "анкет", "заполнить", "опрос", "вопросы"]):
            return await self._skip_to_quiz(conversation)
        
        # Обработка по шагам
        if current_step == 1:
            # Шаг 1: Определяем тип объекта (квартира/коммерция)
            is_commercial = any(word in user_msg_lower for word in [
                "коммерц", "нежил", "офис", "кафе", "магазин", "салон"
            ])
            await db.update_sales_conversation(
                conversation["id"],
                sales_step=2,
                object_type="Коммерция" if is_commercial else "Квартира",
                last_interaction_at=datetime.now(),
            )
            return await self._get_step_message(2, {**conversation, "object_type": "Коммерция" if is_commercial else "Квартира"})
        
        elif current_step == 2:
            # Шаг 2: Переходим к запросу документа
            await db.update_sales_conversation(
                conversation["id"],
                sales_step=3,
                last_interaction_at=datetime.now(),
            )
            return await self._get_step_message(3, conversation)
        
        elif current_step == 3:
            # Шаг 3: Проверяем, прислал ли документ
            has_document = any(word in user_msg_lower for word in [
                "план", "бти", "эскиз", "фото", "скан", "прислал", "отправл"
            ]) or user_message.startswith("http") or "file" in user_msg_lower
            
            if has_document:
                # Документ получен → переходим к УТП
                await db.update_sales_conversation(
                    conversation["id"],
                    sales_step=4,
                    document_received=True,
                    last_interaction_at=datetime.now(),
                )
                return await self._get_step_message(4, conversation)
            else:
                # Документ не получен → мягко напоминаем
                return {
                    "step": 3,
                    "message": (
                        "Для точного разбора нужен план БТИ или эскиз. "
                        "Можете прислать фото или описать подробнее, что хотите изменить?"
                    ),
                    "next_step": "step3_document_capture",
                    "completed": False,
                }
        
        elif current_step == 4:
            # Шаг 4: Переходим к квизу
            await db.update_sales_conversation(
                conversation["id"],
                sales_step=5,
                last_interaction_at=datetime.now(),
            )
            return await self._get_step_message(5, conversation)
        
        elif current_step == 5:
            # Шаг 5: Квиз уже предложен, можно завершить
            await db.update_sales_conversation(
                conversation["id"],
                sales_step=6,  # Завершено
                completed=True,
                last_interaction_at=datetime.now(),
            )
            return {
                "step": 6,
                "message": "Отлично! Жду ваших ответов в квизе. Если будут вопросы — пишите!",
                "completed": True,
            }
        
        return None
    
    async def _get_step_message(self, step: int, conversation: Dict) -> Dict:
        """Возвращает текст сообщения для указанного шага"""
        object_type = conversation.get("object_type", "Квартира")
        
        if step == 1:
            keyword = conversation.get("keyword", "перепланировки")
            return {
                "step": 1,
                "message": STEP1_GREETING_TEMPLATE.format(keyword=keyword),
                "next_step": "step1_qualification",
            }
        elif step == 2:
            message = STEP2_VALUE_PROP_COMMERCIAL if object_type == "Коммерция" else STEP2_VALUE_PROP_RESIDENTIAL
            return {
                "step": 2,
                "message": message,
                "next_step": "step2_value_prop",
            }
        elif step == 3:
            return {
                "step": 3,
                "message": STEP3_DOCUMENT_CAPTURE,
                "next_step": "step3_document_capture",
            }
        elif step == 4:
            return {
                "step": 4,
                "message": STEP4_UTP,
                "next_step": "step4_utp",
            }
        elif step == 5:
            return {
                "step": 5,
                "message": STEP5_QUIZ_TRANSITION.format(quiz_link=self.quiz_link),
                "next_step": "step5_quiz_transition",
            }
        return None
    
    async def _skip_to_quiz(self, conversation: Dict) -> Dict:
        """Пропускает шаги 2-4 и сразу переходит к квизу"""
        await db.update_sales_conversation(
            conversation["id"],
            sales_step=5,
            skipped_steps="2,3,4",
            last_interaction_at=datetime.now(),
        )
        return {
            "step": 5,
            "message": STEP5_QUIZ_TRANSITION.format(quiz_link=self.quiz_link),
            "next_step": "step5_quiz_transition",
            "skipped": True,
        }
    
    async def send_reminder(self, conversation: Dict, reminder_type: str = "24h") -> Optional[str]:
        """
        Отправляет напоминание клиенту (24ч или 3 дня).
        
        Returns:
            Текст напоминания или None, если лимит попыток исчерпан
        """
        attempts = conversation.get("reminder_attempts", 0)
        
        if attempts >= 2:
            # Лимит исчерпан → помечаем как "холодный"
            await db.update_sales_conversation(
                conversation["id"],
                status="cold",
                last_interaction_at=datetime.now(),
            )
            return None
        
        message = REMINDER_24H if reminder_type == "24h" else REMINDER_3DAYS
        
        await db.update_sales_conversation(
            conversation["id"],
            reminder_attempts=attempts + 1,
            last_reminder_at=datetime.now(),
            last_interaction_at=datetime.now(),
        )
        
        return message


# Глобальный экземпляр
sales_agent = SalesAgent()
