# Sextant

CLI tool for navigating security events across multiple endpoints (Splunk, TheHive).

## Installation

Requires Python 3.10+.

```bash
pip install .
```

For Okta/WebAuthn authentication support:

```bash
pip install ".[auth]"
```

## Configuration

Sextant reads its configuration from `~/.config/sextant/config.yaml`. Each entry in `endpoints` registers a CLI subcommand.

```yaml
endpoints:
  - name: splunk-prod
    client: splunk
    remote: https://splunk.example.com:8089
    credentials:
      provider: 1password
      vault: Security
      item: Splunk
      fields:
        secret: api-token

  - name: hive
    client: thehive
    remote: https://thehive.example.com:9000
    credentials:
      secret: <your-api-key>
```

### Endpoints

| Field | Description |
|-------|-------------|
| `name` | Name used as the CLI subcommand |
| `client` | Client module to use (`splunk` or `thehive`) |
| `remote` | Base URL of the service |
| `verify` | TLS verification (default: `true`). Set to `false` to skip, or a path to a CA bundle |
| `credentials` | Authentication credentials (see below) |

### Credentials

**Inline credentials** -- provide fields directly:

```yaml
credentials:
  secret: my-api-token
```

TheHive also supports basic auth:

```yaml
credentials:
  username: analyst
  password: hunter2
```

**1Password integration** -- fields are resolved at runtime via the `op` CLI:

```yaml
credentials:
  provider: 1password
  vault: Security
  item: Splunk
  fields:
    secret: api-token
```

## Usage

```
sextant <endpoint> <resource> <action> [options]
```

### Global commands

```bash
# Test authentication against all configured endpoints
sextant check
```

### Splunk

```bash
# Run a search query (results stream as a live table in the terminal)
sextant splunk-prod query "search index=_internal | head 10 | fieldsummary"
sextant splunk-prod query --from 1h --to now "search index=main sourcetype=syslog"

# List and inspect saved searches
sextant splunk-prod search list
sextant splunk-prod search list --user admin --name "failed logins"
sextant splunk-prod search get "My Saved Search"

# Dispatch a saved search and optionally trigger its alert actions
sextant splunk-prod search run "My Saved Search"
sextant splunk-prod search run --trigger --from 2h --to 30m "My Saved Search"

# Manage search jobs
sextant splunk-prod job list
sextant splunk-prod job list --user admin
sextant splunk-prod job get <sid>
sextant splunk-prod job get <sid> --wait 30 --fields _time,host,source

# List accessible indexes
sextant splunk-prod indexes
```

### TheHive

```bash
# List recent alerts and cases (default: last 10 minutes)
sextant hive alert list
sextant hive alert list --from 1h
sextant hive case list --from 7d

# Get a specific alert
sextant hive alert get <alert-id>

# Create an alert from a JSON file
sextant hive alert new alert.json
```

### Piping

When stdout is not a terminal, all commands output JSON for piping:

```bash
# Pipe job results between commands
sextant splunk-prod search run "My Search" | sextant splunk-prod job get - --wait 60

# Feed into jq
sextant hive alert list --from 1d | jq '.[].title'
```

### Time formats

Time options (`--from`, `--to`) accept:

| Format | Example | Description |
|--------|---------|-------------|
| Relative | `30s`, `10m`, `2h`, `7d`, `1y` | Duration ago from now |
| ISO 8601 | `2025-01-15T08:00:00` | Absolute timestamp |
