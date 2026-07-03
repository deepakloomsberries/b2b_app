# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please **do not** open a public GitHub issue.

Instead, report it privately by opening a [GitHub Security Advisory](https://github.com/deepakloomsberries/sales/security/advisories/new) or by contacting the maintainer directly.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested fix or mitigation

You can expect an acknowledgement within 48 hours and a resolution or timeline within 7 days.

## Scope

This project is a self-hosted internal tool. The following are in scope:
- Authentication and session handling
- SQL injection
- Cross-site scripting (XSS)
- Cross-site request forgery (CSRF)
- Sensitive data exposure

## Known Limitations

- CSRF protection is not currently implemented. It is recommended to run this app behind a reverse proxy restricted to trusted networks.
- The app uses SQLite, which is not suitable for high-concurrency multi-process deployments.

## Implemented Protections

- Login attempts are rate-limited: an account is locked for 15 minutes after 5 consecutive failed login attempts (tracked per-username in the database).
- CSV downloads (order export, bulk order export) and Google Sheets order export sanitize cell values that start with `=`, `+`, `-`, or `@` to prevent formula/CSV injection when opened in Excel or Sheets.
- Order status changes, order assignment, and bulk order actions require the `warehouse` or `admin` role.
