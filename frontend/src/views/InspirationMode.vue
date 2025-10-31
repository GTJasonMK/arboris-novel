<template>
  <div class="flex items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-6xl mx-auto">
      <!-- 灵感模式入口界面 -->
      <div v-if="!conversationStarted" class="text-center p-8 bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg fade-in">
        <h1 class="text-4xl md:text-5xl font-bold text-gray-800">小说家的新篇章</h1>
        <p class="text-lg text-gray-600 mt-4 mb-8">
          准备好释放你的创造力了吗？让AI引导你，一步步构建出独一无二的故事世界。
        </p>
        <button
          @click="startConversation"
          :disabled="novelStore.isLoading"
          class="bg-indigo-500 text-white font-bold py-3 px-8 rounded-full hover:bg-indigo-600 transition-all duration-300 transform hover:scale-105 shadow-lg focus:outline-none focus:ring-4 focus:ring-indigo-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ novelStore.isLoading ? '正在准备...' : '开启灵感模式' }}
        </button>
        <button
          @click="goBack"
          class="mt-4 block mx-auto text-gray-500 hover:text-gray-800 transition-colors"
        >
          返回
        </button>
      </div>

      <!-- 灵感模式交互界面 -->
      <div
        v-else-if="!showBlueprintConfirmation && !showBlueprint"
        class="h-[90vh] max-h-[950px] flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden fade-in"
      >
        <!-- 头部 -->
        <div class="p-4 border-b border-gray-200">
          <div class="flex justify-between items-center">
            <div class="flex items-center gap-2">
              <span class="relative flex h-3 w-3">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
              </span>
              <span class="text-sm font-medium text-indigo-600">与“文思”对话中...</span>
            </div>
            <div class="flex items-center gap-4">
              <span v-if="currentTurn > 0" class="text-sm font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded-md">
                第 {{ currentTurn }} 轮
              </span>
              <!-- 手动生成蓝图按钮（当对话进行到一定轮次时显示） -->
              <button
                v-if="currentTurn >= 5 && !showBlueprintConfirmation && !showBlueprint"
                @click="handleManualGenerateBlueprint"
                title="已收集足够信息，可直接生成蓝图"
                class="text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 px-3 py-1.5 rounded-lg transition-all duration-200 shadow-sm hover:shadow-md flex items-center gap-1.5"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
                </svg>
                生成蓝图
              </button>
              <button
                @click="handleRestart"
                title="重新开始"
                class="text-gray-400 hover:text-indigo-600 transition-colors"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
              </button>
              <button
                @click="exitConversation"
                title="返回首页"
                class="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 聊天区域 -->
        <div class="flex-1 p-6 overflow-y-auto space-y-6 relative" ref="chatArea">
          <transition name="fade">
            <InspirationLoading v-if="isInitialLoading" />
          </transition>
          <ChatBubble
            v-for="(message, index) in chatMessages"
            :key="index"
            :message="message.content"
            :type="message.type"
          />
        </div>

        <!-- 输入区域 -->
        <div class="p-4 border-t border-gray-200 bg-gray-50">
          <ConversationInput
            :ui-control="currentUIControl"
            :loading="novelStore.isLoading"
            @submit="handleUserInput"
          />
        </div>
      </div>

      <!-- 蓝图确认界面 -->
      <BlueprintConfirmation
        v-if="showBlueprintConfirmation"
        :ai-message="confirmationMessage"
        @blueprint-generated="handleBlueprintGenerated"
        @back="backToConversation"
        @restart-conversation="handleRestartConversation"
      />

      <!-- 大纲展示界面 -->
      <BlueprintDisplay
        v-if="showBlueprint"
        :blueprint="completedBlueprint"
        :ai-message="blueprintMessage"
        :is-refining="isRefiningBlueprint"
        @confirm="handleConfirmBlueprint"
        @regenerate="handleRegenerateBlueprint"
        @refine="handleRefineBlueprint"
        @restart-conversation="handleRestartConversation"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import type { UIControl, Blueprint } from '@/api/novel'
import { ProjectStatus } from '@/types/enums'
import ChatBubble from '@/components/ChatBubble.vue'
import ConversationInput from '@/components/ConversationInput.vue'
import BlueprintConfirmation from '@/components/BlueprintConfirmation.vue'
import BlueprintDisplay from '@/components/BlueprintDisplay.vue'
import InspirationLoading from '@/components/InspirationLoading.vue'
import { globalAlert } from '@/composables/useAlert'

interface ChatMessage {
  content: string
  type: 'user' | 'ai' | 'error'
}

// localStorage 键名常量
const STORAGE_KEY = 'inspiration_project_id'

const router = useRouter()
const route = useRoute()
const novelStore = useNovelStore()

