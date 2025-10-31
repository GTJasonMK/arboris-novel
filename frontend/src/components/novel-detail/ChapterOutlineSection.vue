<template>
  <div class="space-y-6">
    <!-- 长篇小说（>50章）流程 -->
    <template v-if="needsPartOutlines">
      <!-- 步骤1: 生成部分大纲 -->
      <PartOutlineGenerator
        v-if="!hasPartOutlines"
        :projectId="projectId"
        :partOutlines="partOutlines"
        :totalChapters="blueprint?.total_chapters"
        :chaptersPerPart="blueprint?.chapters_per_part"
        @refresh="emit('refresh')"
      />

      <!-- 步骤2: 显示部分大纲和章节大纲管理 -->
      <template v-if="hasPartOutlines">
        <!-- 部分大纲列表 -->
        <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl border border-purple-200 p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-xl font-bold text-slate-900">部分大纲</h3>
              <p class="text-sm text-slate-600 mt-1">全书共分为 {{ partOutlines.length }} 个部分</p>
            </div>
            <div class="flex items-center gap-2">
              <div class="text-xs text-purple-600 bg-purple-100 px-3 py-1 rounded-full">
                长篇小说
              </div>
              <!-- 重新生成部分大纲按钮 -->
              <button
                @click="showPartRegenerateModal = true"
                :disabled="isRegeneratingPart"
                class="flex items-center gap-1 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg transition-all duration-200"
              >
                <div v-if="isRegeneratingPart" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>{{ isRegeneratingPart ? '生成中...' : '重新生成部分大纲' }}</span>
              </button>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="part in partOutlines"
              :key="part.part_number"
              class="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-shadow"
            >
              <div class="flex items-center justify-between mb-2">
                <h4 class="font-semibold text-slate-900">第{{ part.part_number }}部分</h4>
                <span class="text-xs text-slate-500">{{ part.start_chapter }}-{{ part.end_chapter }}章</span>
              </div>
              <p class="text-sm text-slate-600 font-medium mb-1">{{ part.title }}</p>
              <p class="text-xs text-slate-500 line-clamp-2">{{ part.summary }}</p>
            </div>
          </div>
        </div>

        <!-- 章节大纲列表 -->
        <div>
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
              <p class="text-sm text-slate-500">已生成 {{ outline.length }} / {{ blueprint?.total_chapters || 0 }} 章</p>
            </div>
            <div v-if="editable && outline.length > 0" class="flex items-center gap-2">
              <button
                type="button"
                class="flex items-center gap-1 px-3 py-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
                @click="emitEdit('chapter_outline', '章节大纲', outline)"
              >
                <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                  <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                </svg>
                编辑全部大纲
              </button>
            </div>
          </div>

          <!-- 章节大纲列表 -->
          <div v-if="outline.length > 0" class="space-y-4 mb-6">
            <ol class="relative border-l border-slate-200 ml-3 space-y-6">
              <li
                v-for="chapter in outline"
                :key="chapter.chapter_number"
                class="ml-6"
              >
                <span class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-white text-xs font-semibold">
                  {{ chapter.chapter_number }}
                </span>
                <div class="bg-white/95 rounded-xl border border-slate-200 shadow-sm p-4 hover:shadow-md transition-shadow">
                  <div class="flex items-center justify-between gap-4">
                    <h3 class="text-base font-semibold text-slate-900">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
                    <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
                  </div>
                  <p class="mt-2 text-sm text-slate-600 leading-relaxed whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
                </div>
              </li>
            </ol>
          </div>

          <!-- 空状态提示 -->
          <div v-else class="bg-blue-50 border border-blue-200 rounded-xl px-6 py-8 text-center">
            <svg class="w-12 h-12 text-blue-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p class="text-sm font-medium text-blue-900">还没有章节大纲</p>
            <p class="text-xs text-blue-700 mt-1">请使用下方的"生成大纲"按钮开始创作</p>
          </div>

          <!-- 章节大纲操作按钮（始终显示） -->
          <ChapterOutlineActions
            :projectId="projectId"
            :currentChapterCount="outline.length"
            :totalChapters="blueprint?.total_chapters || 0"
            :latestChapterNumber="latestChapterNumber"
            @refresh="emit('refresh')"
          />
        </div>
      </template>
    </template>

    <!-- 短篇小说（≤50章）流程 -->
    <template v-else>
      <!-- 一次性生成全部章节大纲 -->
      <ChapterOutlineGenerator v-if="outline.length === 0" :projectId="projectId" />

      <!-- 显示章节大纲列表 -->
      <div v-else>
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
          <div>
            <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
            <p class="text-sm text-slate-500">短篇小说 - 共 {{ outline.length }} 章</p>
          </div>
          <div v-if="editable" class="flex items-center gap-2">
            <button
              type="button"
              class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
              @click="$emit('add')"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
              </svg>
              新增章节
            </button>
            <button
              type="button"
              class="flex items-center gap-1 px-3 py-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
              @click="emitEdit('chapter_outline', '章节大纲', outline)"
            >
              <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
              </svg>
              编辑大纲
            </button>
          </div>
        </div>

        <ol class="relative border-l border-slate-200 ml-3 space-y-8">
          <li
            v-for="chapter in outline"
            :key="chapter.chapter_number"
            class="ml-6"
          >
            <span class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-white text-xs font-semibold">
              {{ chapter.chapter_number }}
            </span>
            <div class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5">
              <div class="flex items-center justify-between gap-4">
                <h3 class="text-lg font-semibold text-slate-900">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
                <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
              </div>
              <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
            </div>
          </li>
        </ol>
      </div>
    </template>

    <!-- 重新生成部分大纲对话框 -->
    <RegenerateOutlineModal
      :show="showPartRegenerateModal"
      title="重新生成部分大纲"
      description="重新规划整个故事的部分结构，您可以指定优化方向。"
      warningTitle="此操作将覆盖所有部分大纲"
      warningMessage="重新生成后，所有部分大纲和基于它们生成的章节大纲都将被替换。建议先备份重要内容。"
      :examples="partOutlineExamples"
      :isGenerating="isRegeneratingPart"
      @confirm="handleRegeneratePartOutlines"
      @cancel="showPartRegenerateModal = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, defineEmits, defineProps, ref } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { NovelAPI } from '@/api/novel'
