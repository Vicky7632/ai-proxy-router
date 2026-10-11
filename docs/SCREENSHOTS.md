# Screenshot checklist

This file is a capture plan, not a gallery. **No screenshots have been
captured or included by this documentation change.** Capture the running,
real application and keep the resulting files in an approved location.

Before each capture:

- Use a non-production account and test data where possible.
- Hide or blur proxy API keys, provider credentials, passwords, JWTs, cookies,
  email addresses, and any personal or operational data.
- Do not expose browser DevTools request headers, `sessionStorage`, Kubernetes
  Secret contents, or terminal environment values.
- Use browser zoom/window sizing consistently; capture the actual UI without
  fabricated overlays or altered metrics.
- Review the image at full resolution before sharing. If redaction cannot be
  done safely, do not publish that screenshot.

## Suggested captures

- [ ] **Dashboard overview** — `dashboard-overview.png`
  - Sign in using a demo account.
  - Show the overview cards and navigation.
  - Use safe, representative data; do not imply sample values are live.

- [ ] **API-key management** — `api-key-management-redacted.png`
  - Show key names/statuses and the management UI.
  - Hide the raw secret immediately; do not capture the create-key reveal
    panel with an unredacted value.
  - Hide email/account identifiers if they are not intended for publication.

- [ ] **Playground response** — `playground-chat-response.png`
  - Submit a harmless test prompt and show the rendered response.
  - Ensure the prompt/answer do not contain private customer or provider data.
  - Avoid capturing authorization headers or console diagnostics containing
    request content.

- [ ] **Cache analytics** — `cache-analytics.png`
  - Show the actual analytics UI and the currently displayed totals.
  - Do not invent or edit metric values; identify seeded/demo data if used.

- [ ] **Kubernetes workloads and PVCs** — `kubernetes-workloads-pvcs.png`
  - Capture real `kubectl get deployments,pods,services,pvc -n ai-proxy-router`
    output or an actual Kubernetes dashboard view.
  - Redact hostnames, usernames, local file paths, and unrelated namespaces if
    they reveal information that should not be shared.
  - Never capture output that includes Secret values.

## Add captured images later

After capturing and reviewing images, place them in an intentional location
(for example, `docs/images/`) and add Markdown references here. Do not add
placeholder images or claim uncaptured screenshots exist.
