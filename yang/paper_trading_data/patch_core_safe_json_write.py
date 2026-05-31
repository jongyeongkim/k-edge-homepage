# -*- coding: utf-8 -*-
"""
K-EDGE core SAFE JSON WRITE patcher
실행 위치: C:\\Users\\pc1\\Desktop\\k-edge-homepage\\yang
역할:
- kedge_v9_5_2_SCAN_QUEUE_MEXC/GATE/BITGET/BINGX.py 백업 생성
- _write_json_atomic()를 WinError 5 방지 버전으로 교체
- 주문/청산/API 로직은 건드리지 않음
"""
import os
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FILES = ['kedge_v9_5_2_SCAN_QUEUE_MEXC.py', 'kedge_v9_5_2_SCAN_QUEUE_GATE.py', 'kedge_v9_5_2_SCAN_QUEUE_BITGET.py', 'kedge_v9_5_2_SCAN_QUEUE_BINGX.py']

OLD_RE = re.compile(
    r'def _write_json_atomic\(path: str, data\) -> None:\n'
    r'    os\.makedirs\(os\.path\.dirname\(path\), exist_ok=True\)\n'
    r'    tmp_path = path \+ "\.tmp"\n'
    r'    with open\(tmp_path, "w", encoding="utf-8"\) as f:\n'
    r'        json\.dump\(data, f, ensure_ascii=False, indent=2\)\n'
    r'    os\.replace\(tmp_path, path\)\n',
    re.M
)

NEW_FUNC = 'def _write_json_atomic(path: str, data) -> None:\n    """V9.5.2e SAFE JSON WRITE\n    - Windows WinError 5 방지용\n    - 고정 tmp 파일(path + ".tmp") 사용 금지\n    - 프로세스/스레드별 고유 tmp 사용\n    - .lock 파일 기반 cross-process write lock\n    - os.replace PermissionError retry\n    """\n    import uuid\n    os.makedirs(os.path.dirname(path), exist_ok=True)\n\n    lock_path = path + ".lock"\n    lock_fd = None\n    lock_started = time.time()\n    while True:\n        try:\n            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)\n            try:\n                os.write(lock_fd, f"{os.getpid()}:{threading.get_ident()}:{time.time()}".encode("utf-8"))\n            except Exception:\n                pass\n            break\n        except FileExistsError:\n            try:\n                if time.time() - os.path.getmtime(lock_path) > 10:\n                    os.remove(lock_path)\n                    continue\n            except Exception:\n                pass\n            if time.time() - lock_started > 15:\n                raise PermissionError(f"state lock timeout: {lock_path}")\n            time.sleep(0.05)\n\n    tmp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"\n    try:\n        with open(tmp_path, "w", encoding="utf-8") as f:\n            json.dump(data, f, ensure_ascii=False, indent=2)\n            f.flush()\n            try:\n                os.fsync(f.fileno())\n            except Exception:\n                pass\n\n        last_err = None\n        for i in range(20):\n            try:\n                os.replace(tmp_path, path)\n                last_err = None\n                break\n            except PermissionError as e:\n                last_err = e\n                time.sleep(0.05 + min(i * 0.03, 0.5))\n\n        if last_err is not None:\n            raise last_err\n    finally:\n        try:\n            if os.path.exists(tmp_path):\n                os.remove(tmp_path)\n        except Exception:\n            pass\n        try:\n            if lock_fd is not None:\n                os.close(lock_fd)\n        except Exception:\n            pass\n        try:\n            if os.path.exists(lock_path):\n                os.remove(lock_path)\n        except Exception:\n            pass\n\n'

def patch_file(path: Path):
    if not path.exists():
        print(f"[SKIP] missing {path.name}")
        return
    text = path.read_text(encoding="utf-8")
    if "V9.5.2e SAFE JSON WRITE" in text:
        print(f"[OK] already patched {path.name}")
        return

    backup = path.with_suffix(path.suffix + f".bak_safe_write_{time.strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(text, encoding="utf-8")

    new_text, n = OLD_RE.subn(NEW_FUNC, text)
    if n != 1:
        print(f"[FAIL] pattern not found or duplicate in {path.name} replacements={n}")
        return

    new_text = new_text.replace("K-EDGE V9.5.2", "K-EDGE V9.5.2e", 1)
    path.write_text(new_text, encoding="utf-8")
    print(f"[PATCHED] {path.name} backup={backup.name}")

def main():
    print("=" * 70)
    print("K-EDGE CORE SAFE JSON WRITE PATCH")
    print("주문/청산/API 로직 변경 없음. _write_json_atomic()만 교체.")
    print("=" * 70)
    for name in FILES:
        patch_file(BASE / name)
    print("=" * 70)
    print("완료. ORDER WORKER 재실행 후 WinError 5가 사라지는지 확인하세요.")
    print("=" * 70)

if __name__ == "__main__":
    main()
