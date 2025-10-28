<template>
  <n-space vertical size="large" class="llm-config-management">
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">LLM 配置管理</span>
          <n-button type="primary" size="small" @click="openCreateModal">
            新增配置
          </n-button>
        </div>
      </template>

      <n-spin :show="loading">
        <n-alert v-if="error" type="error" closable @close="error = null" class="mb-4">
          {{ error }}
        </n-alert>

        <n-alert type="info" class="mb-4">
          <div>
            <p class="font-medium mb-1">配置说明</p>
            <ul class="text-sm list-disc list-inside space-y-1">
              <li>您可以创建多个 LLM 配置，系统将使用当前激活的配置进行 AI 生成</li>
              <li>测试配置可以验证 API Key 是否有效，响应时间是否正常</li>
              <li>激活的配置不能被删除，请先切换到其他配置</li>
            </ul>
          </div>
        </n-alert>

        <n-data-table
          :columns="columns"
          :data="configs"
          :loading="loading"
          :bordered="false"
          :row-key="rowKey"
          class="config-table"
        />
      </n-spin>
    </n-card>
  </n-space>

  <!-- 创建/编辑配置 Modal -->
  <n-modal
    v-model:show="modalVisible"
    preset="card"
    :title="modalTitle"
    class="config-modal"
    :style="{ width: '600px', maxWidth: '92vw' }"
  >
    <n-form ref="formRef" :model="formData" :rules="formRules" label-placement="top">
      <n-form-item label="配置名称" path="config_name">
        <n-input
          v-model:value="formData.config_name"
          placeholder="如：GPT-4 配置、Claude 配置等"
        />
      </n-form-item>

      <n-form-item label="API Base URL" path="llm_provider_url">
        <n-input
          v-model:value="formData.llm_provider_url"
          placeholder="https://api.openai.com/v1"
        />
      </n-form-item>

      <n-form-item label="API Key" path="llm_provider_api_key">
        <n-input
          v-model:value="formData.llm_provider_api_key"
          type="password"
          show-password-on="click"
          placeholder="sk-..."
        />
      </n-form-item>

      <n-form-item label="模型名称" path="llm_provider_model">
        <n-input
          v-model:value="formData.llm_provider_model"
          placeholder="gpt-4、claude-3-opus-20240229 等"
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeModal">取消</n-button>
        <n-button type="primary" :loading="saving" @click="submitConfig">
          保存
        </n-button>
      </n-space>
    </template>
  </n-modal>

  <!-- 测试结果 Modal -->
  <n-modal
    v-model:show="testResultVisible"
    preset="card"
    title="测试结果"
    :style="{ width: '500px', maxWidth: '92vw' }"
  >
    <n-result
      :status="testResult?.success ? 'success' : 'error'"
      :title="testResult?.success ? '连接成功' : '连接失败'"
      :description="testResult?.message"
    >
      <template #footer v-if="testResult?.success">
        <n-descriptions :column="1" bordered size="small">
          <n-descriptions-item label="响应时间">
            {{ testResult.response_time_ms?.toFixed(2) }} ms
          </n-descriptions-item>
          <n-descriptions-item label="模型">
            {{ testResult.model_info }}
          </n-descriptions-item>
        </n-descriptions>
      </template>
    </n-result>

    <template #footer>
      <n-space justify="end">
        <n-button type="primary" @click="testResultVisible = false">关闭</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NResult,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  type DataTableColumns,
  type FormInst,
  type FormRules
} from 'naive-ui'
import { useAlert } from '@/composables/useAlert'
import {
  activateLLMConfig,
  createLLMConfig,
  deleteLLMConfigById,
  listLLMConfigs,
  testLLMConfig,
  updateLLMConfig,
  type LLMConfig,
  type LLMConfigCreate,
  type LLMConfigTestResponse,
  type LLMConfigUpdate
} from '@/api/llm'

const { showAlert } = useAlert()

// 数据状态
const configs = ref<LLMConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)

// Modal 状态
const modalVisible = ref(false)
const isCreateMode = ref(true)
const formRef = ref<FormInst | null>(null)
const formData = reactive<LLMConfigCreate | LLMConfigUpdate>({
  config_name: '',
  llm_provider_url: '',
  llm_provider_api_key: '',
  llm_provider_model: ''
})

// 测试结果
const testResultVisible = ref(false)
const testResult = ref<LLMConfigTestResponse | null>(null)

const rowKey = (row: LLMConfig) => row.id

const modalTitle = computed(() => (isCreateMode.value ? '新增 LLM 配置' : '编辑 LLM 配置'))

// 表单验证规则
const formRules: FormRules = {
  config_name: [
    { required: true, message: '请输入配置名称', trigger: 'blur' }
  ]
}

