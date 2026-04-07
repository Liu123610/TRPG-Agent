<!-- frontend/src/components/Chat/ChatMessage.vue -->
<template>
  <div :class="['message-wrapper', message.role]">
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
      <div class="message-bubble">
        <p class="message-text">{{ message.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '../../Services_/chatService'

const props = defineProps<{
  message: ChatMessage
}>()

// 头像接口（可从 message 中获取，或根据 role 配置）
const avatarUrl = computed(() => {
  // 预留头像接口
  if (props.message.avatar) return props.message.avatar
  return null
})

// 显示名称接口
const displayName = computed(() => {
  if (props.message.displayName) return props.message.displayName
  return props.message.role === 'user' ? '我' : 'TRPG 助手'
})

// 头像图标（无图片时显示）
const avatarIcon = computed(() => {
  return props.message.role === 'user' ? '👤' : '🤖'
})

// 格式化时间
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
</style>