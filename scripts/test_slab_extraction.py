
import ezdxf
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.safe_reader import safe_readfile

dxf_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"

print(f"Testing slab extraction on: {dxf_path}")

try:
    doc = safe_readfile(dxf_path)
    extractor = StructuralExtractor(min_slab_area_m2=10.0)
    # 전체 도면에서 추출 시도 (클립 없이)
    result = extractor.extract(doc)

    print(f"\n[Extraction Result]")
    print(f"  Columns: {len(result.columns)}")
    print(f"  Beams: {len(result.beams)}")
    print(f"  Slabs: {len(result.slab_outlines)}")

    # 슬래브 결과 상세 출력
    matched_slabs = [s for s in result.slab_outlines if s.symbol != "NOSLAB"]
    print(f"\n[Slab Details (Total: {len(result.slab_outlines)}, Matched: {len(matched_slabs)})]")
    for i, s in enumerate(result.slab_outlines[:10]):
        print(f"  {i+1}. Symbol: {s.symbol}, Area: {s.area_m2:.1f}m2, Layer: {s.layer}")

    if len(result.slab_outlines) > 10:
        print(f"  ... and {len(result.slab_outlines)-10} more.")

except Exception as e:
    print(f"Error during extraction: {e}")
    import traceback
    traceback.print_exc()
