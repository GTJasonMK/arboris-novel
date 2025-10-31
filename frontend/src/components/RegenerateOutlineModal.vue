<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
        @click.self="handleCancel"
      >
        <div class="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
          <!-- 头部 -->
          <div class="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 rounded-t-2xl">
            <div class="flex items-center justify-between">
              <h3 class="text-xl font-bold text-slate-900">{{ title }}</h3>
              <button
                @click="handleCancel"
                class="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <p v-if="description" class="mt-2 text-sm text-slate-600">{{ description }}</p>
          </div>

          <!-- 内容 -->
          <div class="px-6 py-5 space-y-4">
            <!-- 警告提示 -->
            <div class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-start gap-3">
              <svg class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              <div class="flex-1">
                <p class="text-sm font-medium text-amber-900">{{ warningTitle }}</p>
                <p class="text-xs text-amber-700 mt-1">{{ warningMessage }}</p>
              </div>
            </div>

            <!-- 提示词输入 -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">
                优化方向（可选）
              </label>
              <textarea
                v-model="promptText"
                rows="4"
                placeholder="例如：增加更多悬念、强化角色冲突、加快节奏..."
                class="w-full px-4 py-3 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
              />
            </div>

            <!-- 示例提示 -->
            <div v-if="examples.length > 0" class="space-y-2">
              <p class="text-xs font-medium text-slate-600">常用示例（点击快速填入）：</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="(example, index) in examples"
                  :key="index"
                  @click="promptText = example"
                  class="px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
                >
                  {{ example }}
                </button>
              </div>
            </div>
          </div>

          <!-- 底部按钮 -->
          <div class="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 rounded-b-2xl flex justify-end gap-3">
            <button
              @click="handleCancel"
              :disabled="isGenerating"
              class="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              取消
            </button>
            <button
              @click="handleConfirm"
              :disabled="isGenerating"
              class="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg transition-all duration-200 flex items-center gap-2"
            >
              <div v-if="isGenerating" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{{ isGenerating ? '生成中...' : '确认重新生成' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  show: boolean
  title: string
  description?: string
  warningTitle?: string
  warningMessage?: string
  examples?: string[]
  isGenerating?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  description: '',
  warningTitle: '注意',
  warningMessage: '重新生成将覆盖当前内容，此操作不可撤销。',
  examples: () => [],
  isGenerating: false
})

const emit = defineEmits<{
  confirm: [prompt: string]
  cancel: []
}>()

const promptText = ref('')

// 监听 show 变化，打开时清空输入
watch(() => props.show, (newVal) => {
  if (newVal) {
    promptText.value = ''
  }
})

const handleConfirm = () => {
  emit('confirm', promptText.value.trim())
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .bg-white,
.modal-leave-active .bg-white {
  transition: transform 0.2s ease;
}

.modal-enter-from .bg-white,
.modal-leave-to .bg-white {
  transform: scale(0.95);
}
</style>
