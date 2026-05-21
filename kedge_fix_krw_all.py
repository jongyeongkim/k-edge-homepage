# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parent

replacements = {
    "월 26 USD": "월 35,000원",
    "월 49 USD": "월 70,000원",
    "월 70 USD": "월 100,000원",
    "$26": "35,000원",
    "$49": "70,000원",
    "$70": "100,000원",
    "26 USD": "35,000원",
    "49 USD": "70,000원",
    "70 USD": "100,000원",
    "VIP / BOT 상품 20% 할인": "VIP / BOT 상품 20% 할인 · VIP 28,000원 / 반자동 56,000원 / 자동 80,000원",
    "VIP / VIP+반자동 / VIP+자동 등록 시 할인 혜택을 안내합니다.": "VIP / VIP+반자동 / VIP+자동 등록 시 20% 할인 적용 · VIP 28,000원 / 반자동 56,000원 / 자동 80,000원",
}

changed_files = []

for path in ROOT.rglob("*.html"):
    if ".git" in path.parts:
        continue

    text = path.read_text(encoding="utf-8", errors="ignore")
    old = text

    for a, b in replacements.items():
        text = text.replace(a, b)

    if text != old:
        path.write_text(text, encoding="utf-8")
        changed_files.append(str(path.relative_to(ROOT)))

print("=" * 60)
print("K-EDGE 원화 가격 자동 수정 완료")
print("=" * 60)

if changed_files:
    print("수정된 파일:")
    for f in changed_files:
        print(" -", f)
else:
    print("수정된 파일 없음: 이미 원화이거나 검색 문구가 다릅니다.")

print()
print("이제 아래 명령어 실행:")
print("git add .")
print('git commit -m "fix krw pricing all pages"')
print("git push")
input("\n엔터 누르면 종료...")