const conversationStarted = ref(false)
const isInitialLoading = ref(false)
const showBlueprintConfirmation = ref(false)
const showBlueprint = ref(false)
const isRefiningBlueprint = ref(false)
const chatMessages = ref<ChatMessage[]>([])
const currentUIControl = ref<UIControl | null>(null)
const currentTurn = ref(0)
const completedBlueprint = ref<Blueprint | null>(null)
const confirmationMessage = ref('')
const blueprintMessage = ref('')
const chatArea = ref<HTMLElement>()

const goBack = () => {
  router.push('/')
}

// 清空所有状态，开始新的灵感对话
const resetInspirationMode = () => {
  conversationStarted.value = false
  isInitialLoading.value = false
  showBlueprintConfirmation.value = false
  showBlueprint.value = false
  chatMessages.value = []
  currentUIControl.value = null
  currentTurn.value = 0
  completedBlueprint.value = null
  confirmationMessage.value = ''
  blueprintMessage.value = ''

  // 清空 store 中的当前项目和对话状态
  novelStore.setCurrentProject(null)
  novelStore.currentConversationState = {}

  // 清理 localStorage 中的项目ID
  localStorage.removeItem(STORAGE_KEY)
}

const exitConversation = async () => {
  const confirmed = await globalAlert.showConfirm('确定要退出灵感模式吗？当前进度可能会丢失。', '退出确认')
  if (confirmed) {
    resetInspirationMode()
    router.push('/')
  }
}

const handleRestart = async () => {
  const confirmed = await globalAlert.showConfirm('确定要重新开始吗？当前对话内容将会丢失。', '重新开始确认')
  if (confirmed) {
    await startConversation()
  }
}

const backToConversation = () => {
  showBlueprintConfirmation.value = false
}

// 处理从蓝图确认页面重新开始灵感对话
const handleRestartConversation = async () => {
  const project = novelStore.currentProject
  if (!project) return

  // 根据项目是否有章节给出不同的警告
  const hasChapters = project.chapters && project.chapters.length > 0
  const warningMessage = hasChapters
    ? `项目"${project.title}"已有 ${project.chapters.length} 个章节。\n\n重新调整蓝图后，您可能需要重新生成章节大纲，现有章节内容可能与新蓝图不匹配。\n\n是否从头开始重新对话？\n\n• 选择"确定"：清空对话历史，从头开始\n• 选择"取消"：留在当前页面`
    : `项目"${project.title}"已完成灵感阶段。\n\n是否从头开始重新对话？\n\n• 选择"确定"：清空对话历史，从头开始\n• 选择"取消"：留在当前页面`

  const confirmed = await globalAlert.showConfirm(warningMessage, '重新进行灵感对话')

  if (!confirmed) {
    return
  }

  // 用户确认，重置状态，从头开始新对话
  resetInspirationMode()
}

const startConversation = async () => {
  // 重置所有状态，开始全新的对话
  resetInspirationMode()
  conversationStarted.value = true
  isInitialLoading.value = true

  try {
    await novelStore.createProject('未命名灵感', '开始灵感模式')

    // 保存项目ID到 localStorage，以便刷新后恢复
    if (novelStore.currentProject) {
      localStorage.setItem(STORAGE_KEY, novelStore.currentProject.id)
    }

    // 发起第一次对话
    await handleUserInput(null)
  } catch (error) {
    console.error('启动灵感模式失败:', error)
    globalAlert.showError(`无法开始灵感模式: ${error instanceof Error ? error.message : '未知错误'}`, '启动失败')
    resetInspirationMode() // 失败时重置回初始状态
  }
}

