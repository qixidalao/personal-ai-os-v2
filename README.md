# Personal AI OS

**Self-hosted AI workspace with conversations, tools, approvals, and optional remote execution.**

Personal AI OS runs as a web application on your own machine or server. It connects to model providers that you configure, stores conversations locally, and can run tools inside a restricted local sandbox. A regular user can optionally connect their own SSH server for remote execution.

## Current scope

- Email/password sign-in with server-side sessions
- Chat with streaming responses, saved conversations, and file/image attachments
- OpenAI-compatible model providers
- Tool registry with approval controls and run history
- Local sandbox for the instance administrator
- Per-account conversation and run ownership
- Optional SSH execution on a user's own public server
- Browser-based speech input and speech playback
- OneBot integration for deployments that configure it

This is a self-hosted application, not a hosted cloud-computer service. Each deployment operator is responsible for its model provider, email delivery, network exposure, storage, and backups. Multi-user isolation is in progress; do not enable public self-registration until file/media ownership isolation is complete.

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer and npm
- Linux or WSL2 for local sandbox execution (Bubblewrap is recommended)
- A model-provider API key
- Optional: SMTP credentials for verification and password recovery
- Optional: Docker on a user's own server for remote execution

## Install

```bash
git clone https://github.com/qixidalao/personal-ai-os-v2.git
cd personal-ai-os-v2
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
```

## Configure and start

Create a local virtual environment and install Python and frontend dependencies as shown below. Keep credentials in the local `storage/` directory or environment variables; never commit them.

Start the service on loopback:

```bash
./scripts/hhs.sh start
```

Open `http://127.0.0.1:8080`. By default, the launcher binds only to loopback. Remote access requires an authenticated HTTPS reverse proxy or private network. Do not bind `0.0.0.0` or expose the backend port directly to the Internet.

For development:

```bash
cd frontend
npm install
npm run dev
```

## User documentation

- [User guide](docs/AIOS-使用手册.md)
- [Connect your own execution server](docs/AIOS-执行器接入指南.md)
- [Documentation index](docs/README.md)

Architecture, protocol, Termux, plugin, and API notes are historical/reference material and may not match this release. The docs index labels their status. Do not use them as installation steps without verifying against the current code.

The administrator console is at `/#/admin`; normal users use `/#/settings`. Instance-wide provider secrets, registration/email configuration, login defenses, and developer diagnostics belong to the administrator. Users configure only their personal preferences, account, and execution server.

## First launch and accounts

Start the service and open `http://127.0.0.1:8080` on the same machine. If the account database is empty, a local-only setup screen creates the first administrator; it does not require SMTP. After setup, users sign in with email and password. SMTP is used for subsequent verification and password recovery.

## Model providers

Each account configures its own compatible model provider and API key under **Settings → Model & Services**. Credentials and provider choices are stored in that account's private runtime settings, not shared with other accounts.

## Remote execution

A regular user may configure a public SSH server they control. The instance will not fall back to running that user's commands on the host. `127.0.0.1`, private networks, and metadata addresses are rejected for regular accounts.

The server bootstrap script is `scripts/aios-bootstrap.sh`; its image source is `scripts/runner/Dockerfile`. The bootstrap builds the runner image locally on the user's server. Review both files before running the bootstrap as root.

## Tests

```bash
python -m pytest tests -q
cd frontend && npm run build
```

## Data and secrets

- `storage/` contains runtime settings, credentials, sessions, logs, uploaded media, and databases; it is ignored by Git.
- Back up `storage/` privately. Never attach it to an issue or publish it.
- Rotate any credential that has appeared in chat, logs, screenshots, or a public repository.
- The historical development archive is kept locally and is intentionally excluded from Git.

## License

GPL-3.0. See [LICENSE](LICENSE).
