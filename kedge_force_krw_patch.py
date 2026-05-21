# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parent
script_path = ROOT / "script.js"
style_path = ROOT / "style.css"

PATCH_MARK = "K-EDGE 전체 페이지 원화 강제 패치"
STYLE_MARK = "K-EDGE 원화/레퍼럴/카드 줄 정렬 강제 보강"

patch_js = r"""
/* ===== K-EDGE 전체 페이지 원화 강제 패치 ===== */
(function(){
  function replaceTextValue(text){
    if(!text) return text;

    let t = text;

    // USD / 달러 가격만 변경. USDT는 건드리지 않음.
    t = t.replace(/월\s*26\s*USD\b/gi, "월 35,000원");
    t = t.replace(/월\s*49\s*USD\b/gi, "월 70,000원");
    t = t.replace(/월\s*70\s*USD\b/gi, "월 100,000원");

    t = t.replace(/26\s*USD\b/gi, "35,000원");
    t = t.replace(/49\s*USD\b/gi, "70,000원");
    t = t.replace(/70\s*USD\b/gi, "100,000원");

    t = t.replace(/\$26\b/g, "35,000원");
    t = t.replace(/\$49\b/g, "70,000원");
    t = t.replace(/\$70\b/g, "100,000원");

    t = t.replace(/26\s*달러/g, "35,000원");
    t = t.replace(/49\s*달러/g, "70,000원");
    t = t.replace(/70\s*달러/g, "100,000원");

    t = t.replace(/월\s*35,000원\s*상당/gi, "월 35,000원");
    t = t.replace(/월\s*70,000원\s*상당/gi, "월 70,000원");
    t = t.replace(/월\s*100,000원\s*상당/gi, "월 100,000원");

    return t;
  }

  function walkTextNodes(root){
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node){
        const p = node.parentElement;
        if(!p) return NodeFilter.FILTER_REJECT;
        const tag = p.tagName ? p.tagName.toLowerCase() : "";
        if(["script","style","textarea","input"].includes(tag)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });

    const nodes = [];
    while(walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach(node => {
      const old = node.nodeValue;
      const next = replaceTextValue(old);
      if(old !== next) node.nodeValue = next;
    });
  }

  function forceKrwPricing(){
    walkTextNodes(document.body);

    // 카드 라벨 직접 보정
    document.querySelectorAll(".label, .price-big, .pricing-table td, .pricing-table th, .service-card, .product-detail-card").forEach(el=>{
      if(el.childNodes.length === 1 && el.childNodes[0].nodeType === Node.TEXT_NODE){
        el.textContent = replaceTextValue(el.textContent);
      }
    });

    // 레퍼럴 할인 가격이 없는 페이지에는 보이는 레퍼럴 섹션에 추가
    document.querySelectorAll(".referral-obvious, .referral-banner").forEach(box=>{
      const text = box.innerText || "";
      if(text.includes("20%") && !text.includes("28,000원")){
        const div = document.createElement("div");
        div.className = "discount-line";
        div.innerHTML = `
          <span>VIP 35,000원 → 28,000원</span>
          <span>반자동 70,000원 → 56,000원</span>
          <span>자동 100,000원 → 80,000원</span>
        `;
        box.appendChild(div);
      }
    });
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", forceKrwPricing);
  }else{
    forceKrwPricing();
  }

  setTimeout(forceKrwPricing, 300);
  setTimeout(forceKrwPricing, 1200);
})();
"""

css_patch = r"""
/* ===== K-EDGE 원화/레퍼럴/카드 줄 정렬 강제 보강 ===== */
.service-card{
  display:flex!important;
  flex-direction:column!important;
}
.service-card ul{
  flex:1!important;
}
.service-card .outline{
  margin-top:auto!important;
  min-height:52px!important;
  font-size:17px!important;
}
.discount-line{
  display:flex!important;
  flex-wrap:wrap!important;
  gap:8px!important;
  margin-top:12px!important;
}
.discount-line span{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  padding:8px 12px!important;
  border-radius:999px!important;
  border:1px solid rgba(255,202,56,.42)!important;
  background:rgba(255,202,56,.10)!important;
  color:#ffca38!important;
  font-weight:950!important;
  font-size:14px!important;
  white-space:nowrap!important;
}
@media(max-width:680px){
  .service-card .outline{min-height:46px!important;font-size:15px!important}
  .discount-line span{font-size:12px!important;padding:7px 10px!important}
}
"""

if not script_path.exists():
    print("[실패] script.js 파일을 못 찾았습니다.")
else:
    text = script_path.read_text(encoding="utf-8", errors="ignore")
    if PATCH_MARK not in text:
        script_path.write_text(text.rstrip() + "\n\n" + patch_js + "\n", encoding="utf-8")
        print("[완료] script.js 원화 강제 패치 추가")
    else:
        print("[스킵] script.js 패치 이미 있음")

if not style_path.exists():
    print("[실패] style.css 파일을 못 찾았습니다.")
else:
    css = style_path.read_text(encoding="utf-8", errors="ignore")
    if STYLE_MARK not in css:
        style_path.write_text(css.rstrip() + "\n\n" + css_patch + "\n", encoding="utf-8")
        print("[완료] style.css 카드/레퍼럴 정렬 패치 추가")
    else:
        print("[스킵] style.css 패치 이미 있음")

print()
print("이제 아래 명령어 실행:")
print("git add script.js style.css")
print('git commit -m "force krw pricing on all pages"')
print("git push")
input("\n엔터 누르면 종료...")