// 表格列定义
const columns: DataTableColumns<LLMConfig> = [
  {
    title: '配置名称',
    key: 'config_name',
    width: 150
  },
  {
    title: '状态',
    key: 'is_active',
    width: 80,
    render: (row) => {
      return h(
        NTag,
        {
          type: row.is_active ? 'success' : 'default',
          size: 'small'
        },
        { default: () => (row.is_active ? '激活' : '未激活') }
      )
    }
  },
  {
    title: '验证状态',
    key: 'is_verified',
    width: 100,
    render: (row) => {
      if (!row.is_verified && !row.test_status) {
        return h(NTag, { type: 'default', size: 'small' }, { default: () => '未测试' })
      }
      if (row.test_status === 'success') {
        return h(NTag, { type: 'success', size: 'small' }, { default: () => '已验证' })
      }
      if (row.test_status === 'failed') {
        return h(NTag, { type: 'error', size: 'small' }, { default: () => '验证失败' })
      }
      return h(NTag, { type: 'warning', size: 'small' }, { default: () => '测试中' })
    }
  },
  {
    title: 'API Key',
    key: 'llm_provider_api_key_masked',
    width: 150,
    ellipsis: true,
    render: (row) => row.llm_provider_api_key_masked || '(未设置)'
  },
  {
    title: 'Base URL',
    key: 'llm_provider_url',
    width: 200,
    ellipsis: true,
    render: (row) => row.llm_provider_url || '(默认)'
  },
  {
    title: '模型',
    key: 'llm_provider_model',
    width: 150,
    ellipsis: true,
    render: (row) => row.llm_provider_model || '(默认)'
  },
  {
    title: '最后测试',
    key: 'last_test_at',
    width: 170,
    render: (row) => {
      if (!row.last_test_at) return '-'
      return new Date(row.last_test_at).toLocaleString('zh-CN')
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    fixed: 'right',
    render: (row) => {
      return h(
        NSpace,
        { size: 'small' },
        {
          default: () => [
            // 测试按钮
            h(
              NButton,
              {
                size: 'small',
                quaternary: true,
                type: 'info',
                loading: testingConfigId.value === row.id,
                onClick: () => handleTest(row)
              },
              { default: () => '测试' }
            ),
            // 激活/已激活按钮
            row.is_active
              ? h(
                  NTag,
                  { type: 'success', size: 'small' },
                  { default: () => '当前激活' }
                )
              : h(
                  NButton,
                  {
                    size: 'small',
                    quaternary: true,
                    type: 'primary',
                    onClick: () => handleActivate(row)
                  },
                  { default: () => '激活' }
                ),
            // 编辑按钮
            h(
              NButton,
              {
                size: 'small',
                quaternary: true,
                onClick: () => handleEdit(row)
              },
              { default: () => '编辑' }
            ),
            // 删除按钮
            h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete(row)
              },
              {
                default: () => (row.is_active ? '无法删除当前激活的配置' : '确定删除此配置？'),
                trigger: () =>
                  h(
                    NButton,
                    {
                      size: 'small',
                      quaternary: true,
                      type: 'error',
                      disabled: row.is_active
                    },
                    { default: () => '删除' }
                  )
              }
            )
          ]
        }
      )
    }
  }
]

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
  formRef.value?.restoreValidation()
}

// 提交配置
const submitConfig = async () => {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    if (isCreateMode.value) {
      await createLLMConfig(formData as LLMConfigCreate)
      showAlert('创建成功', 'success')
    } else {
      // 如果 API Key 为空，则不发送
      const updateData: LLMConfigUpdate = { ...formData }
      if (!updateData.llm_provider_api_key) {
        delete updateData.llm_provider_api_key
      }
      await updateLLMConfig(formData.id!, updateData)
      showAlert('更新成功', 'success')
    }
    closeModal()
    await fetchConfigs()
  } catch (err: any) {
    error.value = err.message || '保存失败'
  } finally {
    saving.value = false
  }
}

// 激活配置
const handleActivate = async (config: LLMConfig) => {
  try {
    await activateLLMConfig(config.id)
    showAlert('已激活配置', 'success')
    await fetchConfigs()
  } catch (err: any) {
    error.value = err.message || '激活失败'
  }
}

// 删除配置
const handleDelete = async (config: LLMConfig) => {
  try {
    await deleteLLMConfigById(config.id)
    showAlert('删除成功', 'success')
    await fetchConfigs()
  } catch (err: any) {
    error.value = err.message || '删除失败'
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
  } finally {
    testingConfigId.value = null
  }
}

onMounted(() => {
  fetchConfigs()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>
