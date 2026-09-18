# Security Model — Openings Personal Job Search OS

## 1. Network Boundary
- **Localhost Bind:** `OPENINGS_WEB_BIND=127.0.0.1`, port `8501`.
- **Remote Access:** Recommended via SSH tunnel or Tailscale VPN. Public 0.0.0.0 binding is disabled.

## 2. Secrets & Credentials
- All secrets (Telegram bot tokens, API keys) are injected via environment variables or `.env` file.
- `.env` is listed in `.gitignore` and never committed to version control.

## 3. Human-In-The-Loop Security
- **Submission Barrier:** AI agents are restricted to read, score, draft, and package applications.
- **External Actions:** Submitting applications, sending emails, or agreeing to legal terms requires human initiation.
