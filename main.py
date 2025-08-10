# main.py
from dotenv import load_dotenv
import cocoindex  # just to ensure it's importable
# Import the flow so CocoIndex discovers it on import:
from codeagent.pipeline.flow import build_index  # noqa: F401

# Optional: load env eagerly so CODEAGENT_ROOT/DB URL are available to the server
load_dotenv()
# Optional: init CocoIndex config (harmless if called; not required for server)
cocoindex.init()
