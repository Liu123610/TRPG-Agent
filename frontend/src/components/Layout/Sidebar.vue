<!-- frontend/src/components/Layout/Sidebar.vue -->
<template>
  <aside :class="['sidebar', { collapsed: isCollapsed }]">
    <div class="sidebar-nav">
      <button
        v-for="item in navItems"
        :key="item.id"
        :class="['nav-btn', { active: currentTab === item.id }]"
        @click="$emit('select', item.id)"
      >
        <component 
          :is="item.icon" 
          class="nav-icon"
          :size="20"
          stroke-width="1.5"
          stroke="currentColor"
          fill="none"
        />
        <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { 
  Home, 
  MessageCircle, 
  Hash, 
  Star,
  BookOpen,
  Sword,
  Trophy,
  BarChart3,
  Settings,        // 改为 Settings
  User,
  type LucideIcon
} from 'lucide-vue-next'

// 导入样式
import '../../styles_/sidebar.css'

const props = defineProps<{
  isCollapsed: boolean
  currentTab: string
}>()

const emit = defineEmits<{
  select: [tabId: string]
}>()

interface NavItem {
  id: string
  label: string
  icon: LucideIcon
}

const navItems: NavItem[] = [
  { id: 'welcome', label: '欢迎', icon: Home },
  { id: 'chat', label: '聊天助手', icon: MessageCircle },
  { id: 'page1', label: '1', icon: Hash },
  { id: 'page2', label: '2', icon: Star },
  { id: 'page3', label: '3', icon: BookOpen },
  { id: 'page4', label: '4', icon: Sword },
  { id: 'page5', label: '5', icon: Trophy },
  { id: 'page6', label: '6', icon: BarChart3 },
  { id: 'page7', label: '设置', icon: Settings },     // 改为"设置"
  { id: 'profile', label: '用户', icon: User },
]
</script>