import PartOutlineGenerator from './PartOutlineGenerator.vue'
import ChapterOutlineGenerator from './ChapterOutlineGenerator.vue'
import ChapterOutlineActions from './ChapterOutlineActions.vue'
import RegenerateOutlineModal from '../RegenerateOutlineModal.vue'
import type { Blueprint } from '@/api/novel'

interface OutlineItem {
  chapter_number: number
  title: string
  summary: string
}

interface Props {
  outline: OutlineItem[]
  editable?: boolean
  blueprint?: Blueprint | null
  projectId?: string
}

const props = withDefaults(defineProps<Props>(), {
  editable: false,
  blueprint: null,
  projectId: ''
})

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
  (e: 'refresh'): void
}>()

// 部分大纲重新生成状态
const showPartRegenerateModal = ref(false)
const isRegeneratingPart = ref(false)

// 提示词示例
const partOutlineExamples = [
  '增加整体悬念和节奏感',
  '强化角色成长弧线',
  '调整故事结构更紧凑',
  '增加情感冲突和戏剧张力',
  '优化各部分之间的衔接'
]

const needsPartOutlines = computed(() => props.blueprint?.needs_part_outlines || false)
const partOutlines = computed(() => props.blueprint?.part_outlines || [])
const hasPartOutlines = computed(() => partOutlines.value.length > 0)

// 计算最新章节编号
const latestChapterNumber = computed(() => {
  if (props.outline.length === 0) return 0
  return Math.max(...props.outline.map(c => c.chapter_number))
})

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}

// 重新生成部分大纲
const handleRegeneratePartOutlines = async (prompt: string) => {
  if (!props.projectId) {
    globalAlert.showError('项目ID不存在', '操作失败')
    return
  }

  isRegeneratingPart.value = true
  try {
    await NovelAPI.regeneratePartOutlines(props.projectId, prompt)
    globalAlert.showSuccess('部分大纲已重新生成', '生成成功')

    showPartRegenerateModal.value = false
    emit('refresh')
  } catch (err) {
    const message = err instanceof Error ? err.message : '重新生成部分大纲失败'
    globalAlert.showError(message, '操作失败')
  } finally {
    isRegeneratingPart.value = false
  }
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>
