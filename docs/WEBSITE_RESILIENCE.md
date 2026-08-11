# Website resilience and deployment fallbacks

The Automation OS website is a static artifact under `site/`. GitHub is the canonical source of truth for website bytes and validation history. No hosting provider is canonical.

## Deployment tiers

1. **GitHub Pages** — preferred public mirror when repository Pages is enabled. Publication is not evidence of release promotion.
2. **Base44 Automation control plane** — optional hosted UI mirror using an existing Automation app. It must not become authority over canonical repository or release records.
3. **Portable Actions artifact** — `.github/workflows/site-artifact.yml` packages the exact validated `site/` tree plus SHA-256 manifest even when Pages is unavailable.
4. **Local / Termux server** — `python site/serve.py` or `deploy/termux/serve-site.sh` serves the same static bytes without any hosting account.

## Local execution

From a checkout:

```bash
python site/serve.py
```

Default address: `http://127.0.0.1:8080/`.

For trusted LAN access only:

```bash
python site/serve.py --bind 0.0.0.0 --port 8080
```

On Termux:

```bash
bash deploy/termux/serve-site.sh "$HOME/centinal26"
```

Set `BIND=0.0.0.0` only when LAN exposure is intentional.

## Evidence boundary

A successful website build or deployment means only that the static control surface was validated and published. It does **not** establish Android physical validation, endurance validation, device synchronization, release certification, or GA promotion.

## Failure behavior

- A Pages permission failure must not block creation of the portable artifact.
- A Base44 or Vercel outage must not alter canonical repository state.
- Local serving requires no third-party service.
- All mirrors should originate from the validated `site/` tree; provider-specific edits are non-canonical until imported back into GitHub with provenance.
