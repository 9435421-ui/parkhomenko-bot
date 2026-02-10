"""Middleware для логирования событий."""
import logging

logger = logging.getLogger(__name__)


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
            raise
