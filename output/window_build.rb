# window_build.rb — 기준층 세대창/문 3D 생성 (골조선 끊김 기반)
#   load 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output/window_build.rb'
# 창=파랑 반투명 개구, 문=빨강. 벽 라인 따라 sill~top 높이로 박스.
require 'json'
MM = 25.4
WALL_T = 200.0          # 벽 두께(개구 깊이)
BASE = 'D:/Git/FreeCAD_4TH/.claude/worktrees/slab-precision-2026-07/output'
data = JSON.parse(File.read("#{BASE}/window_build_TYP.json"))

model = Sketchup.active_model
mat = model.materials
m_win = mat['창_개구'] || mat.add('창_개구'); m_win.color = [80, 130, 255]; m_win.alpha = 0.55
m_door = mat['문_개구'] || mat.add('문_개구'); m_door.color = [255, 90, 90]; m_door.alpha = 0.55

# 기준층 대표 z (3F=6130). 반복층은 이 개구를 각 층에 복제하면 됨.
Z_BASE = 6130.0

old = model.entities.grep(Sketchup::Group).find { |g| g.name == '창문_기준층' }
old.erase! if old
g = model.entities.add_group
g.name = '창문_기준층'
ents = g.entities

nwin = ndoor = 0
data['windows'].each do |w|
  begin
    ax = w['x1']; ay = w['y1']; bx = w['x2']; by = w['y2']
    dx = bx - ax; dy = by - ay
    len = Math.sqrt(dx*dx + dy*dy)
    next if len < 1
    # 벽 법선(개구 깊이 방향)
    nx = -dy / len * (WALL_T / 2.0)
    ny = dx / len * (WALL_T / 2.0)
    z0 = (Z_BASE + w['z0']) / MM
    z1 = (Z_BASE + w['z1']) / MM
    # 4점 밑면(벽 두께 폭)
    p1 = [(ax + nx)/MM, (ay + ny)/MM, z0]
    p2 = [(bx + nx)/MM, (by + ny)/MM, z0]
    p3 = [(bx - nx)/MM, (by - ny)/MM, z0]
    p4 = [(ax - nx)/MM, (ay - ny)/MM, z0]
    face = ents.add_face(p1, p2, p3, p4)
    next unless face && face.valid?
    face.pushpull((z1 - z0))
    door = w['is_door']
    face.material = door ? m_door : m_win
    face.all_connected.grep(Sketchup::Face).each { |f| f.material = door ? m_door : m_win }
    door ? (ndoor += 1) : (nwin += 1)
  rescue StandardError
  end
end
model.active_view.zoom_extents
puts "창 #{nwin} / 문 #{ndoor} 생성 (창문_기준층 그룹, z=#{Z_BASE})"
