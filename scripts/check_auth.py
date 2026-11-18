"""Print OAuth setup readiness and callback URLs, never credential values."""
from pathlib import Path
import sys
from dotenv import load_dotenv
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
load_dotenv(root / '.env')
from backend.auth.auth import AuthManager

def main():
    try:
        auth = AuthManager()
    except ValueError as exc:
        print(f'Authentication configuration error: {exc}')
        return 1
    for provider, configured in auth.providers.items():
        print(f'{provider.title()}: {"credentials present (not live-verified)" if configured else "missing client ID or secret"}')
        print(f'  Callback: {auth.base_url}/api/auth/callback/{provider}')
    print('Setup instructions: AUTH_SETUP.md')
    return 0 if all(auth.providers.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
