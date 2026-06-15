import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, Eye, EyeOff, CheckCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useConfigStore } from '../store/configStore';
import { getConfig, updateConfig } from '../api/client';
import type { PipelineMode, ConfigResponse } from '../types';

export default function SettingsPage() {
  const { mode, debateAgents, temperature, maxTokens, setMode, setDebateAgents, setTemperature, setMaxTokens } = useConfigStore();

  // API connection settings
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [apiKeyMasked, setApiKeyMasked] = useState('');

  // UI state
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fetching, setFetching] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; error?: string; response_preview?: string } | null>(null);

  // Load current config from backend on mount
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setFetching(true);
    try {
      const config = await getConfig();
      setApiUrl(config.api_url);
      setModelName(config.model_name);
      setHasApiKey(config.has_api_key);
      setApiKeyMasked(config.api_key_masked);
      setMode(config.pipeline_mode as PipelineMode);
      setDebateAgents(config.debate_agents);
      setTemperature(config.temperature);
      setMaxTokens(config.max_tokens);
    } catch (err) {
      console.error('Failed to load config:', err);
    } finally {
      setFetching(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setError('');
    try {
      const updates: Record<string, unknown> = {
        api_url: apiUrl,
        model_name: modelName,
        temperature,
        max_tokens: maxTokens,
        pipeline_mode: mode,
        debate_agents: debateAgents,
      };
      // Only send API key if user typed a new one
      if (apiKey) {
        updates.api_key = apiKey;
      }

      const result = await updateConfig(updates);
      setHasApiKey(result.has_api_key);
      setApiKeyMasked(result.api_key_masked);
      setApiKey(''); // Clear the input after saving
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '保存失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (fetching) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <SettingsIcon className="w-6 h-6 text-gray-700" />
          <h2 className="text-2xl font-bold text-gray-900">系统设置</h2>
        </div>
        <button onClick={loadConfig} className="btn-secondary text-sm flex items-center gap-1">
          <RefreshCw className="w-4 h-4" />
          刷新
        </button>
      </div>

      <div className="space-y-6">
        {/* API Connection */}
        <div className="card border-l-4 border-l-primary-500">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">🔗 API 连接配置</h3>
          <p className="text-xs text-gray-500 mb-4">
            配置 Intern-S1 或兼容的 LLM API。修改后会自动保存到 .env 文件。
          </p>

          <div className="space-y-4">
            {/* API URL */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API 地址
              </label>
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://internlm.intern-ai.org.cn/api/v1/chat/completions"
                className="input-field font-mono text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                OpenAI 兼容的 Chat Completions 端点
              </p>
            </div>

            {/* API Key */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={hasApiKey ? `已配置: ${apiKeyMasked} — 输入新密钥替换` : 'sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
                  className="input-field font-mono text-sm pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {hasApiKey && (
                <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />
                  已配置密钥: {apiKeyMasked}
                </p>
              )}
            </div>

            {/* Model Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                模型名称
              </label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="Intern-S1"
                className="input-field font-mono text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                常见值: Intern-S1, internlm2-chat-7b, gpt-4, deepseek-chat
              </p>
            </div>
          </div>
        </div>

        {/* Test Connection */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">🧪 测试 API 连接</h3>
          <p className="text-xs text-gray-500 mb-3">
            先保存 API 配置，然后点击测试按钮验证连接是否正常。
          </p>
          <button
            onClick={async () => {
              setTesting(true);
              setTestResult(null);
              try {
                const res = await fetch('/api/config/test', { method: 'POST' });
                const data = await res.json();
                setTestResult(data);
              } catch (err) {
                setTestResult({ status: 'error', error: '请求失败' });
              } finally {
                setTesting(false);
              }
            }}
            disabled={testing}
            className="btn-secondary flex items-center gap-2"
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {testing ? '测试中...' : '测试 API 连接'}
          </button>
          {testResult && (
            <div className={`mt-3 p-3 rounded-lg text-sm ${
              testResult.status === 'success'
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}>
              {testResult.status === 'success' ? (
                <div>
                  <p className="font-semibold">✅ 连接成功！</p>
                  <p className="text-xs mt-1">API 响应: {testResult.response_preview}</p>
                  <p className="text-xs mt-1">URL: {apiUrl}</p>
                </div>
              ) : (
                <div>
                  <p className="font-semibold">❌ 连接失败</p>
                  <p className="text-xs mt-1">{testResult.error}</p>
                  <p className="text-xs mt-2 text-red-600">
                    请检查: 1) API 地址是否正确 2) API Key 是否有效 3) 模型名称是否存在
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Pipeline Mode */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">推理模式</h3>
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setMode('single')}
              className={`p-4 rounded-lg border-2 text-left transition-colors ${
                mode === 'single'
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold text-gray-900">单智能体模式</p>
              <p className="text-sm text-gray-500 mt-1">线性流水线：理解→分类→定位→规划→求解→验证→解释</p>
            </button>
            <button
              onClick={() => setMode('multi_debate')}
              className={`p-4 rounded-lg border-2 text-left transition-colors ${
                mode === 'multi_debate'
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold text-gray-900">辩论模式</p>
              <p className="text-sm text-gray-500 mt-1">N个求解器并行推理 + 共识投票</p>
            </button>
          </div>
        </div>

        {/* Debate Agents */}
        {mode === 'multi_debate' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">辩论智能体数量</h3>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={1}
                max={10}
                value={debateAgents}
                onChange={(e) => setDebateAgents(Number(e.target.value))}
                className="flex-1"
              />
              <span className="text-lg font-mono font-bold text-primary-600 w-8 text-center">
                {debateAgents}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-2">更多智能体 = 更高准确性，但更慢且更贵</p>
          </div>
        )}

        {/* LLM Parameters */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">模型参数</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Temperature: {temperature.toFixed(1)}
              </label>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-400">
                <span>精确 (0)</span>
                <span>创造性 (2)</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                最大 Tokens: {maxTokens}
              </label>
              <input
                type="range"
                min={1024}
                max={32768}
                step={1024}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-400">
                <span>1024</span>
                <span>32768</span>
              </div>
            </div>
          </div>
        </div>

        {/* Save button */}
        <div className="flex items-center gap-3">
          <button onClick={handleSave} disabled={loading} className="btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {loading ? '保存中...' : saved ? '已保存并持久化 ✓' : '保存设置'}
          </button>
          {saved && (
            <span className="text-sm text-green-600 flex items-center gap-1">
              <CheckCircle className="w-4 h-4" />
              配置已保存到 .env 文件，重启后仍然生效
            </span>
          )}
          {error && (
            <span className="text-sm text-red-600 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}