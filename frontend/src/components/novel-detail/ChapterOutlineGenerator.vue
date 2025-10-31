<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
        <p class="text-sm text-slate-500">快速生成完整的章节规划</p>
      </div>
    </div>

    <!-- 生成章节大纲按钮区域 -->
    <div v-if="!hasChapterOutlines" class="bg-gradient-to-r from-blue-50 to-cyan-50 rounded-2xl border border-blue-200 p-8 text-center">
      <div class="max-w-2xl mx-auto">
        <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        </div>
        <h3 class="text-xl font-bold text-slate-900 mb-2">您的小说计划 {{ totalChapters }} 章</h3>
        <p class="text-sm text-slate-600 mb-6">
          蓝图已准备就绪，现在可以生成详细的章节大纲。<br>
          系统将基于您的世界观、角色设定和主线剧情，为每一章生成具体的情节规划。
        </p>
        <button
          :disabled="isGenerating"
          @click="generateChapterOutlines"
          class="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
        >
          <svg v-if="!isGenerating" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
          <div v-else class="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          <span>{{ isGenerating ? '生成中...' : '生成章节大纲' }}</span>
        </button>
      </div>
    </div>

    <!-- 章节大纲已生成提示 -->
    <div v-else class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <svg class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
      <div class="flex-1">
        <p class="text-sm font-medium text-green-900">章节大纲已生成</p>
        <p class="text-xs text-green-700 mt-1">
          共 {{ totalChapters }} 章大纲已准备就绪，您可以在下方的"章节大纲"区域查看详情，或前往写作台开始创作。
        </p>
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

    <!-- 成功提示 -->
    <div v-if="successMessage" class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <svg class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
      <div class="flex-1">
        <p class="text-sm font-medium text-green-900">生成成功</p>
        <p class="text-xs text-green-700 mt-1">{{ successMessage }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useNovelStore } from '@/stores/novel'
import { NovelAPI } from '@/api/novel'
import {
  GenerationType,
  markGenerationStart,
  markGenerationComplete,
  isGenerating as checkIsGenerating
} from '@/utils/generationState'

interface Props {
  projectId: string
}

const props = defineProps<Props>()

const novelStore = useNovelStore()
const isGenerating = ref(false)
const error = ref<string | null>(null)
const successMessage = ref<string | null>(null)

const project = computed(() => novelStore.currentProject)
const totalChapters = computed(() => project.value?.blueprint?.total_chapters || 0)
const hasChapterOutlines = computed(() => {
  // 检查数据库中是否已有章节大纲（通过章节数量判断）
  const chapters = project.value?.chapters || []
  return chapters.length > 0
})

const generateChapterOutlines = async () => {
  isGenerating.value = true
  error.value = null
  successMessage.value = null

  // 标记生成开始（状态持久化）
  markGenerationStart(GenerationType.CHAPTER_OUTLINE, props.projectId)

  try {
    const result = await NovelAPI.generateAllChapterOutlines(props.projectId)
    successMessage.value = result.message

    // 重新加载项目数据以获取最新的章节大纲
    await novelStore.loadProject(props.projectId)

    // 标记生成完成
    markGenerationComplete(GenerationType.CHAPTER_OUTLINE, props.projectId)
    isGenerating.value = false

    // 3秒后清除成功消息
    setTimeout(() => {
      successMessage.value = null
    }, 3000)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '生成章节大纲失败'
    console.error('生成章节大纲失败:', err)
    markGenerationComplete(GenerationType.CHAPTER_OUTLINE, props.projectId)
    isGenerating.value = false
  }
}

// 组件挂载时检查是否有未完成的生成状态
onMounted(() => {
  // 如果已经有章节大纲，清除可能存在的生成状态
  if (hasChapterOutlines.value) {
    markGenerationComplete(GenerationType.CHAPTER_OUTLINE, props.projectId)
    return
  }

  // 检查是否正在生成
  const { generating, elapsed } = checkIsGenerating(GenerationType.CHAPTER_OUTLINE, props.projectId, 5 * 60 * 1000)
  if (generating) {
    console.log(`恢复章节大纲生成状态（已等待 ${elapsed}ms）`)
    isGenerating.value = true
  }
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineGenerator'
})
</script>
