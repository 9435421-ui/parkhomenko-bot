<<<<<<< HEAD
"""
Middleware для обработки необработанных callback-запросов
Логирует нажатия на кнопки, которые не были обработаны ни одним хендлером
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject
=======
"""Middleware для логирования событий."""
import logging
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377

logger = logging.getLogger(__name__)


<<<<<<< HEAD
class UnhandledCallbackMiddleware(BaseMiddleware):
    """
    Middleware для обработки необработанных callback-запросов.
    
    Логирует callback_data, которые не были обработаны ни одним хендлером,
    чтобы отслеживать устаревшие кнопки или ошибки в обработчиках.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка middleware для callback_query событий.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Событие (CallbackQuery)
            data: Данные контекста
            
        Returns:
            Результат обработки или None, если callback не был обработан
        """
        # Проверяем, что это CallbackQuery
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        
        try:
            # Пытаемся обработать через следующий handler
            result = await handler(event, data)
            
            # Если handler вернул None или не обработал callback,
            # это означает, что callback не был обработан
            if result is None:
                logger.warning(
                    f"⚠️ Необработанный callback: data='{event.data}', "
                    f"user_id={event.from_user.id}, "
                    f"message_id={event.message.message_id if event.message else 'N/A'}"
                )
            
            return result
            
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            logger.error(
                f"❌ Ошибка при обработке callback: data='{event.data}', "
                f"user_id={event.from_user.id}, error={e}"
            )
            # Пробрасываем исключение дальше
=======
class UnhandledCallbackMiddleware:
    """Логирует все callback, которые не были обработаны"""
    
    async def __call__(self, handler, event, data):
        try:
            response = await handler(event, data)
            return response
        except Exception as e:
            # Логируем необработанные callback
            if hasattr(event, 'callback_query'):
                cb = event.callback_query
                logger.warning(f"🔔 Unhandled callback: {cb.data} от @{cb.from_user.username}")
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
            raise
