import json

data = json.load(open('output/members_accumulated.json', encoding='utf-8'))
members = data['members']

# 대략적인 위치(50m 단위)로 클러스터링
clusters = {}
for m in members:
    x_grid = int(m['x'] / 50000) * 50000
    y_grid = int(m['y'] / 50000) * 50000
    z_grid = int(m.get('z_bot', 0) / 1000) * 1000
    key = (x_grid, y_grid, z_grid)
    if key not in clusters:
        clusters[key] = {'count': 0, 'sources': set(), 'types': set(), 'sample_ids': []}
    clusters[key]['count'] += 1
    clusters[key]['sources'].add(m.get('source'))
    clusters[key]['types'].add(m.get('type'))
    if len(clusters[key]['sample_ids']) < 3:
        clusters[key]['sample_ids'].append(m['id'])

print('Clusters (50m resolution):')
for k, v in sorted(clusters.items(), key=lambda item: item[1]['count'], reverse=True):
    sources = list(v['sources'])
    types = list(v['types'])
    print(f'Pos X={k[0]}, Y={k[1]}, Z={k[2]}: Count={v["count"]}, Sources={sources}, Types={types}, Samples={v["sample_ids"]}')
