<template>
  <Teleport to="body">
    <Transition name="combat-sheet-fade">
      <div v-if="open" class="combat-sheet-overlay" @click.self="emit('close')">
        <div class="combat-sheet">
          <div class="sheet-header">
            <div>
              <div class="sheet-eyebrow">当前行动</div>
              <h4 class="sheet-title">{{ actorName }} 的动作选择</h4>
            </div>
            <button class="sheet-close" type="button" @click="emit('close')">×</button>
          </div>

          <div v-if="selectedTargetName" class="sheet-target">
            当前目标：<strong>{{ selectedTargetName }}</strong>
          </div>

          <div class="sheet-groups">
            <section v-for="group in groups" :key="group.id" class="sheet-group">
              <div class="group-title">{{ group.title }}</div>
              <div v-if="group.items.length" class="group-list">
                <button
                  v-for="item in group.items"
                  :key="item.id"
                  type="button"
                  class="action-item"
                  :class="[`accent-${item.accent}`, { disabled: !!item.disabledReason }]"
                  @click="handleItemClick(item)"
                >
                  <span class="item-main">
                    <span class="item-label">{{ item.label }}</span>
                    <span class="item-detail">{{ item.detail }}</span>
                  </span>
                  <span v-if="item.disabledReason" class="item-state">{{ item.disabledReason }}</span>
                  <span v-else class="item-state item-ready">可用</span>
                </button>
              </div>
              <div v-else class="group-empty">{{ group.emptyText }}</div>
            </section>
          </div>

          <div class="sheet-footer">
            <button
              type="button"
              class="end-turn-btn"
              :disabled="disabledEndTurn"
              @click="emit('endTurn')"
            >
              结束回合
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import type { CombatActionMenuGroup, CombatActionMenuItem } from '../../../Services_/combatActionCatalog'

const props = defineProps<{
  open: boolean
  actorName: string
  groups: CombatActionMenuGroup[]
  selectedTargetName?: string
  disabledEndTurn?: boolean
}>()

const emit = defineEmits<{
  close: []
  submit: [item: CombatActionMenuItem]
  blocked: [reason: string]
  endTurn: []
}>()

/**
 * 中文注释：动作面板只分流“可提交”和“不可提交”，具体规则仍以后端裁定为准。
 */
const handleItemClick = (item: CombatActionMenuItem) => {
  if (item.disabledReason) {
    emit('blocked', item.disabledReason)
    return
  }
  emit('submit', item)
}
</script>

<style scoped>
.combat-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 10010;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: rgba(6, 8, 11, 0.58);
  backdrop-filter: blur(10px);
  padding: 20px;
}

.combat-sheet {
  width: min(720px, 100%);
  max-height: min(82vh, 920px);
  overflow: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
  border-radius: 24px 24px 18px 18px;
  background:
    linear-gradient(180deg, rgba(23, 24, 30, 0.98) 0%, rgba(12, 13, 18, 0.98) 100%);
  border: 1px solid rgba(223, 190, 128, 0.18);
  box-shadow:
    0 24px 60px rgba(0, 0, 0, 0.42),
    0 0 0 1px rgba(255, 244, 214, 0.04) inset;
  color: #f5efe4;
}

.combat-sheet::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}

.sheet-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding: 20px 22px 12px;
}

.sheet-eyebrow {
  color: #b79a6b;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.sheet-title {
  margin: 4px 0 0;
  font-size: 22px;
  font-weight: 600;
}

.sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #d8d2c5;
  font-size: 22px;
  cursor: pointer;
}

.sheet-target {
  margin: 0 22px 16px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(201, 168, 123, 0.08);
  border: 1px solid rgba(201, 168, 123, 0.14);
  color: #dbc9ab;
  font-size: 13px;
}

.sheet-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 0 22px 16px;
}

.sheet-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-title {
  color: #cfb284;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.group-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-item {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.action-item:hover {
  transform: translateY(-1px);
}

.action-item.disabled {
  cursor: not-allowed;
  opacity: 0.78;
}

.item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-label {
  font-size: 15px;
  font-weight: 600;
}

.item-detail {
  color: #9fa4b3;
  font-size: 12px;
}

.item-state {
  max-width: 220px;
  color: #f5c7c7;
  font-size: 12px;
  text-align: right;
}

.item-ready {
  color: #d9c08b;
}

.accent-weapon {
  border-color: rgba(176, 71, 52, 0.28);
}

.accent-spell {
  border-color: rgba(71, 120, 196, 0.28);
}

.accent-item {
  border-color: rgba(134, 94, 255, 0.26);
}

.accent-class {
  border-color: rgba(199, 159, 77, 0.28);
}

.accent-combat {
  border-color: rgba(104, 126, 86, 0.28);
}

.group-empty {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
  color: #898f9d;
  font-size: 13px;
}

.sheet-footer {
  position: sticky;
  bottom: 0;
  z-index: 2;
  padding: 14px 22px 22px;
  background:
    linear-gradient(180deg, rgba(12, 13, 18, 0) 0%, rgba(12, 13, 18, 0.86) 24%, rgba(12, 13, 18, 0.98) 100%);
  backdrop-filter: blur(8px);
}

.end-turn-btn {
  width: 100%;
  min-height: 52px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.96) 0%, rgba(69, 10, 10, 0.98) 100%);
  box-shadow:
    0 12px 28px rgba(127, 29, 29, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset;
  color: #ffe3e3;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.end-turn-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(248, 113, 113, 0.44);
  box-shadow:
    0 14px 30px rgba(127, 29, 29, 0.34),
    0 0 0 1px rgba(255, 255, 255, 0.06) inset;
}

.end-turn-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  transform: none;
  box-shadow: none;
}

.end-turn-btn:active {
  transform: translateY(0);
}

.combat-sheet-fade-enter-active,
.combat-sheet-fade-leave-active {
  transition: opacity 0.22s ease;
}

.combat-sheet-fade-enter-from,
.combat-sheet-fade-leave-to {
  opacity: 0;
}

.combat-sheet-fade-enter-from .combat-sheet,
.combat-sheet-fade-leave-to .combat-sheet {
  transform: translateY(14px);
}

.combat-sheet-fade-enter-active .combat-sheet,
.combat-sheet-fade-leave-active .combat-sheet {
  transition: transform 0.22s ease;
}

@media (max-width: 640px) {
  .combat-sheet-overlay {
    padding: 12px;
  }
  .sheet-header,
  .sheet-groups,
  .sheet-footer {
    padding-left: 16px;
    padding-right: 16px;
  }
  .sheet-target {
    margin-left: 16px;
    margin-right: 16px;
  }
  .action-item {
    flex-direction: column;
    align-items: flex-start;
  }
  .item-state {
    max-width: none;
    text-align: left;
  }
}
</style>
