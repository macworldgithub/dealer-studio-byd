"""Background task entry point with a credential-free execution receipt."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run():
    receipt = {'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    code = 0
    try:
        import httpx
        from dealerstudio_session import main, atomic_json, SessionBusy, AuthenticationRequired
        try:
            main()
            receipt['status'] = 'succeeded'
        except SessionBusy:
            receipt['status'] = 'busy'
        except Exception as error:
            code = 1
            receipt.update(status='failed', error=type(error).__name__, message='Dealer Studio could not be reached.' if isinstance(error, httpx.RequestError) else str(error))
        receipt['finishedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        atomic_json(ROOT / '.runtime/task-status.json', receipt)
    except Exception as error:
        code = 1
        # Even dependency/bootstrap failures leave a useful receipt without a traceback.
        file = ROOT / '.runtime/task-status.json'
        file.parent.mkdir(exist_ok=True)
        file.write_text(json.dumps({**receipt, 'status': 'failed', 'error': type(error).__name__, 'message': str(error)}), encoding='utf8')
    return code


if __name__ == '__main__':
    sys.exit(run())
