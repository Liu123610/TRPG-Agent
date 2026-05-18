<template>
  <div class="hp-overview">
    <div v-if="hpUnits.length === 0" class="empty-state">
      暂无单位血量数据
    </div>

    <template v-else>
      <div v-if="combatActive" class="overview-banner">
        <div class="banner-copy">
          <span class="banner-label">先攻顺序</span>
          <strong>{{ activeActorLabel }}</strong>
        </div>
        <div class="banner-round">第 {{ combatRound }} 轮</div>
      </div>

      <TransitionGroup name="initiative-list" tag="div" class="hp-unit-list">
        <button
          v-for="unit in hpUnits"
          :key="unit.id"
          type="button"
          class="hp-overview-item"
          :class="{
            'is-active': unit.isCurrentActor,
            'is-enemy-turn': unit.isCurrentActor && unit.side === 'enemy',
            'is-player-turn': unit.isCurrentActor && unit.side !== 'enemy',
            'is-player-unit': unit.isPlayerUnit,
            'is-clickable': canOpenControlledActions && unit.isCurrentActor && unit.side !== 'enemy',
          }"
          :disabled="!combatActive || !unit.isCurrentActor || unit.side === 'enemy'"
          @click="handleUnitClick(unit)"
        >
          <div class="item-meta">
            <div class="meta-main">
              <span class="unit-name">{{ unit.name }}</span>
              <span v-if="unit.isCurrentActor" class="turn-badge">行动中</span>
              <span v-else-if="unit.initiativeLabel" class="initiative-badge">
                {{ unit.initiativeLabel }}
              </span>
            </div>
            <div class="meta-side">
              <span class="side-badge" :class="`side-${unit.side}`">{{ unit.sideLabel }}</span>
              <span class="hp-value">{{ unit.hp }} / {{ unit.maxHp }}</span>
            </div>
          </div>

          <HpBar
            :name="unit.name"
            :old-hp="unit.hp"
            :new-hp="unit.hp"
            :max-hp="unit.maxHp"
            compact
          />
        </button>
      </TransitionGroup>
    </template>

    <CombatActionSheet
      :open="actionSheetOpen"
      :actor-name="controlledActorName"
      :groups="actionGroups"
      :selected-target-name="selectedTargetName"
      :disabled-end-turn="!canEndCurrentTurn"
      @close="actionSheetOpen = false"
      @submit="handleActionSubmit"
      @blocked="handleActionBlocked"
      @end-turn="handleEndTurn"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CombatActionSheet from './CombatActionSheet.vue'
import HpBar from '../SideCharacterPanel/HpBar.vue'
import {
  buildCombatActionMenu,
  type CombatActionMenuGroup,
  type CombatActionMenuItem,
} from '../../../Services_/combatActionCatalog'
import type { AvailabilitySelectionUnit } from '../../../Services_/actionAvailabilityService'
import type { PlayerState } from '../../../Services_/characterStateService'

type HpOverviewUnit = {
  id: string
  name: string
  hp: number
  maxHp: number
  side: string
  sideLabel: string
  initiative: number
  initiativeRank: number | null
  initiativeLabel: string
  isCurrentActor: boolean
  isPlayerUnit: boolean
}

const props = defineProps<{
  externalPlayer: PlayerState | null
  combat?: Record<string, any> | null
  space?: Record<string, any> | null
  sceneUnits?: Record<string, any> | null
  selectedUnit?: AvailabilitySelectionUnit | null
  sendCombatActionRequest?: ((message: string) => Promise<void>) | null
  endCombatTurnRequest?: ((actorId: string) => Promise<void>) | null
}>()
const emit = defineEmits<{
  actionNotice: [text: string]
}>()

const actionSheetOpen = ref(false)
const previousCurrentActorId = ref('')

const playerUnitId = computed(() => {
  if (!props.externalPlayer) return ''
  if (props.externalPlayer.id?.trim()) return props.externalPlayer.id.trim()
  const name = props.externalPlayer.name?.trim()
  return name ? `player_${name}` : ''
})

const combatActive = computed(() => {
  const participants = props.combat?.participants
  return !!(props.combat && participants && typeof participants === 'object' && Object.keys(participants).length > 0)
})

const currentActorId = computed(() => {
  const raw = props.combat?.current_actor_id
  return typeof raw === 'string' ? raw.trim() : ''
})

const playerDisplayName = computed(() => props.externalPlayer?.name?.trim() || '玩家')