const restoreConversation = async (projectId: string) => {
  try {
    await novelStore.loadProject(projectId)
    const project = novelStore.currentProject

    if (!project) {
      throw new Error('项目不存在')
    }

    // 检查是否为调整蓝图模式（来自详情页的"重新调整蓝图"按钮）
    const isRefineMode = route.query.refine_mode === 'true'

    // 关键检查：灵感模式只处理 draft 状态的项目
    if (project.status !== ProjectStatus.DRAFT) {
      localStorage.removeItem(STORAGE_KEY)  // 清除缓存

      // 如果是调整蓝图模式，直接显示已生成的蓝图展示页面，不提示
      if (isRefineMode) {
        // 确保项目有蓝图
        if (!project.blueprint) {
          globalAlert.showError('该项目还没有蓝图，请先完成灵感对话', '无法调整蓝图')
          router.push(`/novel/${projectId}`)
          return
        }

        // 设置状态直接显示蓝图展示页面（BlueprintDisplay）
        conversationStarted.value = true
        showBlueprint.value = true
        completedBlueprint.value = project.blueprint
        blueprintMessage.value = '您可以选择优化蓝图、重新生成，或者点击下方按钮重新进行灵感对话。'

        // 加载现有对话历史（如果有）
        if (project.conversation_history) {
          chatMessages.value = project.conversation_history.map((item): ChatMessage | null => {
            if (item.role === 'user') {
              try {
                const userInput = JSON.parse(item.content)
                return { content: userInput.value, type: 'user' }
              } catch {
                return { content: item.content, type: 'user' }
              }
            } else { // assistant
              try {
                const assistantOutput = JSON.parse(item.content)
                return { content: assistantOutput.ai_message, type: 'ai' }
              } catch {
                return { content: item.content, type: 'ai' }
              }
            }
          }).filter((msg): msg is ChatMessage => msg !== null && msg.content !== null)
        }

        return
      }

      // 项目已完成灵感阶段，用户想重新调整蓝图
      console.warn('项目状态为', project.status, '，用户尝试重新调整蓝图')

      // 根据项目是否有章节给出不同的警告
      const hasChapters = project.chapters && project.chapters.length > 0
      const warningMessage = hasChapters
        ? `项目"${project.title}"已有 ${project.chapters.length} 个章节。\n\n重新调整蓝图后，您可能需要重新生成章节大纲，现有章节内容可能与新蓝图不匹配。\n\n是否从头开始重新对话？\n\n• 选择"确定"：清空对话历史，从头开始\n• 选择"取消"：返回项目详情页`
        : `项目"${project.title}"已完成灵感阶段。\n\n是否从头开始重新对话？\n\n• 选择"确定"：清空对话历史，从头开始\n• 选择"取消"：返回项目详情页`

      const confirmed = await globalAlert.showConfirm(warningMessage, '重新调整蓝图')

      if (!confirmed) {
        router.push(`/novel/${projectId}`)
        return
      }

      // 用户确认，重置状态，从头开始新对话
      resetInspirationMode()
      // 重置后直接返回，用户会看到初始界面，可以开始新对话
      return
    }

    // 只有 status='draft' 的项目才继续恢复对话
    if (project.conversation_history) {
      conversationStarted.value = true

      // 保存到 localStorage（成功恢复后更新缓存）
      localStorage.setItem(STORAGE_KEY, projectId)

      chatMessages.value = project.conversation_history.map((item): ChatMessage | null => {
        if (item.role === 'user') {
          try {
            const userInput = JSON.parse(item.content)
            return { content: userInput.value, type: 'user' }
          } catch {
            return { content: item.content, type: 'user' }
          }
        } else { // assistant
          try {
            const assistantOutput = JSON.parse(item.content)
            return { content: assistantOutput.ai_message, type: 'ai' }
          } catch {
            return { content: item.content, type: 'ai' }
          }
        }
      }).filter((msg): msg is ChatMessage => msg !== null && msg.content !== null) // 过滤掉空的 user message

      // status === 'draft'，项目处于灵感对话阶段
      // 检查对话状态
      const lastAssistantMsgStr = project.conversation_history.filter(m => m.role === 'assistant').pop()?.content
      if (lastAssistantMsgStr) {
        const lastAssistantMsg = JSON.parse(lastAssistantMsgStr)

        if (lastAssistantMsg.is_complete) {
          // 对话已完成，显示蓝图确认界面
          confirmationMessage.value = lastAssistantMsg.ai_message
          showBlueprintConfirmation.value = true
        } else {
          // 对话进行中，恢复对话界面
          currentUIControl.value = lastAssistantMsg.ui_control
        }
      }

      // 计算当前轮次
      currentTurn.value = project.conversation_history.filter(m => m.role === 'assistant').length
      await scrollToBottom()
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
    globalAlert.showError(`无法恢复对话: ${error instanceof Error ? error.message : '未知错误'}`, '加载失败')
    // 恢复失败，清理缓存
    localStorage.removeItem(STORAGE_KEY)
    resetInspirationMode()
  }
}

const handleUserInput = async (userInput: any) => {
  try {
    // 如果有用户输入，添加到聊天记录
    if (userInput && userInput.value) {
      chatMessages.value.push({
        content: userInput.value,
        type: 'user'
      })
      await scrollToBottom()
    }

    const response = await novelStore.sendConversation(userInput)

    // 首次加载完成后，关闭加载动画
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }

    // 添加AI回复到聊天记录
    chatMessages.value.push({
      content: response.ai_message,
      type: 'ai'
    })
    currentTurn.value++

    await scrollToBottom()

    if (response.is_complete && response.ready_for_blueprint) {
      // 对话完成，显示蓝图确认界面
      confirmationMessage.value = response.ai_message
      showBlueprintConfirmation.value = true
    } else if (response.is_complete) {
      // 向后兼容：直接生成蓝图（如果后端还没更新）
      await handleGenerateBlueprint()
    } else {
      // 继续对话
      currentUIControl.value = response.ui_control
    }
  } catch (error) {
    console.error('对话失败:', error)
    // 确保在出错时也停止初始加载状态
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }

    // 在聊天记录中显示错误消息，允许用户继续对话
    chatMessages.value.push({
      content: `抱歉，处理您的消息时遇到问题：${error instanceof Error ? error.message : '未知错误'}。请尝试换一种方式重新表达，或点击下方按钮重试。`,
      type: 'error'
    })
    await scrollToBottom()

    // 保持当前UI控制状态，允许用户重新输入
    // 不调用 resetInspirationMode()，保留对话历史
  }
}

