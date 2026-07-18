from __future__ import annotations

"""Run the staged SMTP diagnostic with the current backend environment.

For production, execute the copy built into the Container App so it uses the
secret reference without downloading or printing that secret:

    az containerapp exec --name job-portal-api \\
      --resource-group job-portal-prod-rg \\
      --command "python -m app.services.smtp_diagnostic --send"
"""

from common import add_backend_to_path


if __name__ == "__main__":
    add_backend_to_path()
    from app.services.smtp_diagnostic import main

    raise SystemExit(main())
