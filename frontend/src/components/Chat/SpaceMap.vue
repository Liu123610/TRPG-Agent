<template>
  <section class="space-map">
    <div class="map-header">
      <div>
        <div class="section-title">战术地图</div>
        <div v-if="activeMap" class="map-subtitle">
          {{ activeMap.name }} · {{ formatNumber(activeMap.width) }}x{{ formatNumber(activeMap.height) }} 尺
        </div>
      </div>
      <button
        class="clear-selection-btn"
        type="button"
        :disabled="!selectedUnit"
        title="清除选择"
        @click="selectedUnitId = null"
      >
        <X :size="14" stroke-width="1.8" />
      </button>
    </div>

    <div v-if="!activeMap" class="empty-map">
      暂无地图数据
    </div>

    <div v-else class="map-shell">
      <svg
        class="map-canvas"
        :viewBox="`0 0 ${viewBoxWidth} ${viewBoxHeight}`"
        role="img"
        :aria-label="`${activeMap.name} 平面地图`"
      >
        <rect
          class="map-bg"
          :x="0"
          :y="0"
          :width="viewBoxWidth"
          :height="viewBoxHeight"
          rx="0"
        />
        <path
          v-for="line in gridLines"
          :key="line.key"
          class="grid-line"
          :d="line.path"
        />
        <g
          v-for="unit in visibleUnits"
          :key="unit.id"
          class="unit-node"
          :class="[{ selected: unit.id === selectedUnitId }, unit.sideClass]"
          role="button"
          tabindex="0"
          :aria-label="`${unit.name} 坐标 ${formatNumber(unit.x)}, ${formatNumber(unit.y)}`"
          @click="selectedUnitId = unit.id"
          @keydown.enter.prevent="selectedUnitId = unit.id"
          @keydown.space.prevent="selectedUnitId = unit.id"
        >
          <circle class="unit-aura" :cx="unit.screenX" :cy="unit.screenY" :r="unit.selected ? 9 : 7" />
          <circle class="unit-dot" :cx="unit.screenX" :cy="unit.screenY" :r="4" />
          <text class="unit-label" :x="unit.screenX" :y="unit.screenY - 8">
            {{ unit.initial }}
          </text>
        </g>
      </svg>
      <div class="axis-row">
        <span>0,0</span>
        <span>{{ formatNumber(activeMap.width) }},{{ formatNumber(activeMap.height) }}</span>
      </div>
    </div>

    <div v-if="selectedUnit" class="unit-detail">
      <div class="unit-detail-head">
        <span class="unit-name">{{ selectedUnit.name }}</span>
        <span class="unit-id">{{ selectedUnit.id }}</span>
      </div>
      <div class="detail-grid">
        <div>
          <span>坐标</span>
          <strong>({{ formatNumber(selectedUnit.x) }}, {{ formatNumber(selectedUnit.y) }})</strong>
        </div>
        <div>
          <span>阵营</span>
          <strong>{{ sideLabel(selectedUnit.side) }}</strong>
        </div>
        <div v-if="selectedUnit.hp !== undefined">
          <span>生命值</span>
          <strong>{{ selectedUnit.hp }} / {{ selectedUnit.max_hp ?? '?' }}</strong>
        </div>
        <div v-if="selectedUnit.ac !== undefined">
          <span>护甲</span>
          <strong>{{ selectedUnit.ac }}</strong>
        </div>
      </div>
      <div v-if="selectedUnit.conditions.length" class="condition-line">
        <span v-for="condition in selectedUnit.conditions" :key="condition" class="mini-condition">
          {{ condition }}
        </span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

type Point = {
  x?: number
  y?: number
}

type Placement = {
  unit_id: string
  map_id: string
  position: Point
  facing_deg?: number
}

type PlaneMap = {
  id: string
  name: string
  width: number
  height: number
  grid_size?: number
}

type UnitInfo = {
  id: string
  name?: string
  side?: string
  hp?: number
  max_hp?: number
  ac?: number
  conditions?: Array<{ id?: string; name_cn?: string }>
}

type VisibleUnit = {
  id: string
  name: string
  side: string
  sideClass: string
  initial: string
  x: number
  y: number
  screenX: number
  screenY: number
  selected: boolean
  hp?: number
  max_hp?: number
  ac?: number
  conditions: string[]
}

const props = defineProps<{
  space: any | null
  player: any | null
  combat?: any | null
  sceneUnits?: Record<string, any> | null
}>()

const selectedUnitId = ref<string | null>(null)

const activeMap = computed<PlaneMap | null>(() => {
  const space = props.space
  if (!space?.maps || !space.active_map_id) return null
  return space.maps[space.active_map_id] ?? null
})

const viewBoxWidth = computed(() => Math.max(1, Number(activeMap.value?.width ?? 1)))
const viewBoxHeight = computed(() => Math.max(1, Number(activeMap.value?.height ?? 1)))

const unitsById = computed<Record<string, UnitInfo>>(() => {
  const result: Record<string, UnitInfo> = {}

  if (props.sceneUnits) {
    Object.entries(props.sceneUnits).forEach(([id, unit]) => {
      result[id] = { ...(unit as UnitInfo), id }
    })
  }

  if (props.combat?.participants) {
    Object.entries(props.combat.participants).forEach(([id, unit]) => {
      result[id] = { ...(unit as UnitInfo), id }
    })
  }

  if (props.player) {
    const playerId = props.player.id || `player_${props.player.name || 'player'}`
    result[playerId] = { id: playerId, ...props.player, side: 'player' }
  }

  return result
})

