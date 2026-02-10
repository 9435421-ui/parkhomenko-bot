"""
RAG-система для работы с базой знаний
"""
import os
import re
from typing import List, Dict, Optional
import aiofiles


class KnowledgeBase:
    """RAG-система для поиска релевантной информации в базе знаний"""
    
    def __init__(self, docs_dir: str = "docs"):
        self.docs_dir = docs_dir
        self.documents: List[Dict[str, str]] = []
        self.indexed = False
    
    async def index_documents(self):
        """Асинхронная индексация всех .md файлов из папки docs"""
        if not os.path.exists(self.docs_dir):
            print(f"⚠️ Папка {self.docs_dir} не найдена")
            return
        
        # Исключаем системные папки
        exclude_dirs = {'knowledge_base', '__pycache__', '.git', 'backups', 'migrations', 'mini_app', 'uploads'}
        
        document_count = 0
        
        for root, dirs, files in os.walk(self.docs_dir):
            # Исключаем системные папки из обхода
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for filename in files:
                if filename.endswith(('.md', '.txt')):
                    filepath = os.path.join(root, filename)
                    try:
                        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            
                            # Сохраняем относительный путь для лучшей идентификации
                            relative_path = os.path.relpath(filepath, self.docs_dir)
                            
                            self.documents.append({
                                'filename': relative_path,
                                'content': content,
                                'path': filepath
                            })
                            document_count += 1
                            
                    except Exception as e:
                        print(f"❌ Ошибка чтения {filename}: {e}")
        
        self.indexed = True
        print(f"✅ База знаний проиндексирована: {document_count} документов")
        return document_count
    
    async def get_context(
        self,
        query: str,
        max_chunks: int = 3,
        context_size: int = 800
    ) -> str:
        """
        Получить релевантный контекст по запросу
        
        Args:
            query: Запрос пользователя
            max_chunks: Максимальное количество фрагментов
            context_size: Размер каждого фрагмента в символах
        
        Returns:
            str: Релевантный контекст из базы знаний
        """
        if not self.indexed:
            await self.index_documents()
        
        if not self.documents:
            return "База знаний пуста."
        
        # Извлекаем ключевые слова из запроса
        query_lower = query.lower()
        keywords = self._extract_keywords(query_lower)
        
        # Оценка релевантности документов
        scored_docs = []
        for doc in self.documents:
            score = self._calculate_relevance_score(doc['content'], keywords)
            if score > 0:
                scored_docs.append((score, doc))
        
        # Сортировка по релевантности
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        
        # Формирование контекста
        if not scored_docs:
            return "Информация по вашему запросу не найдена в базе знаний."
        
        context_parts = []
        for i, (score, doc) in enumerate(scored_docs[:max_chunks]):
            # Извлекаем релевантный фрагмент
            snippet = self._extract_relevant_snippet(
                doc['content'],
                keywords,
                context_size
            )
            context_parts.append(
                f"📄 Из документа '{doc['filename']}':\n{snippet}"
            )
        
        return "\n\n".join(context_parts)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Извлечение ключевых слов из текста"""
        # Удаляем стоп-слова и извлекаем значимые слова
        stop_words = {
            'как', 'что', 'это', 'где', 'когда', 'почему', 'можно', 'нужно',
            'хочу', 'хотим', 'нужен', 'есть', 'ли', 'или', 'также', 'если'
        }
        
        words = re.findall(r'\w+', text.lower())
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        return keywords
    
    def _calculate_relevance_score(
        self,
        content: str,
        keywords: List[str]
    ) -> int:
        """Расчёт релевантности документа на основе ключевых слов"""
        content_lower = content.lower()
        
        # Простой подсчёт вхождений ключевых слов
        score = 0
        for keyword in keywords:
            score += content_lower.count(keyword)
        
        return score
    
    def _extract_relevant_snippet(
        self,
        content: str,
        keywords: List[str],
        context_size: int = 800
    ) -> str:
        """Извлечение релевантного фрагмента из документа"""
        content_lower = content.lower()
        
        # Поиск первого совпадения с ключевым словом
        best_position = -1
        for keyword in keywords:
            pos = content_lower.find(keyword)
            if pos != -1 and (best_position == -1 or pos < best_position):
                best_position = pos
        
        if best_position == -1:
            # Если не нашли — берём начало
            snippet = content[:context_size]
            if len(content) > context_size:
                snippet += "..."
            return snippet
        
        # Берём контекст вокруг найденного ключевого слова
        start = max(0, best_position - context_size // 2)
        end = min(len(content), best_position + context_size // 2)
        
        snippet = content[start:end]
        
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def get_document_categories(self) -> List[str]:
        """Получить список категорий документов (директорий)"""
        categories = set()
        
        for doc in self.documents:
            # Извлекаем первую часть пути (категорию)
            parts = doc['filename'].split(os.sep)
            if len(parts) > 1:
                categories.add(parts[0])
        
        return sorted(list(categories))
    
    def get_documents_by_category(self, category: str) -> List[Dict[str, str]]:
        """Получить документы по категории"""
        return [
            doc for doc in self.documents
            if doc['filename'].startswith(category)
        ]


# Singleton instance
kb = KnowledgeBase()


# Alias для совместимости
async def search(query: str, limit: int = 3) -> List[Dict[str, str]]:
    """Удобная функция-алиас для get_context"""
    context = await kb.get_context(query, max_chunks=limit)
    return [{'text': context, 'source': 'knowledge_base'}]
