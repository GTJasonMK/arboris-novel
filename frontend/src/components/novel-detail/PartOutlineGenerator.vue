<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">部分大纲</h2>
        <p class="text-sm text-slate-500">长篇小说分阶段规划，总览故事主线</p>
      </div>
    </div>

    <!-- 生成部分大纲按钮区域 -->
    <div v-if="!partOutlines || partOutlines.length === 0" class="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl border border-indigo-200 p-8 text-center">
      <div class="max-w-2xl mx-auto">
        <div class="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        </div>
        <h3 class="text-xl font-bold text-slate-900 mb-2">您的小说计划 {{ totalChapters }} 章</h3>
        <p class="text-sm text-slate-600 mb-6">
          为了更好地组织长篇小说的结构，建议先生成部分大纲。<br>
          系统将把全书分为若干部分，每部分约 {{ chaptersPerPart }} 章，便于后续分批生成详细章节大纲。
        </p>

        <!-- 生成中提示 -->
        <div v-if="isGenerating" class="mb-6 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
          <p class="text-sm font-medium text-blue-900 mb-2">正在生成部分大纲...</p>
          <p class="text-xs text-blue-700">
            这可能需要 1-2 分钟，您可以离开页面，稍后回来查看结果
          </p>
        </div>

        <button
          :disabled="isGenerating"
          @click="generatePartOutlines"
          class="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
        >
          <svg v-if="!isGenerating" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
          <div v-else class="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          <span>{{ isGenerating ? '生成中...' : '生成部分大纲' }}</span>
        </button>
      </div>
    </div>

    <!-- 部分大纲列表 -->
    <div v-else class="space-y-6">
      <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-start gap-3">
        <svg class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>
        <div class="flex-1">
          <p class="text-sm font-medium text-green-900">部分大纲已生成</p>
          <p class="text-xs text-green-700 mt-1">
            全书共 {{ totalParts }} 个部分，每部分约 {{ chaptersPerPart }} 章。接下来可以生成详细的章节大纲。
          </p>
        </div>
      </div>

      <!-- 部分大纲卡片 -->
      <div class="grid gap-4">
        <div
          v-for="part in partOutlines"
          :key="part.part_number"
          class="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-200 p-6"
        >
          <div class="flex items-start justify-between gap-4 mb-3">
            <div class="flex items-center gap-3">
              <span class="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-sm font-bold">
                {{ part.part_number }}
              </span>
              <div>
                <h3 class="text-lg font-semibold text-slate-900">{{ part.title }}</h3>
                <p class="text-xs text-slate-500">第 {{ part.start_chapter }}-{{ part.end_chapter }} 章</p>
              </div>
            </div>
            <span
              :class="[
                'px-2.5 py-1 text-xs font-medium rounded-full',
                part.generation_status === 'completed' ? 'bg-green-100 text-green-800' :
                part.generation_status === 'generating' ? 'bg-blue-100 text-blue-800' :
                part.generation_status === 'failed' ? 'bg-red-100 text-red-800' :
                'bg-slate-100 text-slate-600'
              ]"
            >
              {{ getStatusText(part.generation_status) }}
            </span>
          </div>

          <div class="space-y-3 text-sm text-slate-600">
            <p class="leading-relaxed">{{ part.summary }}</p>

            <div v-if="part.theme" class="flex items-start gap-2">
              <span class="font-medium text-slate-700 flex-shrink-0">主题：</span>
              <span>{{ part.theme }}</span>
            </div>

            <div v-if="part.key_events && part.key_events.length > 0">
              <span class="font-medium text-slate-700 block mb-1">关键事件：</span>
              <ul class="list-disc list-inside space-y-1 ml-2">
                <li v-for="(event, idx) in part.key_events" :key="idx">{{ event }}</li>
              </ul>
            </div>

            <div v-if="part.conflicts && part.conflicts.length > 0">
              <span class="font-medium text-slate-700 block mb-1">核心冲突：</span>
              <ul class="list-disc list-inside space-y-1 ml-2">
                <li v-for="(conflict, idx) in part.conflicts" :key="idx">{{ conflict }}</li>
              </ul>
            </div>

            <div v-if="part.character_arcs && Object.keys(part.character_arcs).length > 0">
              <span class="font-medium text-slate-700 block mb-1">角色弧光：</span>
              <div class="space-y-1 ml-2">
                <div v-for="(arc, character) in part.character_arcs" :key="character" class="text-xs">
                  <span class="font-medium text-slate-600">{{ character }}:</span> {{ arc }}
                </div>
              </div>
            </div>

            <div v-if="part.ending_hook" class="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <span class="font-medium text-slate-700 block mb-1 text-xs">结尾钩子：</span>
              <p class="text-xs italic">{{ part.ending_hook }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <svg class="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
      </svg>
      <div class="flex-1">
        <p class="text-sm font-medium text-red-900">生成失败</p>
        <p class="text-xs text-red-700 mt-1">{{ error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useNovelStore } from '@/stores/novel'
import type { PartOutline } from '@/api/novel'

interface Props {
  projectId: string
}

const props = defineProps<Props>()

const novelStore = useNovelStore()
const isGenerating = ref(false)
const error = ref<string | null>(null)
let pollingTimer: ReturnType<typeof setInterval> | null = null

const project = computed(() => novelStore.currentProject)
const totalChapters = computed(() => project.value?.blueprint?.total_chapters || 0)
const chaptersPerPart = computed(() => project.value?.blueprint?.chapters_per_part || 25)
const partOutlines = computed(() => project.value?.blueprint?.part_outlines || [])
const totalParts = computed(() => partOutlines.value.length)

// localStorage key for tracking generation status
const getStorageKey = () => `part_outline_generating_${props.projectId}`

// Start polling to check generation status
const startPolling = () => {
  if (pollingTimer) return

  pollingTimer = setInterval(async () => {
    try {
      await novelStore.loadProject(props.projectId, true) // force reload

      // Check if generation completed
      if (partOutlines.value.length > 0) {
        stopPolling()
        isGenerating.value = false
        localStorage.removeItem(getStorageKey())
      }
    } catch (err) {
      console.error('轮询项目状态失败:', err)
    }
  }, 5000) // Poll every 5 seconds
}

// Stop polling
const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

// Check if generation is in progress on mount
onMounted(() => {
  const generatingFlag = localStorage.getItem(getStorageKey())

  if (generatingFlag === 'true' && partOutlines.value.length === 0) {
    // Generation was in progress, resume status
    isGenerating.value = true
    startPolling()
  }
})

// Cleanup on unmount
onUnmounted(() => {
  stopPolling()
})

const generatePartOutlines = async () => {
  isGenerating.value = true
  error.value = null

  // Mark generation in progress in localStorage
  localStorage.setItem(getStorageKey(), 'true')

  try {
    await novelStore.generatePartOutlines()
    // Success - clear localStorage
    localStorage.removeItem(getStorageKey())
  } catch (err) {
    error.value = err instanceof Error ? err.message : '生成部分大纲失败'
    console.error('生成部分大纲失败:', err)
    // On error, also clear localStorage
    localStorage.removeItem(getStorageKey())
  } finally {
    isGenerating.value = false
    stopPolling()
  }
}

const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '待生成',
    generating: '生成中',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[status] || status
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'PartOutlineGenerator'
})
</script>
