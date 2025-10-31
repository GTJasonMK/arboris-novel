<template>
  <div class="bg-gradient-to-r from-slate-50 to-blue-50 rounded-2xl border border-slate-200 p-6 space-y-6">
    <!-- 标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-lg font-bold text-slate-900">章节大纲管理</h3>
        <p class="text-sm text-slate-600 mt-1">
          已生成 <span class="font-semibold text-indigo-600">{{ currentChapterCount }}</span> / {{ totalChapters }} 章大纲
        </p>
      </div>
      <div class="flex items-center gap-2 text-xs text-slate-500">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>灵活管理大纲</span>
      </div>
    </div>

    <!-- 操作按钮组 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- 1. 生成后续章节大纲 -->
      <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          <h4 class="font-semibold text-slate-900">生成大纲</h4>
        </div>
        <p class="text-xs text-slate-600">从第{{ currentChapterCount + 1 }}章开始生成</p>
        <div class="flex items-center gap-2">
          <input
            v-model.number="generateCount"
            type="number"
            min="1"
            :max="remainingChapters"
            placeholder="数量"
            class="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
          />
          <button
            @click="handleGenerate"
            :disabled="isGenerating || generateCount < 1 || generateCount > remainingChapters"
            class="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg transition-all duration-200 flex items-center gap-1"
          >
            <div v-if="isGenerating" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            <span>{{ isGenerating ? '生成中' : '生成' }}</span>
          </button>
        </div>
        <p v-if="remainingChapters === 0" class="text-xs text-amber-600">已生成全部章节</p>
        <p v-else class="text-xs text-slate-500">剩余 {{ remainingChapters }} 章可生成</p>
      </div>

      <!-- 2. 删除最新章节大纲 -->
      <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          <h4 class="font-semibold text-slate-900">删除大纲</h4>
        </div>
        <p class="text-xs text-slate-600">删除最新的N章大纲</p>
        <div class="flex items-center gap-2">
          <input
            v-model.number="deleteCount"
            type="number"
            min="1"
            :max="currentChapterCount"
            placeholder="数量"
            class="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          />
          <button
            @click="handleDelete"
            :disabled="isDeleting || deleteCount < 1 || deleteCount > currentChapterCount"
            class="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg transition-all duration-200 flex items-center gap-1"
          >
            <div v-if="isDeleting" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            <span>{{ isDeleting ? '删除中' : '删除' }}</span>
          </button>
        </div>
        <p v-if="currentChapterCount === 0" class="text-xs text-amber-600">暂无章节大纲</p>
        <p v-else class="text-xs text-slate-500">当前共 {{ currentChapterCount }} 章</p>
      </div>

      <!-- 3. 重新生成最新章节 -->
      <div class="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-cyan-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <h4 class="font-semibold text-slate-900">重新生成</h4>
        </div>
        <p class="text-xs text-slate-600">重新生成第{{ latestChapterNumber }}章大纲</p>
        <button
          @click="showRegenerateModal = true"
          :disabled="isRegenerating || currentChapterCount === 0"
          class="w-full px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg transition-all duration-200 flex items-center justify-center gap-2"
        >
          <div v-if="isRegenerating" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          <span>{{ isRegenerating ? '生成中' : '重新生成' }}</span>
        </button>
        <p class="text-xs text-slate-500">可添加优化提示词</p>
      </div>
    </div>

    <!-- 重新生成对话框 -->
    <RegenerateOutlineModal
      :show="showRegenerateModal"
      :title="`重新生成第${latestChapterNumber}章大纲`"
      :description="`仅重新生成最新的第${latestChapterNumber}章大纲，不影响其他章节。`"
      warningTitle="此操作将覆盖该章节大纲"
      warningMessage="重新生成后，该章节的当前大纲将被替换。如果已生成章节内容，不会受影响。"
      :examples="regenerateExamples"
      :isGenerating="isRegenerating"
      @confirm="handleRegenerate"
      @cancel="showRegenerateModal = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { NovelAPI } from '@/api/novel'
import RegenerateOutlineModal from '../RegenerateOutlineModal.vue'

interface Props {
  projectId: string
  currentChapterCount: number
  totalChapters: number
  latestChapterNumber: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  refresh: []
}>()

// 状态
const generateCount = ref(10)
const deleteCount = ref(1)
const isGenerating = ref(false)
const isDeleting = ref(false)
const isRegenerating = ref(false)
const showRegenerateModal = ref(false)

// 计算剩余章节数
const remainingChapters = computed(() => props.totalChapters - props.currentChapterCount)

// 重新生成提示词示例
const regenerateExamples = [
  '增加转折点',
  '强化情感冲突',
  '加快节奏',
  '增加悬念',
  '丰富场景描写',
  '深化角色刻画'
]

// 生成后续章节大纲
const handleGenerate = async () => {
  if (generateCount.value < 1 || generateCount.value > remainingChapters.value) {
    globalAlert.showError('生成数量超出范围', '参数错误')
    return
  }

  const confirmed = await globalAlert.showConfirm(
    `确定要生成后续 ${generateCount.value} 章大纲吗？将从第 ${props.currentChapterCount + 1} 章开始生成。`,
    '确认生成'
  )

  if (!confirmed) return

  isGenerating.value = true
  try {
    await NovelAPI.generateChapterOutlinesByCount(props.projectId, generateCount.value)
    globalAlert.showSuccess(`已生成后续 ${generateCount.value} 章大纲`, '生成成功')

    emit('refresh')
  } catch (err) {
    const message = err instanceof Error ? err.message : '生成章节大纲失败'
    globalAlert.showError(message, '操作失败')
  } finally {
    isGenerating.value = false
  }
}

// 删除最新章节大纲
const handleDelete = async () => {
  if (deleteCount.value < 1 || deleteCount.value > props.currentChapterCount) {
    globalAlert.showError('删除数量超出范围', '参数错误')
    return
  }

  const startChapter = props.latestChapterNumber - deleteCount.value + 1
  const endChapter = props.latestChapterNumber

  const confirmed = await globalAlert.showConfirm(
    `确定要删除第 ${startChapter} 到第 ${endChapter} 章大纲吗？此操作不可撤销。`,
    '确认删除'
  )

  if (!confirmed) return

  isDeleting.value = true
  try {
    const result = await NovelAPI.deleteLatestChapterOutlines(props.projectId, deleteCount.value)

    let successMessage = `已删除最新 ${deleteCount.value} 章大纲`
    if (result.warning) {
      successMessage += `\n警告：${result.warning}`
    }

    globalAlert.showSuccess(successMessage, '删除成功')

    emit('refresh')
  } catch (err) {
    const message = err instanceof Error ? err.message : '删除章节大纲失败'
    globalAlert.showError(message, '操作失败')
  } finally {
    isDeleting.value = false
  }
}

// 重新生成最新章节
const handleRegenerate = async (prompt: string) => {
  isRegenerating.value = true
  try {
    await NovelAPI.regenerateChapterOutline(props.projectId, props.latestChapterNumber, prompt)
    globalAlert.showSuccess(`第 ${props.latestChapterNumber} 章大纲已重新生成`, '生成成功')

    showRegenerateModal.value = false
    emit('refresh')
  } catch (err) {
    const message = err instanceof Error ? err.message : '重新生成章节大纲失败'
    globalAlert.showError(message, '操作失败')
  } finally {
    isRegenerating.value = false
  }
}
</script>