const handleManualGenerateBlueprint = async () => {
  const confirmed = await globalAlert.showConfirm(
    '确定要结束对话并生成蓝图吗？\n\n已收集的信息足够生成一份完整的小说蓝图。',
    '生成确认'
  )

  if (confirmed) {
    // 模拟 AI 完成对话的消息
    confirmationMessage.value = '🎉 完美！灵感的每一个碎片都已归位。我已经收集了构建你故事宇宙所需的所有核心基石。\n\n现在可以开始生成蓝图了！'
    showBlueprintConfirmation.value = true
  }
}

const handleGenerateBlueprint = async () => {
  try {
    const response = await novelStore.generateBlueprint()
    handleBlueprintGenerated(response)
  } catch (error) {
    console.error('生成蓝图失败:', error)
    globalAlert.showError(`生成蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  }
}

const handleBlueprintGenerated = (response: any) => {
  console.log('收到蓝图生成完成事件:', response)
  completedBlueprint.value = response.blueprint
  blueprintMessage.value = response.ai_message
  showBlueprintConfirmation.value = false
  showBlueprint.value = true

  // 蓝图生成完成，灵感对话阶段结束，清除localStorage
  // 项目状态已变为 blueprint_ready，不应该再在灵感模式中恢复
  localStorage.removeItem(STORAGE_KEY)
  console.log('蓝图生成完成，已清除灵感模式缓存')
}

const handleRegenerateBlueprint = () => {
  showBlueprint.value = false
  showBlueprintConfirmation.value = true
}

const handleRefineBlueprint = async (instruction: string) => {
  isRefiningBlueprint.value = true
  try {
    const response = await novelStore.refineBlueprint(instruction)
    completedBlueprint.value = response.blueprint
    blueprintMessage.value = response.ai_message
    // 保持在蓝图展示界面，显示优化后的蓝图
  } catch (error) {
    console.error('优化蓝图失败:', error)
    globalAlert.showError(`优化蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '优化失败')
  } finally {
    isRefiningBlueprint.value = false
  }
}

const handleConfirmBlueprint = async () => {
  if (!completedBlueprint.value) {
    globalAlert.showError('蓝图数据缺失，请重新生成或稍后重试。', '保存失败')
    return
  }
  try {
    await novelStore.saveBlueprint(completedBlueprint.value)

    // 蓝图保存成功，清理 localStorage（灵感对话已完成）
    localStorage.removeItem(STORAGE_KEY)

    // 跳转到写作工作台
    if (novelStore.currentProject) {
      router.push(`/novel/${novelStore.currentProject.id}`)
    }
  } catch (error) {
    console.error('保存蓝图失败:', error)
    globalAlert.showError(`保存蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatArea.value) {
    chatArea.value.scrollTop = chatArea.value.scrollHeight
  }
}

// 查找未完成的项目（灵感模式进行中的项目）
const findUnfinishedProject = async () => {
  try {
    await novelStore.loadProjects()
    const projects = novelStore.projects

    // 查找符合条件的项目：状态为 draft（灵感模式进行中）
    const unfinished = projects.find(p => p.status === ProjectStatus.DRAFT)

    return unfinished
  } catch (error) {
    console.error('查找未完成项目失败:', error)
    return null
  }
}

onMounted(async () => {
  // 优先级1：URL参数（最高优先级）
  const projectId = route.query.project_id as string
  if (projectId) {
    await restoreConversation(projectId)
    return
  }

  // 优先级2：localStorage 缓存
  const cachedProjectId = localStorage.getItem(STORAGE_KEY)
  if (cachedProjectId) {
    try {
      await restoreConversation(cachedProjectId)
      return
    } catch (error) {
      // 缓存的项目ID失效（可能已删除），清理缓存
      console.warn('缓存的项目ID失效，已清理:', error)
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  // 优先级3：查找未完成的项目
  const unfinishedProject = await findUnfinishedProject()
  if (unfinishedProject) {
    const confirmed = await globalAlert.showConfirm(
      `检测到未完成的对话"${unfinishedProject.title}"，是否继续？`,
      '恢复对话'
    )
    if (confirmed) {
      await restoreConversation(unfinishedProject.id)
      return
    }
  }

  // 如果都没有，重置状态等待用户开始新对话
  resetInspirationMode()
})

</script>
