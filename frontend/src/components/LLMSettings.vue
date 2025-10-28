<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold text-gray-800">LLM 配置管理</h2>
        <p class="text-sm text-gray-600 mt-1">管理您的 AI 模型配置，支持多个配置切换</p>
      </div>
      <button
        @click="openCreateModal"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
      >
        新增配置
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="text-center py-8">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      <p class="text-gray-600 mt-2">加载中...</p>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
      {{ error }}
    </div>

    <!-- 配置说明 -->
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-blue-800 font-medium mb-2">💡 配置说明</p>
      <ul class="text-sm text-blue-700 space-y-1 list-disc list-inside">
        <li>您可以创建多个 LLM 配置，系统将使用当前激活的配置进行 AI 生成</li>
        <li>测试配置可以验证 API Key 是否有效，响应时间是否正常</li>
        <li>激活的配置不能被删除，请先切换到其他配置</li>
      </ul>
    </div>

    <!-- 配置列表 -->
    <div v-if="!loading && configs.length > 0" class="space-y-4">
      <div
        v-for="config in configs"
        :key="config.id"
        class="border rounded-xl p-6 hover:shadow-md transition-shadow"
        :class="config.is_active ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 bg-white'"
      >
        <div class="flex justify-between items-start mb-4">
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <h3 class="text-lg font-semibold text-gray-800">{{ config.config_name }}</h3>
              <span
                v-if="config.is_active"
                class="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full"
              >
                当前激活
              </span>
              <span
                v-if="config.is_verified && config.test_status === 'success'"
                class="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full"
              >
                已验证
              </span>
              <span
                v-else-if="config.test_status === 'failed'"
                class="px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full"
              >
                验证失败
              </span>
            </div>
            <div class="space-y-1 text-sm text-gray-600">
              <p><strong>API URL:</strong> {{ config.llm_provider_url || '(默认)' }}</p>
              <p><strong>API Key:</strong> {{ config.llm_provider_api_key_masked || '(未设置)' }}</p>
              <p><strong>模型:</strong> {{ config.llm_provider_model || '(默认)' }}</p>
              <p v-if="config.last_test_at" class="text-xs text-gray-500">
                最后测试: {{ formatDate(config.last_test_at) }}
              </p>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="flex gap-2 flex-wrap">
          <button
            @click="handleTest(config)"
            :disabled="testingConfigId === config.id"
            class="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {{ testingConfigId === config.id ? '测试中...' : '测试连接' }}
          </button>
          <button
            v-if="!config.is_active"
            @click="handleActivate(config)"
            class="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            激活配置
          </button>
          <button
            @click="handleEdit(config)"
            class="px-4 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            编辑
          </button>
          <button
            @click="handleDelete(config)"
            :disabled="config.is_active"
            class="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
            :title="config.is_active ? '无法删除当前激活的配置' : '删除配置'"
          >
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && configs.length === 0" class="text-center py-12">
      <p class="text-gray-500 mb-4">您还没有配置 LLM，点击上方"新增配置"按钮创建</p>
    </div>
  </div>

  <!-- 创建/编辑配置弹窗 -->
  <div
    v-if="modalVisible"
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
    @click.self="closeModal"
  >
    <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
      <div class="p-6 border-b border-gray-200">
        <h3 class="text-xl font-bold text-gray-800">
          {{ isCreateMode ? '新增 LLM 配置' : '编辑 LLM 配置' }}
        </h3>
      </div>

      <form @submit.prevent="submitConfig" class="p-6 space-y-6">
        <div>
          <label for="config_name" class="block text-sm font-medium text-gray-700 mb-2">
            配置名称 <span class="text-red-500">*</span>
          </label>
          <input
            id="config_name"
            v-model="formData.config_name"
            type="text"
            required
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="如：GPT-4 配置、Claude 配置等"
          />
        </div>

        <div>
          <label for="llm_provider_url" class="block text-sm font-medium text-gray-700 mb-2">
            API Base URL
          </label>
          <input
            id="llm_provider_url"
            v-model="formData.llm_provider_url"
            type="text"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="https://api.openai.com/v1"
          />
        </div>

        <div>
          <label for="llm_provider_api_key" class="block text-sm font-medium text-gray-700 mb-2">
            API Key
          </label>
          <input
            id="llm_provider_api_key"
            v-model="formData.llm_provider_api_key"
            type="password"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            :placeholder="isCreateMode ? 'sk-...' : '留空表示不修改'"
          />
          <p v-if="!isCreateMode" class="text-xs text-gray-500 mt-1">留空表示保持原有 API Key 不变</p>
        </div>

        <div>
          <label for="llm_provider_model" class="block text-sm font-medium text-gray-700 mb-2">
            模型名称
          </label>
          <input
            id="llm_provider_model"
            v-model="formData.llm_provider_model"
            type="text"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="gpt-4、claude-3-opus-20240229 等"
          />
        </div>

        <div class="flex justify-end gap-3 pt-4">
          <button
            type="button"
            @click="closeModal"
            class="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
          <button
            type="submit"
            :disabled="saving"
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- 测试结果弹窗 -->
  <div
    v-if="testResultVisible"
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
    @click.self="testResultVisible = false"
  >
    <div class="bg-white rounded-2xl shadow-2xl max-w-md w-full">
      <div class="p-6">
        <div class="text-center">
          <div
            class="mx-auto flex items-center justify-center h-16 w-16 rounded-full mb-4"
            :class="testResult?.success ? 'bg-green-100' : 'bg-red-100'"
          >
            <span class="text-3xl">{{ testResult?.success ? '✓' : '✗' }}</span>
          </div>
          <h3 class="text-xl font-bold text-gray-800 mb-2">
            {{ testResult?.success ? '连接成功' : '连接失败' }}
          </h3>
          <p class="text-gray-600 mb-4">{{ testResult?.message }}</p>

          <div v-if="testResult?.success" class="bg-gray-50 rounded-lg p-4 text-left space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-gray-600">响应时间:</span>
              <span class="font-medium text-gray-800">{{ testResult.response_time_ms?.toFixed(2) }} ms</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-600">模型:</span>
              <span class="font-medium text-gray-800">{{ testResult.model_info }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="border-t border-gray-200 p-4">
        <button
          @click="testResultVisible = false"
          class="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import {
  listLLMConfigs,
  createLLMConfig,
  updateLLMConfig,
  activateLLMConfig,
  deleteLLMConfigById,
  testLLMConfig,
  type LLMConfig,
  type LLMConfigCreate,
  type LLMConfigUpdate,
  type LLMConfigTestResponse
} from '@/api/llm'

