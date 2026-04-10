<!-- frontend/src/components/Chat/ChatMessage.vue -->
<template>
  <!-- 调试消息：仅调试模式可见 -->
  <div v-if="message.type === 'tool'" v-show="debugMode" class="tool-message-wrapper">
    <div class="tool-badge">TOOL</div>
    <pre class="tool-content">{{ message.content }}</pre>
  </div>

  <!-- 普通消息 / 战斗动作消息 -->
  <div v-else :class="['message-wrapper', message.role]">
    <!-- 头像区域 -->
    <div class="avatar">
      <img v-if="avatarUrl" :src="avatarUrl" :alt="displayName" />
      <div v-else class="avatar-placeholder">
        {{ avatarIcon }}
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="message-content-wrapper">
      <div class="message-header">
        <span class="display-name">{{ displayName }}</span>
        <span class="timestamp">{{ formatTime(message.timestamp) }}</span>
      </div>
      <div class="message-bubble" :class="{ 'combat-bubble': message.type === 'combat_action' }">
        <p v-if="message.content" class="message-text">{{ message.content }}</p>
        <!-- HP 血条动画 -->
        <HpBar
          v-for="(hpc, i) in hpChanges"
          :key="i"
          :name="hpc.name"
          :old-hp="hpc.old_hp"
          :new-hp="hpc.new_hp"
          :max-hp="hpc.max_hp"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import type { ChatMessage } from '../../Services_/chatService'
import HpBar from './HpBar.vue'

const props = defineProps<{
  message: ChatMessage
}>()

// 由 Chatpages 通过 provide 注入
const debugMode = inject<boolean>('debugMode', false)

const hpChanges = computed(() => props.message.metadata?.hp_changes ?? [])

const avatarUrl = computed(() => props.message.avatar ?? null)

const displayName = computed(() => {
  if (props.message.displayName) return props.message.displayName
  return props.message.role === 'user' ? '我' : 'TRPG 助手'
})

const avatarIcon = computed(() => props.message.role === 'user' ? '👤' : '🤖')

const formatTime = (timestamp?: string | number) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}
</script>

<style scoped>
.message-wrapper {
  display: flex;
  gap: 12px;
  padding: 16px 0;
  max-width: 100%;
}

/* 用户消息：头像在右，右对齐 */
.message-wrapper.user {
  flex-direction: row-reverse;
}

.message-wrapper.user .message-content-wrapper {
  align-items: flex-end;
}

.message-wrapper.user .message-header {
  flex-direction: row-reverse;
}

.message-wrapper.user .message-bubble {
  background: rgba(66, 184, 131, 0.15);
  border: 0.5px solid rgba(66, 184, 131, 0.3);
}

/* AI 消息：头像在左，左对齐 */
.message-wrapper.assistant {
  flex-direction: row;
}

.message-wrapper.assistant .message-bubble {
  background: rgba(45, 45, 55, 0.8);
  border: 0.5px solid rgba(255, 255, 255, 0.1);
}

/* 头像 */
.avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(66, 184, 131, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

/* 内容区域 */
.message-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: calc(100% - 48px);
}

/* 消息头部 */
.message-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 6px;
}

.display-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5e5ea;
}

.timestamp {
  font-size: 11px;
  color: #6c6c70;
}

/* 消息气泡 */
.message-bubble {
  padding: 10px 14px;
  border-radius: 16px;
  border-top-left-radius: 4px;
  max-width: 100%;
  word-wrap: break-word;
}

.message-wrapper.user .message-bubble {
  border-top-left-radius: 16px;
  border-top-right-radius: 4px;
}

.message-text {
  margin: 0;
  line-height: 1.5;
  font-size: 14px;
  color: #e5e5ea;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 消息列表容器样式（供父组件使用） */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

/* 战斗动作气泡 */
.combat-bubble {
  border-left: 3px solid #f59e0b !important;
}

/* 调试工具消息 */
.tool-message-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 16px;
  margin: 4px 0;
}

.tool-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(139, 92, 246, 0.3);
  color: #a78bfa;
  letter-spacing: 0.5px;
}

.tool-content {
  margin: 0;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #8e8e93;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(255, 255, 255, 0.03);
  padding: 6px 10px;
  border-radius: 6px;
  max-width: 100%;
  overflow-x: auto;
}
</style>