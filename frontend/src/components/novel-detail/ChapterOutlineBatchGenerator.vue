<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">章节大纲生成</h2>
        <p class="text-sm text-slate-500">基于部分大纲，批量生成详细的章节大纲</p>
      </div>
    </div>

    <!-- 生成按钮区域 -->
    <div v-if="showGenerateButton" class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl border border-blue-200 p-8 text-center">
      <div class="max-w-2xl mx-auto">
        <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        </div>
        <h3 class="text-xl font-bold text-slate-900 mb-2">
          {{ isResume ? '继续生成剩余章节大纲' : '准备生成章节大纲' }}
        </h3>
        <p class="text-sm text-slate-600 mb-2">
          <template v-if="isResume">
            检测到有 {{ pendingPartCount }} 个部分尚未完成，可以继续生成。
          </template>
          <template v-else>
            即将为 {{ totalParts }} 个部分逐个生成详细的章节大纲。
          </template>
        </p>
        <p class="text-xs text-slate-500 mb-6">
          注意：生成过程可能需要较长时间，您可以随时中断并稍后继续。<br>
          所有部分将按顺序逐个生成，确保故事情节的连贯性和质量。
        </p>
        <button
          :disabled="isGenerating || isCancelling"
          @click="startGeneration"
          class="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
        >
          <svg v-if="!isGenerating && !isCancelling" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
          <div v-else class="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          <span>{{ isCancelling ? '取消中...' : (isGenerating ? '生成中...' : (isResume ? '继续生成' : '开始生成')) }}</span>
        </button>
        <button
          v-if="isGenerating || isCancelling"
          :disabled="isCancelling"
          @click="stopGeneration"
          class="ml-3 inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg v-if="!isCancelling" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
          <div v-else class="w-5 h-5 border-2 border-slate-600 border-t-transparent rounded-full animate-spin"></div>
          <span>{{ isCancelling ? '正在取消...' : '停止生成' }}</span>
        </button>
      </div>
    </div>

    <!-- 生成中提示 -->
    <div v-if="isGenerating && currentGeneratingPart !== null && !isCancelling" class="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <div class="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin flex-shrink-0 mt-0.5"></div>
      <div class="flex-1">
        <p class="text-sm font-medium text-blue-900">正在生成第 {{ currentGeneratingPart }} 部分的章节大纲...</p>
        <p class="text-xs text-blue-700 mt-1">
          这可能需要 1-2 分钟，请耐心等待
        </p>
      </div>
    </div>

    <!-- 取消中提示 -->
    <div v-if="isCancelling" class="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <div class="w-5 h-5 border-2 border-orange-600 border-t-transparent rounded-full animate-spin flex-shrink-0 mt-0.5"></div>
      <div class="flex-1">
        <p class="text-sm font-medium text-orange-900">正在撤销生成请求...</p>
        <p class="text-xs text-orange-700 mt-1">
          后端正在取消当前生成任务，这可能需要等待当前 LLM 请求完成（最多 2 分钟）
        </p>
      </div>
    </div>

    <!-- 进度显示 -->
    <div v-if="partOutlines.length > 0" class="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-slate-900">生成进度</h3>
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-slate-600">
            {{ completedPartCount }} / {{ totalParts }} 部分已完成
          </span>
          <!-- 批量重试按钮 -->
          <button
            v-if="failedPartCount > 0 && !isGenerating && !isCancelling"
            @click="retryAllFailed"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-lg transition-colors duration-200"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            <span>重试全部失败 ({{ failedPartCount }})</span>
          </button>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="relative w-full h-3 bg-slate-100 rounded-full overflow-hidden mb-6">
        <div
          class="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-500"
          :style="{ width: `${progressPercentage}%` }"
        ></div>
      </div>

      <!-- 部分列表 -->
      <div class="space-y-3">
        <div
          v-for="part in partOutlines"
          :key="part.part_number"
          class="flex items-center justify-between p-4 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors duration-200"
        >
          <div class="flex items-center gap-3 flex-1">
            <div class="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-600 text-sm font-semibold">
              {{ part.part_number }}
            </div>
            <div class="flex-1 min-w-0">
              <h4 class="text-sm font-medium text-slate-900 truncate">{{ part.title }}</h4>
              <p class="text-xs text-slate-500">第 {{ part.start_chapter }}-{{ part.end_chapter }} 章</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <!-- 状态指示 -->
            <span
              :class="[
                'px-2.5 py-1 text-xs font-medium rounded-full flex items-center gap-1.5',
                part.generation_status === 'completed' ? 'bg-green-100 text-green-800' :
                part.generation_status === 'generating' ? 'bg-blue-100 text-blue-800' :
                part.generation_status === 'cancelling' ? 'bg-orange-100 text-orange-800' :
                part.generation_status === 'cancelled' ? 'bg-yellow-100 text-yellow-800' :
                part.generation_status === 'failed' ? 'bg-red-100 text-red-800' :
                'bg-slate-100 text-slate-600'
              ]"
            >
              <!-- 状态图标 -->
              <svg v-if="part.generation_status === 'completed'" class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
              </svg>
              <div v-else-if="part.generation_status === 'generating'" class="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
              <svg v-else-if="part.generation_status === 'failed'" class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
              </svg>
              <span>{{ getStatusText(part.generation_status) }}</span>
            </span>

            <!-- 重试按钮（仅失败时显示） -->
            <button
              v-if="part.generation_status === 'failed' && !isGenerating && !isCancelling"
              @click="retryPart(part.part_number)"
              class="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors duration-200"
            >
              重试
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 完成提示 -->
    <div v-if="allCompleted" class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <svg class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
      <div class="flex-1">
        <p class="text-sm font-medium text-green-900">全部章节大纲已生成完成</p>
        <p class="text-xs text-green-700 mt-1">
          所有 {{ totalParts }} 个部分的章节大纲已经生成完毕，您现在可以开始创作了！
        </p>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <svg class="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
      </svg>
      <div class="flex-1">
        <p class="text-sm font-medium text-red-900">生成过程中遇到错误</p>
        <p class="text-xs text-red-700 mt-1">{{ error }}</p>
        <p class="text-xs text-red-600 mt-2">
          提示：您可以点击失败部分旁边的"重试"按钮单独重试，或使用右上角的"重试全部失败"按钮批量重试。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useNovelStore } from '@/stores/novel'