// 数据状态
const configs = ref<LLMConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)

// Modal 状态
const modalVisible = ref(false)
const isCreateMode = ref(true)
const formData = reactive<LLMConfigCreate | LLMConfigUpdate>({
  config_name: '',
  llm_provider_url: '',
  llm_provider_api_key: '',
  llm_provider_model: ''
})

// 测试结果
const testResultVisible = ref(false)
const testResult = ref<LLMConfigTestResponse | null>(null)
const testingConfigId = ref<number | null>(null)

// 加载配置列表
const fetchConfigs = async () => {
  loading.value = true
  error.value = null
  try {
    configs.value = await listLLMConfigs()
  } catch (err: any) {
    error.value = err.message || '加载配置失败'
  } finally {
    loading.value = false
  }
}

// 打开创建 Modal
const openCreateModal = () => {
  isCreateMode.value = true
  Object.assign(formData, {
    config_name: '',
    llm_provider_url: '',
    llm_provider_api_key: '',
    llm_provider_model: ''
  })
  modalVisible.value = true
}

// 打开编辑 Modal
const handleEdit = (config: LLMConfig) => {
  isCreateMode.value = false
  Object.assign(formData, {
    config_name: config.config_name,
    llm_provider_url: config.llm_provider_url || '',
    llm_provider_api_key: '', // 不回填 API Key
    llm_provider_model: config.llm_provider_model || ''
  })
  formData.id = config.id
  modalVisible.value = true
}

// 关闭 Modal
const closeModal = () => {
  modalVisible.value = false
}

// 提交配置
const submitConfig = async () => {
  if (!formData.config_name?.trim()) {
    alert('请输入配置名称')
    return
  }

  saving.value = true
  try {
    if (isCreateMode.value) {
      await createLLMConfig(formData as LLMConfigCreate)
      alert('创建成功！')
    } else {
      // 如果 API Key 为空，则不发送
      const updateData: LLMConfigUpdate = { ...formData }
      if (!updateData.llm_provider_api_key) {
        delete updateData.llm_provider_api_key
      }
      await updateLLMConfig(formData.id!, updateData)
      alert('更新成功！')
    }
    closeModal()
    await fetchConfigs()
  } catch (err: any) {
    error.value = err.message || '保存失败'
    alert(error.value)
  } finally {
    saving.value = false
  }
}

// 激活配置
const handleActivate = async (config: LLMConfig) => {
  try {
    await activateLLMConfig(config.id)
    alert('已激活配置！')
    await fetchConfigs()
  } catch (err: any) {
    error.value = err.message || '激活失败'
    alert(error.value)
  }
}

// 删除配置
const handleDelete = async (config: LLMConfig) => {
  if (config.is_active) {
    alert('无法删除当前激活的配置，请先激活其他配置')
    return
  }

  if (!confirm(`确定要删除配置"${config.config_name}"吗？`)) {
    return
  }

  try {
    await deleteLLMConfigById(config.id)
    alert('删除成功！')
    await fetchConfigs()
  } catch (err: any) {
    error.value = err.message || '删除失败'
    alert(error.value)
  }
}

// 测试配置
const handleTest = async (config: LLMConfig) => {
  testingConfigId.value = config.id
  try {
    testResult.value = await testLLMConfig(config.id)
    testResultVisible.value = true
    await fetchConfigs() // 刷新以显示测试结果
  } catch (err: any) {
    error.value = err.message || '测试失败'
    alert(error.value)
  } finally {
    testingConfigId.value = null
  }
}

// 格式化日期
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchConfigs()
})
</script>