const hpUnits = computed<HpOverviewUnit[]>(() => {
  const participants = props.combat?.participants
  const initiativeOrder = Array.isArray(props.combat?.initiative_order)
    ? props.combat?.initiative_order.filter((id: unknown): id is string => typeof id === 'string' && id.trim().length > 0)
    : []
  const initiativeIndex = new Map(initiativeOrder.map((id: string, index: number) => [id, index]))
  const units: HpOverviewUnit[] = []

  if (participants && typeof participants === 'object') {
    Object.values(participants).forEach((participant) => {
      if (!participant || typeof participant !== 'object') return
      const participantRecord = participant as Record<string, any>
      const id = normalizeText(participantRecord.id)
      if (!id) return
      units.push({
        id,
        name: normalizeText(participantRecord.name) || id,
        hp: toNumber(participantRecord.hp),
        maxHp: Math.max(1, toNumber(participantRecord.max_hp)),
        side: resolveSide(normalizeText(participantRecord.side), id, playerUnitId.value),
        sideLabel: resolveSideLabel(normalizeText(participantRecord.side), id, playerUnitId.value),
        initiative: toNumber(participantRecord.initiative),
        initiativeRank: initiativeIndex.has(id) ? initiativeIndex.get(id)! : null,
        initiativeLabel: initiativeIndex.has(id) ? `先攻 #${initiativeIndex.get(id)! + 1}` : '',
        isCurrentActor: id === currentActorId.value,
        isPlayerUnit: id === playerUnitId.value,
      })
    })
  }

  if (props.externalPlayer && playerUnitId.value && !units.some((unit) => unit.id === playerUnitId.value)) {
    units.push({
      id: playerUnitId.value,
      name: props.externalPlayer.name || '玩家',
      hp: props.externalPlayer.hp || 0,
      maxHp: Math.max(1, props.externalPlayer.max_hp || 1),
      side: 'player',
      sideLabel: '玩家',
      initiative: 0,
      initiativeRank: null,
      initiativeLabel: '',
      isCurrentActor: playerUnitId.value === currentActorId.value,
      isPlayerUnit: true,
    })
  }

  return units.sort((left, right) => compareUnitOrder(left, right, currentActorId.value))
})

const combatRound = computed(() => {
  const round = props.combat?.round
  return typeof round === 'number' && Number.isFinite(round) ? round : 1
})

const activeActorLabel = computed(() => {
  const currentActor = hpUnits.value.find((unit) => unit.isCurrentActor)
  if (!currentActor) return '等待回合开始'
  return `${currentActor.name} 正在行动`
})

const currentActor = computed(() => hpUnits.value.find((unit) => unit.isCurrentActor) ?? null)

const canOpenControlledActions = computed(() => {
  const actor = currentActor.value
  return combatActive.value && !!actor && actor.side !== 'enemy'
})

const canEndCurrentTurn = computed(() => {
  const actor = currentActor.value
  return combatActive.value && !!actor && actor.side !== 'enemy' && !!props.endCombatTurnRequest
})

const controlledActorName = computed(() => currentActor.value?.name || playerDisplayName.value)

const controlledActorState = computed<PlayerState | null>(() => {
  const actor = currentActor.value
  if (!actor) return null
  if (actor.isPlayerUnit) return props.externalPlayer

  const participant = props.combat?.participants?.[actor.id]
  if (!participant || typeof participant !== 'object') return null
  return normalizeControlledActorState(participant as Record<string, any>, actor.id, actor.name, actor.side)
})

const selectedTargetName = computed(() => {
  const target = props.selectedUnit
  return target?.name?.trim() || ''
})

const actionGroups = computed<CombatActionMenuGroup[]>(() => {
  const actorState = controlledActorState.value
  if (!actorState) return []
  return buildCombatActionMenu({
    player: actorState,
    combat: props.combat ?? null,
    space: props.space ?? null,
    selectedUnit: props.selectedUnit ?? null,
  })
})

watch(
  currentActorId,
  (actorId) => {
    if (!actorId || actorId === previousCurrentActorId.value) return
    previousCurrentActorId.value = actorId
    const actor = hpUnits.value.find((unit) => unit.id === actorId)
    actionSheetOpen.value = !!actor && actor.side !== 'enemy'
  },
  { immediate: true },
)

const handleUnitClick = (unit: HpOverviewUnit) => {
  if (!unit.isCurrentActor || unit.side === 'enemy' || !canOpenControlledActions.value) return
  actionSheetOpen.value = true
}

/**
 * 中文注释：这里只负责把玩家意图送回聊天链路，不在面板层二次解析动作语义。
 */
const handleActionSubmit = async (item: CombatActionMenuItem) => {
  if (!props.sendCombatActionRequest) {
    emitActionNotice('当前聊天发送器不可用，暂时无法提交战斗动作。')
    return
  }

  actionSheetOpen.value = false
  await props.sendCombatActionRequest(item.command)
}

const handleActionBlocked = (reason: string) => {
  emitActionNotice(reason)
}

