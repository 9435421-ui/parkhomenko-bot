\# Bot Developer Mode - Budget Protection Rules



\## CRITICAL: Budget Constraints

\- Provider: Router AI ($20 balance, $3 daily limit)

\- Model: Gemini Flash (cheapest available)

\- ALWAYS show estimated cost before API calls

\- Ask confirmation for operations \&gt;$0.01

\- Hard stop at $3 daily spend



\## Token Economy

\- Prefer concise answers over long explanations

\- Suggest manual edits for simple changes (\&lt;10 lines)

\- Never analyze entire codebase unless explicitly asked

\- Max 3 files in context - ask which to focus on

\- Use Ask mode for questions, Code mode only for implementation



\## Project: anton\_agency\_bot

Telegram bot for construction permit consulting in Russia.



\### Tech Stack

\- Python + aiogram (Telegram framework)

\- SQLite database

\- JSON knowledge base in /data/



\### Key Files Structure

\- /bot.py - main entry point

\- /handlers/ - Telegram handlers (quiz, leads, admin)

\- /database.py - SQLite operations

\- /config.py - settings and constants

\- /data/ - JSON knowledge base (EXCLUDE large files from context)



\### Business Context

\- Service: construction permit approval (150-180k RUB)

\- Target: Russian apartment owners

\- Triggers: urgent sale, bank requirements, inspection checks

\- Common requests: studio merge, room merge, balcony merge



\## Operation Rules



\### Before Any Edit:

1\. Confirm necessity with user

2\. Show estimated token cost

3\. Get explicit approval

4\. Include only relevant files in context



\### Forbidden (Always Ask First):

\- Web search

\- Browser tool

\- Large file analysis (\&gt;100KB)

\- Multi-file refactoring (\&gt;3 files)

\- Database schema changes



\### Preferred Workflow:

1\. User describes problem

2\. You suggest solution approach

3\. User approves approach

4\. You provide code in response

5\. User applies manually OR approves auto-edit



\## When Context Grows Large

If conversation exceeds 10 messages:

\- Suggest summarizing or starting new task

\- Offer to create checkpoint

\- Remind user of current spend



\## Error Handling

\- If Router AI returns error → stop and inform user

\- If rate limited → wait and retry once

\- If model unavailable → suggest alternative



\## Response Format

Always include:

\- \[Cost estimate: $X.XXX]

\- \[Files in context: N]

\- \[Approach approval needed: Yes/No]

