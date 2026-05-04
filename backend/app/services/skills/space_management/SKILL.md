# 平面空间管理技能

当剧情进入一个可探索、可交互或可能发生冲突的空间时，使用本技能维护客观地图与单位落点。玩家只是闲聊、纯角色扮演或抽象过场时，可以自然回应而不更新地图。

## 入口工具

统一使用 `manage_space`。不要直接调用旧的 `create_plane_map`、`switch_plane_map`、`place_unit`、`move_unit`、`remove_unit`、`measure_distance`、`query_units_in_radius`；这些只保留给历史调用兼容。

## 动作速查

- 创建地图：`action="create_map"`，传 `payload={"name": 名称, "width": 宽度尺, "height": 高度尺}`，可选 `grid_size`、`description`、`activate`。
- 切换地图：`action="switch_map"`，传 `payload={"map_id": 地图ID}`。
- 放置单位：`action="place_unit"`，传 `payload={"unit_id": 单位ID, "x": x坐标, "y": y坐标}`，可选 `map_id`、`facing_deg`、`footprint_radius`、`reason`。
- 移动单位：`action="move_unit"`，传 `payload={"unit_id": 单位ID, "x": 目标x, "y": 目标y}`。
- 自主靠近目标：`action="approach_unit"`，传 `payload={"unit_id": 行动单位ID, "target_id": 目标单位ID}`；可选 `desired_distance`，或传 `attack_name` 让系统按该攻击的射程/触及距离自动靠近。
- 移除单位：`action="remove_unit"`，传 `payload={"unit_id": 单位ID}`，或 `payload={"unit_ids": [单位ID...]}`。
- 测量距离：`action="measure_distance"`，传 `payload={"source_id": 起点单位ID, "target_id": 目标单位ID}`。
- 范围查询：`action="query_radius"`，传 `payload={"x": 圆心x, "y": 圆心y, "radius": 半径尺}`，可选 `map_id`。

## 使用原则

- 探索阶段进入新房间、道路、洞穴、营地等具体空间时，应先确认 HUD 中是否已有当前地图；没有则创建地图，有则按需要切换地图或放置单位。
- 战斗开始前必须有当前平面地图，并且所有参战单位都已放置在当前地图上；`start_combat` 会拒绝缺地图或缺落点的战斗。
- 常规战斗地图默认按 1 格 = 5 尺理解，常见遭遇可先用 30x30 格到 40x40 格；若空间太小会挤爆站位，太大则会让距离和范围失去戏剧性。
- 剧情初始化、传送、推搡后的强制落点、怪物入场，用 `place_unit`；它不消耗移动力。
- 战斗中主动移动单位，用 `move_unit`；它会校验当前回合并扣除 `movement_left`。
- 战斗中怪物需要接近玩家时，优先用 `approach_unit`，不要先测距再手算坐标再移动；该动作会一次性移动到可达的合适距离，并扣除 `movement_left`。
- 战斗结束后，默认先清理死亡单位的空间落点，再保留死亡档案供搜刮、辨认或后续剧情引用。
- 只有需要从地图中真正移除单位时，使用 `remove_unit`；不要用把单位塞到角落的方式假装清理。
- 只需要判断距离或范围时，不要移动单位，先用 `measure_distance` 或 `query_radius`。
- 地图 ID 和单位 ID 优先从 HUD 读取；HUD 不足时再用 `inspect_unit` 查询单位信息。
- 不要为纯对话、回忆、远景介绍等没有可操作空间的位置频繁创建地图。
