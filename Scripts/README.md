# Project Diagnostic Scripts

Each script loads `job portal backend/config.yaml` and `job portal backend/.env`, can be run independently, and exits with status `0` on success or nonzero on failure.

Run from the repository root with the backend virtual environment:

```bash
"job portal backend/.venv/bin/python" Scripts/test_deepseek_api.py
"job portal backend/.venv/bin/python" Scripts/test_database_connection.py
"job portal backend/.venv/bin/python" Scripts/test_youtube_api.py
"job portal backend/.venv/bin/python" Scripts/test_qna_pipeline.py
"job portal backend/.venv/bin/python" Scripts/test_watermark.py
"job portal backend/.venv/bin/python" Scripts/test_r2_upload.py
"job portal backend/.venv/bin/python" Scripts/test_contact_form.py
"job portal backend/.venv/bin/python" Scripts/test_seo.py
"job portal backend/.venv/bin/python" Scripts/test_subscription.py
"job portal backend/.venv/bin/python" Scripts/sync_production_pages.py
```

For the production-equivalent Qwen3-Embedding-0.6B runtime and the same English/Roman-Urdu ranking path used by the application:

```bash
docker compose run --rm --no-deps -v "$PWD:/repo" -w /repo backend \
  python Scripts/test_qwen3_embedding.py
docker compose run --rm --no-deps -v "$PWD:/repo" -w /repo backend \
  python Scripts/test_qna_pipeline.py --title "FIA Inspector in FPSC"
```

The database script performs read-only queries using the same PostgreSQL configuration as the backend and prints a password-redacted target. The subscription script validates email rules, duplicate handling, the admin subscriber count, and editable templates without sending a digest. To test real delivery deliberately, run `Scripts/test_subscription.py --email you@example.com --send-digest`; it processes the current idempotent noon-to-noon window, so it sends nothing when that window contains no new jobs. The page sync script copies the four live production pages into the local API configured by `API_BASE_URL` and refuses remote targets by default. The API-based scripts default to `http://localhost:8000`; set `API_BASE_URL` in `.env` to use another backend. The Q&A pipeline script is a standalone live diagnostic: it independently requires video similarity ranking, transcript/comment collection, complete-content chunking, and DeepSeek extraction/ranking to pass, and prints every selected Q&A's chunk and score. These diagnostics are not included in the application API or UI. Run this model-dependent script inside the backend Docker image when the host virtualenv does not include `llama-cpp-python`. The R2 script uses the first listed job when no job ID or `TEST_JOB_POST_ID` is supplied, and deletes its test object unless `--keep` is passed. The contact script deletes its test message when the configured admin credentials can authenticate. The SEO script creates a temporary backlink and removes it directly through the configured PostgreSQL connection.