const handleEndTurn = async () => {
  if (!props.endCombatTurnRequest) {
    emitActionNotice('当前聊天发送器不可用，暂时无法提交结束回合请求。')
    return
  }
  if (!currentActor.value || currentActor.value.side === 'enemy') {
    emitActionNotice('当前不是玩家或友方单位的回合。')
    return
  }

  actionSheetOpen.value = false
  await props.endCombatTurnRequest(currentActor.value.id)
}

const emitActionNotice = (text: string) => {
  emit('actionNotice', text)
}

function compareUnitOrder(left: HpOverviewUnit, right: HpOverviewUnit, currentId: string): number {
  const leftCurrentPriority = left.id === currentId ? -1 : 0
  const rightCurrentPriority = right.id === currentId ? -1 : 0
  if (leftCurrentPriority !== rightCurrentPriority) {
    return leftCurrentPriority - rightCurrentPriority
  }

  const leftRank = left.initiativeRank ?? Number.MAX_SAFE_INTEGER
  const rightRank = right.initiativeRank ?? Number.MAX_SAFE_INTEGER
  if (leftRank !== rightRank) return leftRank - rightRank

  if (left.initiative !== right.initiative) return right.initiative - left.initiative
  return left.name.localeCompare(right.name, 'zh-Hans-CN')
}

function resolveSide(side: string, id: string, playerId: string): string {
  if (id === playerId) return 'player'
  if (side === 'ally' || side === 'enemy' || side === 'neutral') return side
  return 'ally'
}

function resolveSideLabel(side: string, id: string, playerId: string): string {
  const resolved = resolveSide(side, id, playerId)
  if (resolved === 'player') return '玩家'
  if (resolved === 'ally') return '友方'
  if (resolved === 'enemy') return '敌方'
  return '中立'
}

function normalizeText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function toNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function normalizeControlledActorState(
  participant: Record<string, any>,
  fallbackId: string,
  fallbackName: string,
  fallbackSide: string,
): PlayerState {
  // 中文注释：友方与玩家共用角色型动作菜单；缺失字段只补 UI 所需的空集合。
  return {
    id: normalizeText(participant.id) || fallbackId,
    name: normalizeText(participant.name) || fallbackName,
    role_class: normalizeText(participant.role_class),
    level: toNumber(participant.level) || 1,
    hp: toNumber(participant.hp),
    max_hp: Math.max(1, toNumber(participant.max_hp)),
    temp_hp: toNumber(participant.temp_hp),
    ac: toNumber(participant.ac) || toNumber(participant.base_ac) || 10,
    base_ac: toNumber(participant.base_ac) || undefined,
    abilities: isRecord(participant.abilities) ? participant.abilities as Record<string, number> : {},
    modifiers: isRecord(participant.modifiers) ? participant.modifiers as Record<string, number> : {},
    conditions: Array.isArray(participant.conditions) ? participant.conditions : [],
    resources: isRecord(participant.resources) ? participant.resources as Record<string, number> : {},
    weapons: Array.isArray(participant.weapons) ? participant.weapons : [],
    coins: isRecord(participant.coins) ? participant.coins as Record<string, number> : undefined,
    inventory: Array.isArray(participant.inventory) ? participant.inventory : [],
    known_spells: Array.isArray(participant.known_spells) ? participant.known_spells : [],
    known_cantrips: Array.isArray(participant.known_cantrips) ? participant.known_cantrips : [],
    spellcasting_ability: normalizeText(participant.spellcasting_ability),
    concentrating_on: typeof participant.concentrating_on === 'string' ? participant.concentrating_on : null,
    xp: typeof participant.xp === 'number' ? participant.xp : undefined,
    class_features: Array.isArray(participant.class_features) || isRecord(participant.class_features)
      ? participant.class_features
      : [],
    arcane_tradition: normalizeText(participant.arcane_tradition) || undefined,
    speed: toNumber(participant.speed) || undefined,
    movement_left: toNumber(participant.movement_left),
    action_available: participant.action_available !== false,
    extra_action_available: participant.extra_action_available === true,
    bonus_action_available: participant.bonus_action_available !== false,
    reaction_available: participant.reaction_available !== false,
    side: fallbackSide,
  } as PlayerState & { side: string }
}

function isRecord(value: unknown): value is Record<string, any> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}
</script>

<style scoped>
.hp-overview {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.overview-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(35, 29, 24, 0.96) 0%, rgba(20, 18, 17, 0.94) 100%);
  border: none;
  box-shadow:
    inset 0 12px 18px -16px rgba(255, 248, 235, 0.12),
    inset 0 -18px 24px -20px rgba(255, 248, 235, 0.08);
}

.banner-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #efe4cf;
}