const visibleUnits = computed<VisibleUnit[]>(() => {
  const map = activeMap.value
  const placements = props.space?.placements ?? {}
  if (!map) return []

  return Object.entries(placements)
    .map(([unitId, rawPlacement]) => {
      const placement = rawPlacement as Placement
      const x = Number(placement.position?.x ?? 0)
      const y = Number(placement.position?.y ?? 0)
      const info = unitsById.value[unitId] ?? { id: unitId }
      const side = info.side || 'neutral'
      const name = info.name || unitId
      const selected = unitId === selectedUnitId.value

      return {
        id: unitId,
        name,
        side,
        sideClass: sideClass(side),
        initial: name.slice(0, 1).toUpperCase(),
        x,
        y,
        screenX: clamp(x, 0, map.width),
        screenY: clamp(map.height - y, 0, map.height),
        selected,
        hp: info.hp,
        max_hp: info.max_hp,
        ac: info.ac,
        conditions: (info.conditions ?? []).map((condition) => condition.name_cn || condition.id || '?'),
      }
    })
    .filter((unit) => (props.space?.placements?.[unit.id] as Placement | undefined)?.map_id === map.id)
})

const selectedUnit = computed(() => {
  return visibleUnits.value.find((unit) => unit.id === selectedUnitId.value) ?? visibleUnits.value[0] ?? null
})

const gridLines = computed(() => {
  const map = activeMap.value
  if (!map) return []

  const step = Math.max(5, Number(map.grid_size || 5))
  const lines: Array<{ key: string; path: string }> = []

  for (let x = step; x < map.width; x += step) {
    lines.push({ key: `x-${x}`, path: `M ${x} 0 L ${x} ${map.height}` })
  }
  for (let y = step; y < map.height; y += step) {
    lines.push({ key: `y-${y}`, path: `M 0 ${y} L ${map.width} ${y}` })
  }

  return lines
})

watch(visibleUnits, (units) => {
  if (selectedUnitId.value && units.some((unit) => unit.id === selectedUnitId.value)) return
  selectedUnitId.value = units[0]?.id ?? null
}, { immediate: true })

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const formatNumber = (value: number | undefined) => {
  if (value === undefined || Number.isNaN(value)) return '?'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

const sideLabel = (side: string) => {
  if (side === 'player') return '玩家'
  if (side === 'ally') return '友方'
  if (side === 'enemy') return '敌方'
  return '中立'
}

const sideClass = (side: string) => {
  if (side === 'player') return 'side-player'
  if (side === 'ally') return 'side-ally'
  if (side === 'enemy') return 'side-enemy'
  return 'side-neutral'
}
</script>

<style scoped>
.space-map {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.map-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.section-title {
  color: #c9a87b;
  font-size: 14px;
  font-weight: 600;
}

.map-subtitle {
  margin-top: 3px;
  color: #a1a1aa;
  font-size: 12px;
}

.clear-selection-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0.5px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  border-radius: 6px;
  cursor: pointer;
}

.clear-selection-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.map-shell {
  width: 100%;
}

.map-canvas {
  width: 100%;
  aspect-ratio: 1 / 1;
  max-height: 260px;
  display: block;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: #17181d;
}

.map-bg {
  fill: #191b21;
}

.grid-line {
  fill: none;
  stroke: rgba(255, 255, 255, 0.08);
  stroke-width: 0.55;
  vector-effect: non-scaling-stroke;
}

.unit-node {
  cursor: pointer;
  outline: none;
}

.unit-aura {
  fill: rgba(255, 255, 255, 0.08);
  stroke: rgba(255, 255, 255, 0.25);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.unit-dot {
  stroke: rgba(0, 0, 0, 0.65);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.unit-label {
  fill: #f8fafc;
  font-size: 4px;
  font-weight: 700;
  text-anchor: middle;
  paint-order: stroke;
  stroke: rgba(0, 0, 0, 0.75);
  stroke-width: 1.3;
  pointer-events: none;
}

.unit-node.selected .unit-aura {
  fill: rgba(250, 204, 21, 0.18);
  stroke: #facc15;
}

.side-player .unit-dot {
  fill: #38bdf8;
}

.side-ally .unit-dot {
  fill: #22c55e;
}

.side-enemy .unit-dot {
  fill: #ef4444;
}

.side-neutral .unit-dot {
  fill: #a78bfa;
}

.axis-row {
  display: flex;
  justify-content: space-between;
  color: #71717a;
  font-size: 11px;
  margin-top: 4px;
}

.unit-detail {
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px;
}

.unit-detail-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.unit-name {
  color: #f4f4f5;
  font-size: 14px;
  font-weight: 700;
}

.unit-id {
  color: #71717a;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.detail-grid div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.detail-grid span {
  color: #8e8e93;
  font-size: 11px;
}

.detail-grid strong {
  color: #e5e7eb;
  font-size: 13px;
  font-weight: 600;
}

.condition-line {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}

.mini-condition {
  padding: 2px 6px;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.16);
  border-radius: 6px;
  font-size: 11px;
}

.empty-map {
  color: #8e8e93;
  font-size: 13px;
  text-align: center;
  padding: 18px 0;
}
</style>
