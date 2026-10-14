# Product demo materials

This folder is reserved for genuine Deutschpath product screenshots. As of 2026-10-14, this publish clone contains no verified UI, terminal, or rendered GitHub architecture screenshots. No image links are added to the product README until real captures exist.

Capture screenshots from the running publish clone, using isolated demo data and no real credentials or private attachments. Do not alter visible test results or replace them with mock imagery.

| Planned file | Capture procedure | Acceptance check | Status |
|---|---|---|---|
| `screenshots/01-conversation.png` | Open ChatWorkspace, show a selected session, recent list, persisted messages and history | Real local UI; no private conversation data | TODO |
| `screenshots/02-memory-recovery.png` | Create a demo conversation, restart the local services, reopen it | Same session and messages are read from persistent local storage | TODO |
| `screenshots/03-orchestration-clarification.png` | Ask to rename the current session without providing a title | M08 asks for the missing field; no command has executed | TODO |
| `screenshots/04-orchestration-execution.png` | Confirm the fixed rename/list proposal and show the real title read-back and list result | Command and Query results are visible; avoid implying a general Planner | TODO |
| `screenshots/05-follow-up-suggestions.png` | Opt in to suggestions, click one suggestion, leave it in the input | Suggestion is only prefilled and has not been submitted | TODO |
| `screenshots/06-test-results.png` | Run the documented pytest and API Smoke commands | Show actual terminal output and command context; no keys or private paths | TODO |
| `screenshots/07-architecture.png` | Render the README Mermaid diagram on the GitHub repository page after README update | Real GitHub rendering; no local mock of GitHub | TODO |

After capturing an image, review it for secrets, account identifiers, private attachment text, and accidental claims of production readiness. Then embed only that checked image in the root README. The current images directory is intentionally empty; `.gitkeep` preserves its path.
