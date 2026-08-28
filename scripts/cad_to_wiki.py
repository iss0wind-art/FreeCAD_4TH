"""
이천 CAD 파서 — .fcstd / .step → 피지수 wiki 노트 변환
부재·치수·제약 관계를 백링크([[링크]])로 변환 → Graphify 구체 프렉탈
"""

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

FREECAD_DIR = Path(__file__).parent.parent
PHYSIS_WIKI = Path("/home/nas/AG-Forge/physis_memory/wiki")
PHYSIS_LOG = Path("/home/nas/AG-Forge/physis_memory/wiki/log.md")


def parse_fcstd(fcstd_path: Path) -> dict:
    """FreeCAD 파일에서 객체 목록과 관계 추출"""
    objects = {}
    try:
        with zipfile.ZipFile(fcstd_path, "r") as z:
            if "Document.xml" not in z.namelist():
                return {}
            xml_content = z.read("Document.xml").decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [오류] {fcstd_path.name}: {e}")
        return {}

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return {}

    for obj in root.iter("Object"):
        name = obj.get("name", "")
        obj_type = obj.get("type", "")
        if name:
            objects[name] = {"type": obj_type, "links": []}

    # 링크 관계 추출
    for prop in root.iter("Property"):
        prop_name = prop.get("name", "")
        if prop_name in ("Base", "Profile", "Tool", "Shape"):
            parent = None
            # 부모 객체 찾기
            for obj in root.iter("Object"):
                for child in obj:
                    if child == prop:
                        parent = obj.get("name")
                        break
            link_el = prop.find(".//Link")
            if link_el is not None and parent:
                target = link_el.get("value", "")
                if target and parent in objects:
                    objects[parent]["links"].append(target)

    return objects


def to_wiki_note(fcstd_path: Path, objects: dict) -> str:
    """파싱 결과를 마크다운 노트로 변환"""
    now = datetime.now().strftime("%Y-%m-%d")
    name = fcstd_path.stem
    lines = [
        f"---",
        f"type: cad_model",
        f"source: {fcstd_path.name}",
        f"created: {now}",
        f"ref_count: 0",
        f"outcome_score: 0.0",
        f"---",
        f"",
        f"# {name}",
        f"",
        f"> 출처: `{fcstd_path.name}` — 이천 3지국 FreeCAD 자동 파싱",
        f"",
        f"## 구성 부재 ({len(objects)}개)",
        f"",
    ]

    for obj_name, info in list(objects.items())[:30]:  # 최대 30개
        obj_type = info["type"].split("::")[-1] if "::" in info["type"] else info["type"]
        links = info["links"]
        link_str = " ".join(f"[[{l}]]" for l in links) if links else ""
        lines.append(f"- **{obj_name}** ({obj_type}) {link_str}")

    lines += [
        f"",
        f"## 연결",
        f"",
        f"- [[홍익인간]]",
        f"- [[구체_프렉탈_원리]]",
        f"- [[{name}_BOQ]]",  # 정도전 BOQ와 연결 예약
    ]

    return "\n".join(lines)


def parse_step(step_path: Path) -> dict:
    """STEP 파일에서 엔티티 추출 (ISO 10303-21)"""
    objects = {}
    try:
        text = step_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    # PRODUCT 엔티티 추출
    for m in re.finditer(r"PRODUCT\('([^']+)'", text):
        name = m.group(1).strip()
        if name and name not in ("", " "):
            objects[name] = {"type": "PRODUCT", "links": []}

    # NEXT_ASSEMBLY_USAGE 관계 추출 (어셈블리 계층)
    for m in re.finditer(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\([^,]*,'([^']*)'[^,]*,'([^']*)'", text):
        parent, child = m.group(1).strip(), m.group(2).strip()
        if parent in objects:
            objects[parent]["links"].append(child)

    return objects


def convert_all():
    """FreeCAD_4TH의 모든 .fcstd + .step → 피지수 wiki 노트"""
    fcstd_files = list(FREECAD_DIR.glob("**/*.fcstd")) + list(FREECAD_DIR.glob("**/*.FCStd"))
    step_files = [p for p in FREECAD_DIR.glob("output/**/*.step") if p.stat().st_size < 50_000_000]
    all_files = fcstd_files + step_files
    converted = 0

    print(f"[이천 CAD 파서] .fcstd {len(fcstd_files)}개 + .step {len(step_files)}개")

    for path in all_files:
        print(f"  파싱 중: {path.name}")
        objects = parse_step(path) if path.suffix.lower() == ".step" else parse_fcstd(path)
        if not objects:
            print(f"  → 건너뜀 (객체 없음)")
            continue

        note = to_wiki_note(path, objects)
        out_path = PHYSIS_WIKI / f"CAD_{path.stem}.md"
        out_path.write_text(note, encoding="utf-8")
        print(f"  → {out_path.name} ({len(objects)}개 객체)")
        converted += 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(PHYSIS_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n- [{now}] 이천 CAD 파싱: {converted}개 노트 생성")

    print(f"\n완료 — {converted}개 wiki 노트 생성")


if __name__ == "__main__":
    convert_all()