import type { PartOutline } from '@/api/novel'

interface Props {
  projectId: string
}

const props = defineProps<Props>()

const novelStore = useNovelStore()
const isGenerating = ref(false)
const isCancelling = ref(false)  // 是否正在取消生成
const shouldStop = ref(false)
const error = ref<string | null>(null)
const currentGeneratingPart = ref<number | null>(null)

const project = computed(() => novelStore.currentProject)
const partOutlines = computed(() => project.value?.blueprint?.part_outlines || [])
const totalParts = computed(() => partOutlines.value.length)
const completedPartCount = computed(() =>
  partOutlines.value.filter(p => p.generation_status === 'completed').length
)
const failedPartCount = computed(() =>
  partOutlines.value.filter(p => p.generation_status === 'failed').length
)
const pendingPartCount = computed(() =>
  partOutlines.value.filter(p =>
    p.generation_status === 'pending' ||
    p.generation_status === 'failed' ||
    p.generation_status === 'cancelled'
  ).length
)
const progressPercentage = computed(() =>
  totalParts.value > 0 ? (completedPartCount.value / totalParts.value) * 100 : 0
)
const allCompleted = computed(() =>
  totalParts.value > 0 && completedPartCount.value === totalParts.value
)
const isResume = computed(() =>
  completedPartCount.value > 0 && pendingPartCount.value > 0
)
const showGenerateButton = computed(() =>
  !allCompleted.value  // 只要没有全部完成，就显示按钮区域（包括停止按钮）
)

onMounted(async () => {
  // 组件挂载时查询进度，用于中断恢复
  if (partOutlines.value.length > 0 && !allCompleted.value) {
    try {
      await novelStore.getPartOutlinesProgress()
    } catch (err) {
      console.error('查询进度失败:', err)
    }
  }
})

