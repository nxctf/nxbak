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
cp .nxbak.example.yml .nxbak.yml

export NXBAK_SUPABASE_DB_URL="postgresql://..."
export NXBAK_ENCRYPTION_KEY="long-random-secret"

nxbak doctor
nxbak backup
nxbak list
nxbak restore --dry-run
```

Never store secrets in `.nxbak.yml`. Use environment variables.

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

restore:
  verify_checksum: true
  require_confirmation: true
```

## Commands

Manual backup:

```bash
nxbak backup
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
nxbak list --daily
nxbak list --monthly
nxbak list --limit 20
```

Without flags, `nxbak list` shows history from all snapshot branches.

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
```

## GitHub Actions

Set repository secrets:

- `NXBAK_SUPABASE_DB_URL`
- `NXBAK_ENCRYPTION_KEY`

The daily workflow runs at 02:00 UTC and can also be triggered manually. The monthly workflow runs at 03:00 UTC on the first day of each month. Snapshot workflows do not run on push, so updates to `main` do not automatically create backup commits.

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
