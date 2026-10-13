"""Keep the suite offline even when a developer has configured a project .env file."""

import os


# These values are process-local to pytest and take precedence over .env because
# the production loader intentionally uses override=False.
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""
os.environ["STAGE2_EMBEDDING_PROVIDER"] = "deterministic"
