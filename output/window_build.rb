# window_build.rb v2 — 세대창/문 진짜 오픈 (sill~top만 열고 상하부 벽 채움)
#   load 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output/window_build.rb'
# v1 오류: 벽두께 꽉찬 solid 박스가 이미 열린 개구를 도로 메꿈.
# v2: 골조선 끊김 = 바닥~천장 통째 열림 → sill아래 역보 / top위 인방보로 벽 채우고
#     sill~top 개구에만 얇은 유리. 문은 열어둠(개구 유지).
require 'json'
MM = 25.4
BASE = 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output'
data = JSON.parse(File.read("#{BASE}/window_build_TYP.json"))

Z_BASE  = 6130.0   # 3F 바닥
STOREY  = 2830.0   # 층고 (3F 벽 z 6130~8960)
WALL_T  = 200.0    # 벽/보 두께
GLASS_T = 40.0     # 유리 두께

model = Sketchup.active_model
model.start_operation('win_v2', true)
mat = model.materials
m_glass = mat['유리'] || mat.add('유리'); m_glass.color = [120,170,255]; m_glass.alpha = 0.30
m_lint  = mat['인방보'] || mat.add('인방보'); m_lint.color = [190,170,140]
m_sill  = mat['역보'] || mat.add('역보'); m_sill.color = [170,150,120]

old = model.entities.grep(Sketchup::Group).find { |g| g.name == '창문_기준층' }
old.erase! if old
g = model.entities.add_group; g.name = '창문_기준층'
ents = g.entities

# 벽 라인 따라 z0~z1 박스 (두께 t, 벽 중심 정렬) — 독립 서브그룹으로 생성
def slab_box(parent, ax, ay, bx, by, z0, z1, t, mm, material)
  dx = bx-ax; dy = by-ay; ln = Math.hypot(dx,dy)
  return nil if ln < 1 || (z1-z0).abs < 1
  nx = -dy/ln*t/2; ny = dx/ln*t/2
  pts = [[ax+nx,ay+ny,z0],[bx+nx,by+ny,z0],[bx-nx,by-ny,z0],[ax-nx,ay-ny,z0]]
        .map { |x,y,z| [x/mm, y/mm, z/mm] }
  sub = parent.add_group
  f = sub.entities.add_face(pts)
  unless f && f.valid?
    sub.erase!; return nil
  end
  f.reverse! if f.normal.z < 0
  f.pushpull((z1-z0)/mm)
  sub.entities.grep(Sketchup::Face).each { |x| x.material = material }
  sub
end

# 중복 개구 제거 (같은 자리 50mm 격자)
seen = {}
uniq = data['windows'].reject { |w|
  k = [ (w['x1']/50).round, (w['y1']/50).round, (w['x2']/50).round,
        (w['y2']/50).round, (w['z0']/50).round, (w['z1']/50).round ]
  seen[k] ? true : (seen[k] = true; false)
}

nglass = ndoor = nlint = nsill = 0
uniq.each do |w|
  ax,ay,bx,by = w['x1'], w['y1'], w['x2'], w['y2']
  s = w['z0'].to_f; t = w['z1'].to_f
  door = w['is_door']
  # 하부 역보/허리벽 (창 sill 아래) — 문은 없음
  if !door && s > 50
    nsill += 1 if slab_box(ents, ax,ay,bx,by, Z_BASE, Z_BASE+s, WALL_T, MM, m_sill)
  end
  # 상부 인방보 (top 위 ~ 천장)
  if t < STOREY - 50
    nlint += 1 if slab_box(ents, ax,ay,bx,by, Z_BASE+t, Z_BASE+STOREY, WALL_T, MM, m_lint)
  end
  # 개구부 sill~top: 창은 얇은 유리, 문은 열어둠(빈 개구)
  if !door
    nglass += 1 if slab_box(ents, ax,ay,bx,by, Z_BASE+s, Z_BASE+t, GLASS_T, MM, m_glass)
  else
    ndoor += 1
  end
end
model.commit_operation
puts "유리창 #{nglass} / 문(빈개구) #{ndoor} / 인방보 #{nlint} / 역보 #{nsill}  (중복제거 #{data['windows'].length - uniq.length})"