const startGeneration = async () => {
  isGenerating.value = true
  shouldStop.value = false
  isCancelling.value = false  // 重置取消状态
  error.value = null

  try {
    // 找到第一个未完成的部分（保证连贯性）
    const firstIncompleteIndex = partOutlines.value.findIndex(
      p => p.generation_status !== 'completed'
    )

    if (firstIncompleteIndex === -1) {
      console.log('所有部分已完成')
      return
    }

    // 从第一个未完成的部分开始，收集所有需要生成的部分
    // 这样可以保证剧情连贯性：不能跳过前面的部分直接生成后面的
    const partsToGenerate = partOutlines.value
      .slice(firstIncompleteIndex)  // 从第一个未完成的开始
      .filter(p =>
        p.generation_status === 'pending' ||
        p.generation_status === 'failed' ||
        p.generation_status === 'cancelled'  // 添加 cancelled 状态
      )
      .map(p => p.part_number)

    if (partsToGenerate.length === 0) {
      return
    }

    console.log(`从第 ${firstIncompleteIndex + 1} 部分开始，串行生成 ${partsToGenerate.length} 个部分：[${partsToGenerate.join(', ')}]`)

    // 纯串行生成所有待生成部分
    for (let i = 0; i < partsToGenerate.length; i++) {
      if (shouldStop.value) {
        console.log(`用户手动停止，已完成 ${i}/${partsToGenerate.length} 个部分`)
        break
      }

      const partNumber = partsToGenerate[i]
      currentGeneratingPart.value = partNumber

      try {
        console.log(`[${i + 1}/${partsToGenerate.length}] 开始生成第 ${partNumber} 部分...`)
        await novelStore.getPartOutlinesProgress()  // 刷新显示"生成中"
        await novelStore.generateSinglePartChapters(partNumber)
        await novelStore.getPartOutlinesProgress()  // 刷新显示结果
        console.log(`[${i + 1}/${partsToGenerate.length}] 第 ${partNumber} 部分生成完成 ✓`)
      } catch (err) {
        console.error(`[${i + 1}/${partsToGenerate.length}] 第 ${partNumber} 部分生成失败:`, err)
        error.value = `生成第${partNumber}部分失败: ${err instanceof Error ? err.message : '未知错误'}`
        await novelStore.getPartOutlinesProgress()  // 刷新状态
        // 继续生成下一个部分，不中断整个流程
      } finally {
        currentGeneratingPart.value = null
      }
    }

    // 全部完成后最终刷新进度
    await novelStore.getPartOutlinesProgress()
    console.log(`生成流程结束，共处理 ${partsToGenerate.length} 个部分`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '批量生成失败'
    console.error('批量生成章节大纲失败:', err)
  } finally {
    isGenerating.value = false
    currentGeneratingPart.value = null
  }
}

const stopGeneration = async () => {
  if (currentGeneratingPart.value === null) {
    return
  }

  const cancellingPartNumber = currentGeneratingPart.value
  isCancelling.value = true
  shouldStop.value = true

  try {
    // 调用后端API取消当前正在生成的部分
    const result = await novelStore.cancelPartGeneration(cancellingPartNumber)
    console.log(`取消第 ${cancellingPartNumber} 部分生成:`, result.message)

    // 轮询检查状态，直到取消完成
    const maxPolls = 60  // 最多轮询60次（2分钟）
    let pollCount = 0

    while (pollCount < maxPolls) {
      await new Promise(resolve => setTimeout(resolve, 2000))  // 每2秒检查一次
      await novelStore.getPartOutlinesProgress()

      // 查找当前部分的状态
      const part = partOutlines.value.find(p => p.part_number === cancellingPartNumber)
      if (part && (part.generation_status === 'cancelled' || part.generation_status === 'failed')) {
        console.log(`第 ${cancellingPartNumber} 部分已取消完成，状态: ${part.generation_status}`)
        break
      }

      pollCount++
    }

    if (pollCount >= maxPolls) {
      console.warn(`等待取消超时，停止轮询`)
    }
  } catch (err) {
    console.error(`取消第 ${cancellingPartNumber} 部分失败:`, err)
    error.value = `取消失败: ${err instanceof Error ? err.message : '未知错误'}`
  } finally {
    isCancelling.value = false
  }
}

const retryPart = async (partNumber: number) => {
  error.value = null
  try {
    await novelStore.generateSinglePartChapters(partNumber, true)
    await novelStore.getPartOutlinesProgress()
  } catch (err) {
    error.value = err instanceof Error ? err.message : `重试第${partNumber}部分失败`
    console.error(`重试第${partNumber}部分失败:`, err)
  }
}

// 批量重试所有失败的部分
const retryAllFailed = async () => {
  const failedParts = partOutlines.value
    .filter(p => p.generation_status === 'failed')
    .map(p => p.part_number)

  if (failedParts.length === 0) {
    return
  }

  error.value = null
  isGenerating.value = true

  try {
    console.log(`批量重试 ${failedParts.length} 个失败的部分`)
    for (const partNumber of failedParts) {
      if (shouldStop.value) break

      try {
        await novelStore.getPartOutlinesProgress()
        await novelStore.generateSinglePartChapters(partNumber, true)
        await novelStore.getPartOutlinesProgress()
        console.log(`第${partNumber}部分重试成功`)
      } catch (err) {
        console.error(`第${partNumber}部分重试失败:`, err)
        // 继续重试下一个
      }
    }

    await novelStore.getPartOutlinesProgress()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '批量重试失败'
  } finally {
    isGenerating.value = false
  }
}

const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '待生成',
    generating: '生成中',
    cancelling: '取消中',
    cancelled: '已取消',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[status] || status
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineBatchGenerator'
})
</script>
