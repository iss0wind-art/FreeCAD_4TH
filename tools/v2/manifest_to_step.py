"""
manifest_to_step.py — .boq.yaml → STEP + BOQ CLI (v4 P7)
==========================================================
freecadcmd 환경 필요.

사용:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tools/v2/manifest_to_step.py \\
      --manifest output/v2/<id>/manifest.boq.yaml \\
      --out-dir output/v2/<id>/
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))


def main():
    # 환경변수로 입력 (freecadcmd argparse 충돌 회피)
    manifest_path = Path(os.environ.get("V2_MANIFEST", ""))
    out_dir = Path(os.environ.get("V2_OUT_DIR", ""))
    if not manifest_path.exists():
        raise RuntimeError(f"V2_MANIFEST 환경변수 누락 또는 파일 없음: {manifest_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 출력 stdout flush
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print(f"manifest_to_step: {manifest_path}")
    print("=" * 60)

    # 1. Manifest 로드 + 검증
    from core.manifest_parser import parse_manifest
    text = manifest_path.read_text(encoding="utf-8")
    manifest = parse_manifest(text)
    print(f"Manifest 로드: {len(manifest.members)} members, {len(manifest.floors)} floors")

    # 2. spec_lookup 생성 — 다양한 spec 패턴 + catalog.yaml 병합
    import re
    import yaml as _yaml

    spec_lookup: dict = {}

    # 2-a. catalog.yaml (있으면) — BEAM matched (RG3 등), SLAB labels (A,B,...) 등
    cat_path = manifest_path.parent / "catalog.yaml"
    if cat_path.exists():
        try:
            catalog = _yaml.safe_load(cat_path.read_text(encoding="utf-8")) or {}
            for sym, info in catalog.items():
                if not isinstance(info, dict):
                    continue
                w = info.get("width_mm"); h = info.get("height_mm")
                mt = info.get("member_type")
                if mt == "slab":
                    # SLAB 카탈로그는 width_mm 에 두께
                    spec_lookup[sym] = {"thickness_mm": float(w or 0)}
                elif mt == "wall":
                    spec_lookup[sym] = {"thickness_mm": float(w or 0)}
                else:
                    spec_lookup[sym] = {
                        "width_mm": float(w or 0),
                        "height_mm": float(h or w or 0),
                    }
            print(f"catalog.yaml 적용: {len(catalog)}건")
        except Exception as e:
            print(f"catalog 로드 실패: {e}")

    # 2-b. members[].spec 패턴 자동 추출
    auto_pat = re.compile(r"AUTO-([A-Z]+)-T?(\d+)(?:[xX](\d+))?")
    meas_pat = re.compile(r"(COL|FND|WALL|SLAB)-MEAS-T?(\d+)(?:[xX](\d+))?", re.IGNORECASE)
    slab_lab_pat = re.compile(r"^SLAB-([A-Z0-9]+)-T(\d+)$", re.IGNORECASE)
    slab_unv_pat = re.compile(r"^SLAB-T(\d+)-UNVERIFIED$", re.IGNORECASE)
    slab_unm_pat = re.compile(r"^SLAB-([A-Z0-9]+)-UNMATCHED$", re.IGNORECASE)

    for m in manifest.members:
        sp = m.spec
        if sp in spec_lookup:
            continue

        # COL-MEAS-WxH / FND-MEAS-WxH / WALL-MEAS-TX / SLAB-MEAS-...
        ms = meas_pat.match(sp)
        if ms:
            t, w, h = ms.group(1).upper(), float(ms.group(2)), ms.group(3)
            if t in ("WALL", "SLAB"):
                spec_lookup[sp] = {"thickness_mm": w}
            else:
                spec_lookup[sp] = {"width_mm": w, "height_mm": float(h or w)}
            continue

        # SLAB-A-T450 / SLAB-S12-T200
        ml = slab_lab_pat.match(sp)
        if ml:
            spec_lookup[sp] = {"thickness_mm": float(ml.group(2))}
            continue

        # SLAB-T150-UNVERIFIED
        mu = slab_unv_pat.match(sp)
        if mu:
            spec_lookup[sp] = {"thickness_mm": float(mu.group(1))}
            continue

        # SLAB-S12-UNMATCHED → 폴백 두께 150
        mn = slab_unm_pat.match(sp)
        if mn:
            spec_lookup[sp] = {"thickness_mm": 150.0}
            continue

        # 기존 AUTO-XXX-... 패턴
        mt = auto_pat.match(sp)
        if mt:
            t, w, h = mt.group(1), float(mt.group(2)), mt.group(3)
            if t in ("WALL", "SLAB"):
                spec_lookup[sp] = {"thickness_mm": w}
            else:
                spec_lookup[sp] = {"width_mm": w, "height_mm": float(h or w)}

    print(f"spec_lookup: {len(spec_lookup)}건")

    # 3. STEP 빌드
    t0 = time.time()
    from core.v2.build.build_pipeline import build_step_from_manifest
    step_out = out_dir / f"{manifest.project.id}.step"
    print(f"\n[STEP 빌드] {step_out}")
    report = build_step_from_manifest(manifest, step_out, spec_lookup=spec_lookup)
    print(f"  솔리드 {report.succeeded}/{report.total_members} ({report.failed} 실패)")
    print(f"  by_type: {report.by_type}")
    print(f"  파일: {Path(step_out).stat().st_size//1024} KB")

    # 4. BOQ
    print("\n[BOQ]")
    from core.v2.build.manifest_resolver import resolve
    from core.v2.boq.exporter import export_boq_csv, export_boq_json
    from core.v2.boq.quantity_calc import compute_quantity

    resolved = resolve(manifest, spec_lookup=spec_lookup)
    quantities = [compute_quantity(r) for r in resolved]

    boq_json = out_dir / "boq.json"
    boq_csv = out_dir / "boq.csv"
    export_boq_json(quantities, boq_json, project_id=manifest.project.id)
    export_boq_csv(quantities, boq_csv)
    print(f"  JSON: {boq_json} ({boq_json.stat().st_size//1024} KB)")
    print(f"  CSV:  {boq_csv} ({boq_csv.stat().st_size//1024} KB)")

    print(f"\n소요: {time.time()-t0:.1f}s")


# freecadcmd 환경에서 직접 호출
main()
