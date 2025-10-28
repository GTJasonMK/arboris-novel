<template>
  <div class="space-y-6">
    <!-- 长篇小说分阶段生成流程 -->
    <template v-if="needsPartOutlines">
      <!-- 阶段1: 生成部分大纲 -->
      <PartOutlineGenerator v-if="showPartOutlineGenerator" :projectId="projectId" />

      <!-- 阶段2: 批量生成章节大纲 -->
      <ChapterOutlineBatchGenerator v-if="showChapterBatchGenerator" :projectId="projectId" />

      <!-- 分隔线（如果两个组件都显示） -->
      <div v-if="showPartOutlineGenerator && showChapterBatchGenerator" class="border-t border-slate-200"></div>
    </template>

    <!-- 短篇小说: 一次性生成章节大纲 -->
    <ChapterOutlineGenerator v-if="showChapterOutlineGenerator" :projectId="projectId" />

    <!-- 短篇小说或已完成生成: 显示标准章节大纲列表 -->
    <div v-if="showStandardOutline">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
          <p class="text-sm text-slate-500">故事结构与章节节奏一目了然</p>
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
        <li v-if="!outline.length" class="ml-6 text-slate-400 text-sm">暂无章节大纲</li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineEmits, defineProps } from 'vue'
import { useNovelStore } from '@/stores/novel'
import PartOutlineGenerator from './PartOutlineGenerator.vue'
import ChapterOutlineBatchGenerator from './ChapterOutlineBatchGenerator.vue'
import ChapterOutlineGenerator from './ChapterOutlineGenerator.vue'
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
}>()

const novelStore = useNovelStore()

const needsPartOutlines = computed(() => props.blueprint?.needs_part_outlines || false)
const partOutlines = computed(() => props.blueprint?.part_outlines || [])
const hasPartOutlines = computed(() => partOutlines.value.length > 0)
const allChaptersGenerated = computed(() => {
  if (!hasPartOutlines.value) return false
  return partOutlines.value.every(p => p.generation_status === 'completed')
})

// 长篇小说显示逻辑
const showPartOutlineGenerator = computed(() => needsPartOutlines.value)
const showChapterBatchGenerator = computed(() => needsPartOutlines.value && hasPartOutlines.value)

// 短篇小说显示逻辑：不需要部分大纲 且 还没有章节大纲
const showChapterOutlineGenerator = computed(() => !needsPartOutlines.value && props.outline.length === 0)

// 标准章节大纲列表显示逻辑：短篇已有大纲 或 长篇所有部分已完成
const showStandardOutline = computed(() => {
  if (!needsPartOutlines.value) {
    // 短篇小说：有章节大纲就显示
    return props.outline.length > 0
  } else {
    // 长篇小说：所有部分的章节都生成完成才显示
    return allChaptersGenerated.value
  }
})

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>
