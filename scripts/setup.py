"""Generate a local secret once; never checked into source control."""
from pathlib import Path
import secrets
path = Path(__file__).resolve().parents[1] / ".env"
try:
    with path.open("x") as file:
        file.write(f"TOKEN_SECRET={secrets.token_hex(32)}\n")
    path.chmod(0o600)
    print("Created .env")
except FileExistsError:
    print("Keeping existing .env")
