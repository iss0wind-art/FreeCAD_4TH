"""
test_codex.py — 자가 학습 코덱스 검증 스크립트
=============================================
1. G1 (500x600) 라벨을 통해 코덱스가 학습되는지 확인.
2. 치수 없는 G1 라벨이 코덱스 정보를 가져오는지 확인.
"""
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.codex import ProjectCodex

def test_codex_learning():
    codex = ProjectCodex()
    extractor = StructuralExtractor(codex=codex)
    
    print("--- Phase 1: Learning ---")
    name1, w1, h1 = extractor._parse_beam_label("2G1 500x600")
    print(f"Input: '2G1 500x600' -> Parsed: {name1}, {w1}x{h1}")
    print(f"Codex State: {codex.report()}")
    
    print("\n--- Phase 2: Inference ---")
    name2, w2, h2 = extractor._parse_beam_label("G1")
    print(f"Input: 'G1' (Dimension missing) -> Inferred: {name2}, {w2}x{h2}")
    
    if w2 == 500 and h2 == 600:
        print("\n[SUCCESS] Self-Learning Codex is working perfectly!")
    else:
        print("\n[FAIL] Inference failed.")

if __name__ == "__main__":
    test_codex_learning()
