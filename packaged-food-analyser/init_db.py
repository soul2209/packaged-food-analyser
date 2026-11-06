import sys
from pathlib import Path

from app.db import init_db

target = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "instance" / "analyser.sqlite")
init_db(target)
print(f"Database ready at {target}")
