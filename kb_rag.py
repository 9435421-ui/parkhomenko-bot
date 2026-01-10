import os
import re
from typing import List, Dict

class KnowledgeBaseRAG:
    """Простая RAG-система для работы с markdown базой знаний"""
    
    def __init__(self, knowledge_dir: str):
        self.knowledge_dir = knowledge_dir
        self.documents: List[Dict[str, str]] = []
        
    def index_markdown_files(self):
        """Индексация всех .md и .txt файлов из папки"""
        if not os.path.exists(self.knowledge_dir):
            print(f"⚠️ Папка {self.knowledge_dir} не найдена")
            return
            
        for filename in os.listdir(self.knowledge_dir):
            if filename.endswith(('.md', '.txt')):
                filepath = os.path.join(self.knowledge_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        self.documents.append({
                            'filename': filename,
                            'content': content
                        })
                        print(f"✅ Проиндексирован файл: {filename}")
                except Exception as e:
                    print(f"❌ Ошибка чтения {filename}: {e}")
        
        print(f"📚 Всего документов в базе знаний: {len(self.documents)}")
    
    def get_rag_context(self, query: str, max_chunks: int = 3) -> str:
        """Получить релевантный контекст по запросу"""
        if not self.documents:
            return "База знаний пуста."
        
        # Простой поиск по ключевым словам
        query_lower = query.lower()
        keywords = re.findall(r'\w+', query_lower)
        
        # Оценка релевантности документов
        scored_docs = []
        for doc in self.documents:
            content_lower = doc['content'].lower()
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                scored_docs.append((score, doc))
        
        # Сортировка по релевантности
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        
        # Формирование контекста
        if not scored_docs:
            return "Информация по вашему запросу не найдена в базе знаний."
        
        context_parts = []
        for i, (score, doc) in enumerate(scored_docs[:max_chunks]):
            # Берем начало документа или релевантный фрагмент
            snippet = self._extract_relevant_snippet(doc['content'], keywords)
            context_parts.append(f"Из документа '{doc['filename']}':\n{snippet}")
        
        return "\n\n".join(context_parts)
    
    def _extract_relevant_snippet(self, content: str, keywords: List[str], context_size: int = 500) -> str:
        """Извлечь релевантный фрагмент из документа"""
        content_lower = content.lower()
        
        # Поиск первого совпадения с ключевым словом
        best_position = -1
        for keyword in keywords:
            pos = content_lower.find(keyword)
            if pos != -1 and (best_position == -1 or pos < best_position):
                best_position = pos
        
        if best_position == -1:
            # Если не нашли — берем начало
            return content[:context_size] + ("..." if len(content) > context_size else "")
        
        # Берем контекст вокруг найденного ключевого слова
        start = max(0, best_position - context_size // 2)
        end = min(len(content), best_position + context_size // 2)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
            
        return snippet
    
    def get_context(self, query: str) -> str:
        """Алиас для совместимости с другими версиями"""
        return self.get_rag_context(query)
