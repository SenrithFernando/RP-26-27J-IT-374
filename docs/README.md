# SafeRide-LK routing documentation

**First time on another laptop? Start with the [project guide and first-run checklist](project-guide.md#first-run-checklist).** It uses a separate reviewer database and private new accounts; do not restore the author's private backup or copy `.env`/GPS/session data.

- [Project guide](project-guide.md): tested Python/Node baseline, installation, PostgreSQL/user setup, migrations, repeatable synthetic seeds, private account activation/assignment, startup, optional Google/phone HTTPS, checks and troubleshooting.
- [Architecture](architecture.md): runtime, constraints and navigation.
- [Integration contract](integration-contract.md): provisional Hasara boundary.
- [Evaluation](evaluation.md): provenance, collection and model limits.
- [PP1 walkthrough](pp1-walkthrough.md): current UI and checks.
- [Historical archive and complete move inventory](archive/index.md).

Machine-readable fixtures, schemas and metrics remain at stable paths for existing tests. Historical reports are retained, not regenerated.

Known first-run limits are explicit in the project guide: fresh pip resolution failed in this shell, backend dependencies are not fully locked, optional UI checks need unlisted Playwright, and the tracked ML bundle currently requires a CRLF checkout to match its byte checksums. The existing model is synthetic-trained; no retraining is part of installation. Simulation and manual location review do not need Google keys. Live Google requests require the reviewer's own enabled/billed project and explicit approval.
