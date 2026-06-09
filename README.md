# Python_Repos
Practical Git task repository

## Git Practical Task
Completed by Thami on 2026-02-02
- Created feature branch
- Practiced commits and pull requests

---

## Weekly Neuroradiology Digest

Automated weekly digest of newly published neuroradiology-relevant articles from:
- **AJNR: American Journal of Neuroradiology**
- **AJNR: Clinical Practice** (classified from AJNR by article type)
- **Neuroimaging Clinics of North America**
- **RadioGraphics**

Runs every **Monday at 06:00 UTC** via GitHub Actions. For each article it provides: journal, title, article type, publication date, direct DOI link, and a 2–3 sentence practical summary. Closes with a "Most Practice-Relevant This Week" section ranking the top 3 papers for a working neuroradiologist.

### Setup

1. **Add the Anthropic API key** as a repository secret named `ANTHROPIC_API_KEY`
   - Settings → Secrets and variables → Actions → New repository secret

2. *(Optional)* Add `NCBI_EMAIL` secret with your email to identify requests to NCBI's servers.

3. The workflow (`weekly-neuroradiology-digest.yml`) commits each digest as `digests/digest_YYYY-MM-DD.md`.

### Manual run

Trigger on-demand via **Actions → Weekly Neuroradiology Digest → Run workflow**.

### Local run

```bash
pip install -r neuroradiology_digest/requirements.txt
ANTHROPIC_API_KEY=your_key python neuroradiology_digest/digest.py
```

### Output

Digests are saved in `digests/`. See [`digests/digest_2026-06-09.md`](digests/digest_2026-06-09.md) for a sample.
