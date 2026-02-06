# Instructions for Jules (Technical Specialist)

## Phase 2: Content Agent V2.0 + Spy Module

The stabilization phase is complete. Now implement the expansion as per the following Technical Task (TZ):

### 1. Configuration
- Use `config.py` as provided in the chat.
- All secrets must be moved to `.env`.
- Thread IDs for leads: 2 (Apartments), 5 (Commerce), 8 (Houses).
- Thread IDs for content: 85 (Drafts), 87 (Seasonal), 88 (Logs).

### 2. Media-Anton (Aiogram 3.7)
- **Cross-posting**: Implementation of posting to TG Channel and VK Group.
- **Interview Mode**: Topic 85 collection of facts from expert -> AI generation.
- **AI-Creative**: Yandex Art integration for covers.
- **Info-Flow**: Automatic theme suggestions in topic 87.

### 3. Spy Module
- Async monitoring of keywords in chats.
- Forwarding leads to `NOTIFICATIONS_CHANNEL_ID`.

### 4. Quiz V2.0
- Strict 7-step funnel: City -> Object Type -> Floor -> Area -> Status -> Description -> File Upload.
- Mini App integration (https://ternion.ru/mini_app/).

### 5. Security
- No tokens in code.
- No changes to approved quiz question wordings.
