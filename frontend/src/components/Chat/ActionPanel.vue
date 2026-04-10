<template>
  <!-- 掷骰确认面板 -->
  <div v-if="pendingAction?.type === 'dice_roll'" class="action-panel">
    <p><strong>动作挂起：判断需要掷骰</strong></p>
    <p>原因：{{ pendingAction.reason }} ({{ pendingAction.formula }})</p>
    <button class="roll-btn" @click="$emit('confirm')" :disabled="disabled">
      确认掷骰
    </button>
  </div>

  <!-- 玩家死亡面板 -->
  <div v-else-if="pendingAction?.type === 'player_death'" class="action-panel death-panel">
    <p class="death-title">你的角色倒下了！</p>
    <p class="death-summary" v-if="pendingAction.summary">{{ pendingAction.summary }}</p>
    <div class="death-buttons">
      <button class="revive-btn" @click="$emit('revive')" :disabled="disabled">
        复活继续（恢复一半 HP）
      </button>
      <button class="end-btn" @click="$emit('endCombat')" :disabled="disabled">
        结束战斗
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PendingAction } from '../../Services_/chatService'

defineProps<{
  pendingAction: PendingAction | null
  disabled: boolean
}>()

defineEmits<{
  confirm: []
  revive: []
  endCombat: []
}>()
</script>

<style scoped>
.action-panel {
  margin-top: 10px;
  padding: 12px;
  background: rgba(255, 165, 0, 0.15);
  border: 1px solid #ffaf40;
  border-radius: 8px;
  text-align: center;
}
.action-panel p {
  margin: 4px 0;
  font-size: 14px;
}
.roll-btn {
  margin-top: 8px;
  padding: 8px 24px;
  background: #ffaf40;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.roll-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 玩家死亡面板 */
.death-panel {
  background: rgba(239, 68, 68, 0.15);
  border-color: #ef4444;
}
.death-title {
  font-size: 16px;
  font-weight: bold;
  color: #ef4444;
}
.death-summary {
  font-size: 12px;
  color: #a1a1aa;
  max-height: 120px;
  overflow-y: auto;
  text-align: left;
  white-space: pre-wrap;
}
.death-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 10px;
}
.revive-btn {
  padding: 8px 20px;
  background: #42b883;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.end-btn {
  padding: 8px 20px;
  background: #6b7280;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
.revive-btn:disabled, .end-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>