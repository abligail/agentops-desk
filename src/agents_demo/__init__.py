# Package initializer
import os

try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass  # Allow running without dotenv if environment variables are already set

if not os.environ.get("OPENAI_API_KEY"):
    pass
    # We don't want to crash on import if just testing, unless strictly required.
    # assert os.environ["OPENAI_API_KEY"], "OPENAI_API_KEY not set"
