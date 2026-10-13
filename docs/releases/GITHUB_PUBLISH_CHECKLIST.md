# GitHub publication checklist — JXcloudforge/unified_deutschpath_agent

Status: preparation only. No Git configuration, index, commit, push, or tag
was changed for this checklist. The target repository page was checked
read-only on 2026-10-13 and showed an empty repository. The current `origin`
still points to `JXcloudforge/CRM-agent`; never push this checkout's `main` to
that remote or directly to the new target.

## Recommended clean-history publication

1. Confirm in GitHub that `JXcloudforge/unified_deutschpath_agent` is the
   intended empty destination and that its visibility/license are correct.
2. Create a clean temporary clone of the destination (not from this checkout),
   then copy only the reviewed paths listed below from this working tree.
   This starts with the destination's clean Git history and does not import the
   CRM-agent commits. Do not copy `.git` or use `git remote set-url` here.
3. Review the staged file list and every data/evaluation fixture. Search for
   secrets and private user data. Confirm `.env`, `.venv`, `data/`, databases,
   Chroma collections, uploads, OCR staging, and local logs are absent.
4. Run compileall and `scripts/run_tests.ps1` in the clean candidate. Verify
   `.env.example` contains placeholders only and that no generated temp data is
   staged.
5. Present the exact proposed file list, repository URL, visibility, branch,
   commit message, and test results to the user for final approval.
6. Only after that approval, create the initial commit and push to the new
   repository. Do not create a release tag until a tagged release is separately
   approved. Keep the original CRM-agent checkout and history untouched.

## Include after content review

- `app/**` — active application source only.
- `ui/**` — Streamlit UI and API client.
- `tests/**` — test source and synthetic/public fixtures; inspect images and
  text for private material before inclusion.
- `evals/**` — router evaluation source and candidate datasets only after
  checking for personal data, confidential prompts, API output, and credentials.
- `scripts/**` — active startup, test, acceptance, and evaluation scripts.
- `docs/**` — current README-linked architecture, features, stack, debugging,
  iteration/release notes; review `docs/history/` for machine paths or private
  identifiers and omit local-only reports if they expose them.
- Root files: `README.md`, `ARCHITECTURE.md` if maintained, `pyproject.toml`,
  `.env.example`, `.gitignore`, and `start.bat`.
- Include only additional root configuration files proven necessary by the
  active application and tests.

## Exclude

- `.git/`, the legacy `agent` gitlink, and all CRM-agent commit history.
- Deleted `02_crm_agent/**` history paths; do not stage their removals as part
  of an initial independent-repository publication.
- `.env`, `.venv/`, `data/`, SQLite/DB files, Chroma stores, uploads, OCR image
  staging, user material, logs, test temp directories, caches, and local
  acceptance artifacts.
- External `Deutschpath_agent_archive`, B4/B7 backups, and protected legacy
  user data.
- Any private API output or credentials, even if found under an otherwise
  includable `evals/`, `tests/`, or `docs/` path.

## Why not publish this checkout directly

This checkout is on `main`, and `origin` points to the old CRM-agent remote. At
review time it had 123 staged paths, 124 unstaged path changes, 97 tracked
`02_crm_agent` deletions, and the removed `agent` gitlink still present in the
index (mode `160000`, object `633fbf9f06ff6e0fbb6dd8aa3697f36f37a02ed9`). The
index contains an existing release candidate; do not clear or reuse it for the
new repository. Starting from the target's clean clone and copying a reviewed
whitelist avoids transferring unrelated history or staged CRM deletions.

## User approval required before publication

- Confirm the target repository, owner, visibility, and any license choice.
- Approve the final sanitized path list and initial commit message.
- Approve the first commit and push to the new repository.
- Approve any later version tag/release separately.
