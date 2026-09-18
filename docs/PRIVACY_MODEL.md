# Privacy Model — Openings Personal Job Search OS

## PII Management & Data Isolation
1. **Local Storage Only:** Candidate PII (phone number, home address, email, employment history) resides exclusively in local files (`candidate_profile.yaml`) and the local SQLite database (`openings-data`).
2. **No External Transmission Without Consent:** CV attachments and notes stored in Openings are never transmitted to third-party endpoints or external services automatically.
3. **Public Exposure Safeguards:** Web dashboard and MCP endpoints bind exclusively to `127.0.0.1`.
4. **Git Sanitation:** `.env`, `.env.example` secrets, SQLite databases, and tailored PDF/HTML CVs are excluded from Git version control via `.gitignore`.