.banner-label {
  color: #c6a06e;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.banner-round {
  flex-shrink: 0;
  color: #dcc092;
  font-size: 13px;
}

.hp-unit-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding-right: 6px;
  margin-top: -1px;
  border-radius: 0;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(20, 18, 17, 0.94) 0%, rgba(16, 15, 15, 0.94) 100%);
  border: none;
  box-shadow:
    inset 0 20px 24px -22px rgba(0, 0, 0, 0.2);
}

.hp-overview-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: none;
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(24, 21, 19, 0.95) 0%, rgba(18, 16, 15, 0.95) 100%);
  color: inherit;
  text-align: left;
  transition:
    transform 0.26s ease,
    background 0.26s ease,
    box-shadow 0.26s ease;
  box-shadow:
    inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
    inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
}

.hp-overview-item + .hp-overview-item {
  margin-top: 0;
}

.hp-overview-item:first-child {
  box-shadow:
    inset 0 1px 0 rgba(0, 0, 0, 0.2),
    inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
}

.hp-overview-item:last-child {
  box-shadow:
    inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
    inset 0 -1px 0 rgba(0, 0, 0, 0.18);
}

.hp-overview-item:disabled {
  opacity: 1;
}

.hp-overview-item.is-clickable {
  cursor: pointer;
}

.hp-overview-item.is-clickable:hover {
  transform: translateX(2px);
  background:
    linear-gradient(180deg, rgba(24, 21, 19, 0.96) 0%, rgba(18, 16, 15, 0.96) 100%);
  box-shadow:
    inset 0 12px 18px -16px rgba(0, 0, 0, 0.28),
    inset 0 -14px 18px -18px rgba(0, 0, 0, 0.2),
    0 0 18px rgba(209, 178, 110, 0.08);
}

.hp-overview-item.is-active {
  background:
    linear-gradient(180deg, rgba(24, 21, 19, 0.96) 0%, rgba(18, 16, 15, 0.96) 100%);
  box-shadow:
    inset 0 12px 18px -16px rgba(0, 0, 0, 0.3),
    inset 0 -14px 18px -18px rgba(0, 0, 0, 0.22);
}

.hp-overview-item.is-enemy-turn {
  box-shadow:
    inset 18px 0 30px -18px rgba(239, 68, 68, 0.5),
    inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
    inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
  animation: hostilePulse 1.8s ease-in-out infinite;
}

.hp-overview-item.is-player-turn {
  box-shadow:
    inset 18px 0 30px -18px rgba(245, 199, 103, 0.5),
    inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
    inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
  animation: allyPulse 1.8s ease-in-out infinite;
}

.item-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.meta-main,
.meta-side {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-side {
  align-items: flex-end;
}

.unit-name {
  color: #efede7;
  font-size: 15px;
  font-weight: 600;
}

.turn-badge,
.initiative-badge,
.side-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
}

.turn-badge {
  background: rgba(214, 177, 97, 0.14);
  color: #e2c68f;
}

.initiative-badge {
  background: rgba(255, 255, 255, 0.08);
  color: #b1b5bf;
}

.side-badge {
  background: rgba(255, 255, 255, 0.06);
}

.side-player,
.side-ally {
  color: #d7c08a;
}

.side-enemy {
  color: #ef8a8a;
}

.side-neutral {
  color: #bfc7d3;
}

.hp-value {
  color: #a8adba;
  font-size: 13px;
  font-family: monospace;
}

.initiative-list-move,
.initiative-list-enter-active,
.initiative-list-leave-active {
  transition: all 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.initiative-list-enter-from,
.initiative-list-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

.initiative-list-leave-active {
  position: absolute;
  width: calc(100% - 32px);
}

.empty-state {
  color: #8e8e93;
  font-style: italic;
  text-align: center;
  padding: 20px 0;
}

@keyframes hostilePulse {
  0%, 100% {
    box-shadow:
      inset 18px 0 26px -18px rgba(239, 68, 68, 0.42),
      inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
      inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
  }
  50% {
    box-shadow:
      inset 22px 0 34px -18px rgba(239, 68, 68, 0.58),
      inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
      inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
  }
}

@keyframes allyPulse {
  0%, 100% {
    box-shadow:
      inset 18px 0 26px -18px rgba(245, 199, 103, 0.42),
      inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
      inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
  }
  50% {
    box-shadow:
      inset 22px 0 34px -18px rgba(245, 199, 103, 0.58),
      inset 0 10px 14px -14px rgba(0, 0, 0, 0.28),
      inset 0 -12px 16px -16px rgba(0, 0, 0, 0.2);
  }
}

@media (max-width: 768px) {
  .overview-banner,
  .item-meta {
    flex-direction: column;
  }

  .meta-side {
    align-items: flex-start;
  }
}
</style>
