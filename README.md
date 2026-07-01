# NXBAK

NXBAK is a Python CLI for Supabase database backup and restore using Git branches as snapshot history.

Source code stays on `main`. Backups are committed to snapshot branches:

- `snapshots/manual` for `nxbak backup`
- `snapshots/daily` for `nxbak backup --daily`
- `snapshots/monthly` for `nxbak backup --monthly`

Each snapshot branch only contains the latest snapshot files, while older backups remain available through Git commit history.
The `main` branch stays application-only: source code, README, config examples, tests, and GitHub Actions. Backup commits live only on snapshot branches, so feature updates and backup history do not mix.

## Requirements

- Python 3.10+
- Git
- PostgreSQL client tools: `pg_dump` and `pg_restore`
- A cloned Git repository with remote `origin`

## Installation
### Windows
```bash
pg_dump --version
pg_restore --version
scoop install postgresql
```

```bash
python -m pip install --user pipx
python -m pipx ensurepath

pipx install . --force
python -m pipx install . --force

nxbak --help
nxbak status

nxbak backup
```

### Linux
```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>

sudo apt install pipx
pipx install .
pipx install . --force
```

Alternative:

```bash
pip install .
```

Development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

```bash
sudo apt update
sudo apt install postgresql-client
set -a
source .env
set +a

nxbak status
```

```bash
cp .nxbak.example.yml .nxbak.yml

export NXBAK_SUPABASE_DB_URL="postgresql://..."
export NXBAK_ENCRYPTION_KEY="long-random-secret"

nxbak doctor # check configuration and environment
nxbak backup # creates a backup and commits to snapshots/manual
nxbak list # shows backup history from all snapshot branches
nxbak restore --dry-run # simulates restore without modifying the database
```

Never store secrets in `.nxbak.yml`. Use environment variables.
NXBAK automatically loads `.env` from the repository root when present, without overriding variables already set in your shell or CI.

## Configuration

```yaml
version: 1
remote: origin

branches:
  manual: snapshots/manual
  daily: snapshots/daily
  monthly: snapshots/monthly

source:
  type: supabase
  database_url_env: NXBAK_SUPABASE_DB_URL

backup:
  compression: gzip
  encryption: true
  encryption_key_env: NXBAK_ENCRYPTION_KEY
  schemas:
    - public
  include_auth_data: false
  auth_tables:
    - auth.users
    - auth.identities
    - auth.audit_log_entries

restore:
  verify_checksum: true
  require_confirmation: true
  schemas:
    - public
  include_auth_data: false
  auth_tables:
    - auth.users
    - auth.identities
    - auth.audit_log_entries
```

By default NXBAK backs up and restores only the `public` schema. Supabase manages internal schemas such as `auth`, `storage`, `extensions`, `vault`, `graphql`, and `realtime`; restoring those into a hosted Supabase project can produce permission and grant errors because the `postgres` role is not a full superuser.

Set `include_auth_data: true` when you also need auth user records in the same encrypted snapshot. NXBAK includes selected data tables (`auth.users`, `auth.identities`, and `auth.audit_log_entries`) but avoids sessions, refresh tokens, grants, event triggers, and internal Supabase privileges.

## Commands

Manual backup:

```bash
nxbak backup
nxbak backup --quiet
```

Daily backup:

```bash
nxbak backup --daily
```

Monthly backup:

```bash
nxbak backup --monthly
```

List snapshots:

```bash
nxbak list
nxbak list --manual
nxbak list --daily
nxbak list --monthly
nxbak list --limit 20
nxbak list --show-init
```

Without flags, `nxbak list` shows history from all snapshot branches.
Rows are sorted by commit date, newest first, across manual, daily, and monthly snapshots. Dates are displayed as `HH:MM:SS DD-MM-YYYY`.
NXBAK hides internal branch initialization commits from this list, so the table only shows real backup snapshots.
Branch initialization commits are hidden by default.

Restore latest:

```bash
nxbak restore
nxbak restore --daily
nxbak restore --monthly
```

Restore a commit:

```bash
nxbak restore --commit a81f92c
nxbak restore --daily --commit a81f92c
nxbak restore --monthly --commit a81f92c
```

Dry run:

```bash
nxbak restore --dry-run
```

Use force mode only for legacy/full Supabase dumps where hosted Supabase rejects internal managed objects but you still want `pg_restore` to continue processing restorable data:

```bash
nxbak restore --commit a81f92c --force
```

Inspect a snapshot manifest:

```bash
nxbak inspect --commit a81f92c
```

Decrypt a snapshot without restoring to Supabase:

```bash
nxbak decrypt --commit a81f92c
nxbak decrypt --daily --commit a81f92c --out ./restore-files
nxbak decrypt --monthly --commit a81f92c --out ./restore-files
```

Health checks:

```bash
nxbak status
nxbak doctor
nxbak doctor --remote-check
```

`nxbak doctor` checks local config, environment variables, and required tools. Use `--remote-check` when you also want to verify that Git can fetch from `origin`.

## GitHub Actions

Set repository secrets:

- `NXBAK_SUPABASE_DB_URL`
- `NXBAK_ENCRYPTION_KEY`

The manual workflow is click-only through GitHub Actions and writes to `snapshots/manual`. The daily workflow runs at 02:00 UTC and can also be triggered manually. The monthly workflow runs at 03:00 UTC on the first day of each month. Snapshot workflows do not run on push, so updates to `main` do not automatically create backup commits.

## Security

NXBAK does not checkout snapshot branches in the user's working tree. Backup and restore operations use temporary Git worktrees or temporary directories and clean them up afterwards. It does not force push, does not print full database URLs, and verifies checksums before restore.

When encryption is enabled, only `database.dump.gz.enc`, `manifest.json`, and `checksums.sha256` are committed to snapshot branches.

## Troubleshooting

`NXBAK repository not detected.`

Run NXBAK inside the cloned Git repository.

`Git remote 'origin' was not found.`

Configure it:

```bash
git remote add origin <url>
```

`Required executable 'pg_dump' was not found in PATH.`

Install PostgreSQL client tools and make sure `pg_dump` and `pg_restore` are available in your shell.
