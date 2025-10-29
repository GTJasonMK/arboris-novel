import { useAuthStore } from '@/stores/auth';

const API_PREFIX = '/api';
const LLM_BASE = `${API_PREFIX}/llm-config`;

// ========== 类型定义 ==========

export interface LLMConfig {
  id: number;
  user_id: number;
  config_name: string;
  llm_provider_url: string | null;
  llm_provider_api_key_masked: string | null;
  llm_provider_model: string | null;
  is_active: boolean;
  is_verified: boolean;
  last_test_at: string | null;
  test_status: string | null;
  test_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface LLMConfigCreate {
  config_name: string;
  llm_provider_url?: string;
  llm_provider_api_key?: string;
  llm_provider_model?: string;
}

export interface LLMConfigUpdate {
  config_name?: string;
  llm_provider_url?: string;
  llm_provider_api_key?: string;
  llm_provider_model?: string;
}

export interface LLMConfigTestResponse {
  success: boolean;
  message: string;
  response_time_ms?: number;
  model_info?: string;
}

// ========== 辅助函数 ==========

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authStore.token}`,
  };
};

// ========== 旧版 API（兼容性保留） ==========

/**
 * 获取用户的第一个LLM配置（兼容旧版）
 * @deprecated 建议使用 listLLMConfigs 获取所有配置
 */
export const getLLMConfig = async (): Promise<LLMConfig | null> => {
  const response = await fetch(LLM_BASE, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error('Failed to fetch LLM config');
  }
  return response.json();
};

/**
 * 创建或更新用户的第一个LLM配置（兼容旧版）
 * @deprecated 建议使用 createLLMConfig 或 updateLLMConfig
 */
export const createOrUpdateLLMConfig = async (config: LLMConfigCreate): Promise<LLMConfig> => {
  const response = await fetch(LLM_BASE, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    throw new Error('Failed to save LLM config');
  }
  return response.json();
};

/**
 * 删除用户的第一个LLM配置（兼容旧版）
 * @deprecated 建议使用 deleteLLMConfigById
 */
export const deleteLLMConfig = async (): Promise<void> => {
  const response = await fetch(LLM_BASE, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to delete LLM config');
  }
};

// ========== 新版多配置管理 API ==========

/**
 * 获取用户的所有LLM配置列表
 */
export const listLLMConfigs = async (): Promise<LLMConfig[]> => {
  const response = await fetch(`${LLM_BASE}/configs`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to fetch LLM configs');
  }
  return response.json();
};

/**
 * 获取用户当前激活的LLM配置
 */
export const getActiveLLMConfig = async (): Promise<LLMConfig | null> => {
  const response = await fetch(`${LLM_BASE}/configs/active`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error('Failed to fetch active LLM config');
  }
  return response.json();
};

/**
 * 获取指定ID的LLM配置
 */
export const getLLMConfigById = async (configId: number): Promise<LLMConfig> => {
  const response = await fetch(`${LLM_BASE}/configs/${configId}`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to fetch LLM config');
  }
  return response.json();
};

/**
 * 创建新的LLM配置
 */
export const createLLMConfig = async (config: LLMConfigCreate): Promise<LLMConfig> => {
  const response = await fetch(`${LLM_BASE}/configs`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create LLM config' }));
    throw new Error(error.detail || 'Failed to create LLM config');
  }
  return response.json();
};

/**
 * 更新指定ID的LLM配置
 */
export const updateLLMConfig = async (configId: number, config: LLMConfigUpdate): Promise<LLMConfig> => {
  const response = await fetch(`${LLM_BASE}/configs/${configId}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update LLM config' }));
    throw new Error(error.detail || 'Failed to update LLM config');
  }
  return response.json();
};

/**
 * 激活指定ID的LLM配置
 */
export const activateLLMConfig = async (configId: number): Promise<LLMConfig> => {
  const response = await fetch(`${LLM_BASE}/configs/${configId}/activate`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to activate LLM config');
  }
  return response.json();
};

/**
 * 删除指定ID的LLM配置
 */
export const deleteLLMConfigById = async (configId: number): Promise<void> => {
  const response = await fetch(`${LLM_BASE}/configs/${configId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete LLM config' }));
    throw new Error(error.detail || 'Failed to delete LLM config');
  }
};

/**
 * 测试指定ID的LLM配置
 */
export const testLLMConfig = async (configId: number): Promise<LLMConfigTestResponse> => {
  const response = await fetch(`${LLM_BASE}/configs/${configId}/test`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to test LLM config');
  }
  return response.json();
};

// ========== 导入导出功能 ==========

/**
 * 导出单个LLM配置
 */
export const exportLLMConfig = async (configId: number): Promise<void> => {
  const response = await fetch(`${LLM_BASE}/configs/${configId}/export`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to export LLM config');
  }

  // 下载文件
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `llm_config_${configId}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

/**
 * 导出所有LLM配置
 */
export const exportAllLLMConfigs = async (): Promise<void> => {
  const response = await fetch(`${LLM_BASE}/configs/export/all`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to export all LLM configs');
  }

  // 下载文件
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  a.download = `llm_configs_${timestamp}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

/**
 * 导入LLM配置
 */
export const importLLMConfigs = async (data: any): Promise<any> => {
  const response = await fetch(`${LLM_BASE}/configs/import`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to import LLM configs' }));
    throw new Error(error.detail || 'Failed to import LLM configs');
  }
  return response.json();
};

