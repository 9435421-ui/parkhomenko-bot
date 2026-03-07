"""
Discovery — автоматический поиск новых чатов/групп через глобальный поиск Telegram.
Использует ключевые слова из ScoutParser для поиска релевантных источников.
"""
import logging
import re
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputPeerEmpty
from config import API_ID, API_HASH
from services.scout_parser import ScoutParser

logger = logging.getLogger(__name__)


class Discovery:
    """Класс для автоматического поиска новых чатов/групп через глобальный поиск Telegram"""
    
    def __init__(self):
        self.scout_parser = ScoutParser()
        self.client = None
    
    def get_keywords(self) -> List[str]:
        """
        Возвращает список ключевых слов для поиска.
        Использует KEYWORDS и TECHNICAL_TERMS из ScoutParser.
        
        Returns:
            Список ключевых слов для поиска
        """
        # Извлекаем ключевые слова из списков ScoutParser
        keywords = []
        
        # Добавляем простые ключевые слова (без regex)
        for kw in self.scout_parser.KEYWORDS:
            # Убираем regex-символы для поиска
            clean_kw = re.sub(r'[^\w\s]', '', kw).strip()
            if clean_kw and len(clean_kw) > 3:
                keywords.append(clean_kw.lower())
        
        # Добавляем технические термины (извлекаем базовые слова)
        for term in self.scout_parser.TECHNICAL_TERMS:
            # Убираем regex-символы и извлекаем основное слово
            clean_term = re.sub(r'[^\w\s]', '', term).strip()
            # Убираем окончания (перепланиров -> перепланировка)
            base_word = re.sub(r'[аяеиоуыэю]$', '', clean_term).strip()
            if base_word and len(base_word) > 3:
                keywords.append(base_word.lower())
        
        # Убираем дубликаты и сортируем
        keywords = sorted(list(set(keywords)))
        
        logger.debug(f"🔑 Discovery: подготовлено {len(keywords)} ключевых слов для поиска")
        return keywords
    
    async def _get_client(self) -> Optional[TelegramClient]:
        """Получить или создать Telegram клиент"""
        if self.client is None:
            try:
                self.client = TelegramClient('anton_discovery', API_ID, API_HASH)
                await self.client.connect()
                
                if not await self.client.is_user_authorized():
                    logger.error("❌ Discovery: Антон не авторизован в Telegram!")
                    await self.client.disconnect()
                    self.client = None
                    return None
                
                logger.info("✅ Discovery: Telegram клиент подключен")
            except Exception as e:
                logger.error(f"❌ Discovery: ошибка подключения к Telegram: {e}")
                self.client = None
                return None
        
        return self.client
    
    async def find_new_sources(self, max_results: int = 20) -> List[Dict]:
        """
        Поиск новых чатов/групп через глобальный поиск Telegram.
        
        Args:
            max_results: Максимальное количество результатов для каждого запроса
            
        Returns:
            Список найденных источников с полями: link, title, participants_count
        """
        client = await self._get_client()
        if not client:
            logger.warning("⚠️ Discovery: не удалось подключиться к Telegram")
            return []
        
        keywords = self.get_keywords()
        if not keywords:
            logger.warning("⚠️ Discovery: нет ключевых слов для поиска")
            return []
        
        # Используем наиболее релевантные ключевые слова для поиска
        # Берем первые 5-7 ключевых слов, чтобы не перегружать API
        search_keywords = keywords[:7]
        
        all_results = []
        seen_links = set()
        
        try:
            for keyword in search_keywords:
                try:
                    logger.info(f"🔍 Discovery: поиск по ключевому слову '{keyword}'...")
                    
                    # Глобальный поиск через Telethon
                    # SearchGlobalRequest ищет по всем публичным чатам и каналам
                    try:
                        results = await client(SearchGlobalRequest(
                            q=keyword,
                            filter=None,  # Ищем везде (чаты, каналы, группы)
                            min_date=None,
                            max_date=None,
                            offset_rate=0,
                            offset_peer=InputPeerEmpty(),
                            offset_id=0,
                            limit=max_results
                        ))
                    except Exception as search_error:
                        logger.warning(f"⚠️ Discovery: ошибка глобального поиска по '{keyword}': {search_error}")
                        # Fallback: используем простой поиск через client.get_entity если доступен username
                        continue
                    
                    # Обрабатываем результаты
                    # SearchGlobalRequest возвращает объект с полями: messages, chats, users
                    # Обрабатываем как chats, так и messages (сообщения могут содержать ссылки на чаты)
                    processed_chat_ids = set()
                    
                    # Обрабатываем чаты из results.chats
                    if hasattr(results, 'chats') and results.chats:
                        for chat_entity in results.chats:
                            try:
                                # ── НОВЫЙ ФИЛЬТР: только живые чаты, не каналы ──
                                is_broadcast_channel = (
                                    hasattr(chat_entity, 'broadcast') 
                                    and chat_entity.broadcast 
                                    and not getattr(chat_entity, 'megagroup', False)
                                )
                                if is_broadcast_channel:
                                    logger.debug(f"⏭️ Пропускаем канал (не чат): {getattr(chat_entity, 'title', '')}")
                                    continue
                                
                                # Пропускаем личные чаты (нам нужны только группы/каналы)
                                if not (hasattr(chat_entity, 'broadcast') or hasattr(chat_entity, 'megagroup')):
                                    # Если это не канал и не мегагруппа, проверяем наличие id
                                    if not (hasattr(chat_entity, 'id') and chat_entity.id):
                                        continue
                                
                                chat_id = chat_entity.id
                                if chat_id in processed_chat_ids:
                                    continue
                                processed_chat_ids.add(chat_id)
                                
                                # Формируем ссылку
                                if hasattr(chat_entity, 'username') and chat_entity.username:
                                    link = f"https://t.me/{chat_entity.username}"
                                else:
                                    # Для приватных чатов используем ID (формат: -1001234567890)
                                    # Убираем минус и первые 3 цифры для формата t.me/c/
                                    chat_id_str = str(abs(chat_id))
                                    if len(chat_id_str) > 3:
                                        link = f"https://t.me/c/{chat_id_str[3:]}"
                                    else:
                                        link = f"https://t.me/c/{chat_id_str}"
                                
                                # Пропускаем дубликаты
                                if link in seen_links:
                                    continue
                                seen_links.add(link)
                                
                                # Получаем название и количество участников
                                title = getattr(chat_entity, 'title', '') or getattr(chat_entity, 'name', '') or link
                                participants_count = getattr(chat_entity, 'participants_count', None)
                                
                                # Фильтруем слишком маленькие группы (меньше 50 участников обычно не интересны)
                                if participants_count and participants_count < 50:
                                    continue
                                
                                # Фильтруем по названию: должны быть релевантные ключевые слова
                                title_lower = title.lower()
                                if not any(kw in title_lower for kw in ['перепланиров', 'недвижим', 'жк', 'жил', 'квартир', 'ремонт', 'строитель', 'москв']):
                                    # Пропускаем группы, которые явно не связаны с нашей тематикой
                                    continue
                                
                                all_results.append({
                                    'link': link,
                                    'title': title,
                                    'participants_count': participants_count or 0
                                })
                                
                                logger.debug(f"✅ Discovery: найден источник '{title}' ({participants_count or '?'} участников)")
                                
                            except Exception as e:
                                logger.debug(f"⚠️ Discovery: ошибка обработки чата: {e}")
                                continue
                    
                    # Также обрабатываем сообщения из results.messages (могут содержать ссылки на чаты)
                    if hasattr(results, 'messages') and results.messages:
                        for msg in results.messages:
                            if not hasattr(msg, 'peer_id') or not msg.peer_id:
                                continue
                            
                            try:
                                peer = msg.peer_id
                                
                                # Пропускаем личные чаты
                                if not hasattr(peer, 'channel_id') and not hasattr(peer, 'chat_id'):
                                    continue
                                
                                # Получаем ID чата
                                if hasattr(peer, 'channel_id'):
                                    chat_id = peer.channel_id
                                elif hasattr(peer, 'chat_id'):
                                    chat_id = peer.chat_id
                                else:
                                    continue
                                
                                if chat_id in processed_chat_ids:
                                    continue
                                processed_chat_ids.add(chat_id)
                                
                                # Получаем полную информацию о чате
                                try:
                                    chat_entity = await client.get_entity(chat_id)
                                except Exception:
                                    continue
                                
                                # Формируем ссылку
                                if hasattr(chat_entity, 'username') and chat_entity.username:
                                    link = f"https://t.me/{chat_entity.username}"
                                else:
                                    chat_id_str = str(abs(chat_id))
                                    if len(chat_id_str) > 3:
                                        link = f"https://t.me/c/{chat_id_str[3:]}"
                                    else:
                                        link = f"https://t.me/c/{chat_id_str}"
                                
                                # Пропускаем дубликаты
                                if link in seen_links:
                                    continue
                                seen_links.add(link)
                                
                                # Получаем название и количество участников
                                title = getattr(chat_entity, 'title', '') or getattr(chat_entity, 'name', '') or link
                                participants_count = getattr(chat_entity, 'participants_count', None)
                                
                                # Фильтруем слишком маленькие группы
                                if participants_count and participants_count < 50:
                                    continue
                                
                                # Фильтруем по названию
                                title_lower = title.lower()
                                if not any(kw in title_lower for kw in ['перепланиров', 'недвижим', 'жк', 'жил', 'квартир', 'ремонт', 'строитель', 'москв']):
                                    continue
                                
                                all_results.append({
                                    'link': link,
                                    'title': title,
                                    'participants_count': participants_count or 0
                                })
                                
                                logger.debug(f"✅ Discovery: найден источник из сообщений '{title}' ({participants_count or '?'} участников)")
                                
                            except Exception as e:
                                logger.debug(f"⚠️ Discovery: ошибка обработки сообщения: {e}")
                                continue
                    
                    # Небольшая задержка между запросами, чтобы не перегружать API
                    import asyncio
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Discovery: ошибка поиска по '{keyword}': {e}")
                    continue
            
            logger.info(f"✅ Discovery: найдено {len(all_results)} новых источников")
            return all_results
            
        except Exception as e:
            logger.error(f"❌ Discovery: критическая ошибка поиска: {e}")
            return []
        finally:
            # Не закрываем клиент, он может использоваться повторно
            pass
    
    async def close(self):
        """Закрыть соединение с Telegram"""
        if self.client:
            try:
                await self.client.disconnect()
                logger.info("✅ Discovery: соединение с Telegram закрыто")
            except Exception:
                pass
            finally:
                self.client = None
