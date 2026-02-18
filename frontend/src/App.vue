<template>
  <div class="min-h-screen bg-gray-100">
    <!-- Header -->
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto px-4 py-6">
        <h1 class="text-3xl font-bold text-gray-900">API Exchange 管理后台</h1>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-6">
      <!-- Login -->
      <div v-if="!isLoggedIn" class="max-w-md mx-auto bg-white rounded-lg shadow p-6">
        <h2 class="text-xl font-semibold mb-4">登录</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700">管理密钥</label>
            <input
              v-model="adminKey"
              type="password"
              class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 px-3 py-2 border"
              placeholder="sk-api-exchange-admin"
              @keyup.enter="login"
            />
          </div>
          <button
            @click="login"
            class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700"
          >
            登录
          </button>
          <p v-if="loginError" class="text-red-500 text-sm">{{ loginError }}</p>
        </div>
      </div>

      <!-- Dashboard -->
      <div v-else>
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div class="bg-white rounded-lg shadow p-6">
            <div class="text-sm font-medium text-gray-500">总余额</div>
            <div class="text-3xl font-bold text-green-600">${{ stats.total_balance?.toFixed(4) || '0.00' }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-6">
            <div class="text-sm font-medium text-gray-500">已消费</div>
            <div class="text-3xl font-bold text-orange-600">${{ stats.total_used?.toFixed(4) || '0.00' }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-6">
            <div class="text-sm font-medium text-gray-500">总请求数</div>
            <div class="text-3xl font-bold text-blue-600">{{ stats.total_requests || 0 }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-6">
            <div class="text-sm font-medium text-gray-500">可用 Keys</div>
            <div class="text-3xl font-bold text-purple-600">
              {{ stats.active_keys || 0 }} / {{ stats.total_keys || 0 }}
            </div>
          </div>
        </div>

        <!-- Tabs -->
        <div class="bg-white rounded-lg shadow">
          <div class="border-b border-gray-200">
            <nav class="flex -mb-px">
              <button
                @click="activeTab = 'keys'"
                :class="[
                  'px-6 py-3 text-sm font-medium',
                  activeTab === 'keys'
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                ]"
              >
                API Keys
              </button>
              <button
                @click="activeTab = 'models'; loadModels()"
                :class="[
                  'px-6 py-3 text-sm font-medium',
                  activeTab === 'models'
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                ]"
              >
                模型列表
              </button>
              <button
                @click="activeTab = 'pricing'"
                :class="[
                  'px-6 py-3 text-sm font-medium',
                  activeTab === 'pricing'
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                ]"
              >
                定价配置
              </button>
              <button
                @click="activeTab = 'import'"
                :class="[
                  'px-6 py-3 text-sm font-medium',
                  activeTab === 'import'
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                ]"
              >
                批量导入
              </button>
            </nav>
          </div>

          <!-- Keys Tab -->
          <div v-if="activeTab === 'keys'" class="p-6">
            <!-- Filter and Sync -->
            <div class="flex justify-between items-center mb-4">
              <div class="flex gap-2">
                <button
                  v-for="status in ['all', 'active', 'exhausted', 'invalid']"
                  :key="status"
                  @click="filterStatus = status === 'all' ? null : status; loadKeys()"
                  :class="[
                    'px-3 py-1 rounded-full text-sm',
                    (filterStatus === status || (status === 'all' && !filterStatus))
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  ]"
                >
                  {{ status === 'all' ? '全部' : status === 'active' ? '可用' : status === 'exhausted' ? '已耗尽' : '无效' }}
                </button>
              </div>
              <div class="flex gap-2 items-center">
                <span v-if="syncResult" class="text-sm text-gray-500">
                  同步: {{ syncResult.synced }}/{{ syncResult.total }}
                </span>
                <button
                  @click="handleSyncAll"
                  :disabled="syncing"
                  class="px-4 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {{ syncing ? '同步中...' : '同步远程余额' }}
                </button>
              </div>
            </div>

            <!-- Keys Table -->
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Key</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">余额</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">已用</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">请求数</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                  <tr v-for="key in keys" :key="key.id">
                    <td class="px-4 py-3 text-sm font-mono">
                      {{ key.key.slice(0, 20) }}...{{ key.key.slice(-8) }}
                    </td>
                    <td class="px-4 py-3 text-sm">
                      <span :class="key.balance > 0.1 ? 'text-green-600' : 'text-orange-600'">
                        ${{ key.balance.toFixed(4) }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-500">
                      ${{ key.used_amount.toFixed(4) }}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-500">
                      {{ key.request_count }}
                    </td>
                    <td class="px-4 py-3 text-sm">
                      <span
                        :class="[
                          'px-2 py-1 rounded-full text-xs',
                          key.status === 'active' ? 'bg-green-100 text-green-800' :
                          key.status === 'exhausted' ? 'bg-orange-100 text-orange-800' :
                          'bg-red-100 text-red-800'
                        ]"
                      >
                        {{ key.status === 'active' ? '可用' : key.status === 'exhausted' ? '已耗尽' : '无效' }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-sm space-x-2">
                      <button
                        @click="handleSyncSingle(key.id)"
                        class="text-blue-600 hover:text-blue-800"
                      >
                        同步
                      </button>
                      <button
                        @click="handleDeleteKey(key.id)"
                        class="text-red-600 hover:text-red-800"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Pagination -->
            <div v-if="totalPages > 1" class="mt-4 flex items-center justify-between">
              <div class="text-sm text-gray-500">
                共 {{ totalKeys }} 条，第 {{ currentPage }}/{{ totalPages }} 页
              </div>
              <div class="flex gap-2">
                <button
                  @click="goToPage(1)"
                  :disabled="currentPage === 1"
                  class="px-3 py-1 border rounded text-sm disabled:opacity-50"
                >
                  首页
                </button>
                <button
                  @click="goToPage(currentPage - 1)"
                  :disabled="currentPage === 1"
                  class="px-3 py-1 border rounded text-sm disabled:opacity-50"
                >
                  上一页
                </button>
                <span class="px-3 py-1 text-sm">
                  <input
                    v-model.number="currentPage"
                    type="number"
                    min="1"
                    :max="totalPages"
                    class="w-16 border rounded px-2 py-1 text-center"
                    @change="goToPage(currentPage)"
                  />
                </span>
                <button
                  @click="goToPage(currentPage + 1)"
                  :disabled="currentPage === totalPages"
                  class="px-3 py-1 border rounded text-sm disabled:opacity-50"
                >
                  下一页
                </button>
                <button
                  @click="goToPage(totalPages)"
                  :disabled="currentPage === totalPages"
                  class="px-3 py-1 border rounded text-sm disabled:opacity-50"
                >
                  末页
                </button>
              </div>
            </div>

            <!-- Add Key -->
            <div class="mt-6 border-t pt-6">
              <h3 class="text-lg font-medium mb-4">添加单个 Key</h3>
              <div class="flex gap-4">
                <input
                  v-model="newKey.key"
                  type="text"
                  class="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 px-3 py-2 border"
                  placeholder="sk-xxx..."
                />
                <input
                  v-model.number="newKey.balance"
                  type="number"
                  step="0.01"
                  class="w-32 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 px-3 py-2 border"
                  placeholder="余额"
                />
                <button
                  @click="handleAddKey"
                  class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                >
                  添加
                </button>
              </div>
            </div>
          </div>

          <!-- Models Tab -->
          <div v-if="activeTab === 'models'" class="p-6">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-medium">
                上游支持的模型 
                <span class="text-gray-500 text-sm">(共 {{ modelsTotal }} 个)</span>
              </h3>
              <button
                @click="loadModels"
                :disabled="loadingModels"
                class="px-4 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {{ loadingModels ? '加载中...' : '刷新' }}
              </button>
            </div>

            <div v-if="modelCategories.length === 0 && !loadingModels" class="text-gray-500 text-center py-8">
              暂无模型数据，请先导入 API Key
            </div>

            <div v-else class="space-y-6">
              <div v-for="category in modelCategories" :key="category.name" class="border rounded-lg overflow-hidden">
                <div class="bg-gray-50 px-4 py-3 border-b">
                  <h4 class="font-medium text-gray-900">
                    {{ category.name }}
                    <span class="text-gray-500 text-sm ml-2">({{ category.models.length }} 个模型)</span>
                  </h4>
                </div>
                <div class="divide-y">
                  <div
                    v-for="model in category.models"
                    :key="model.id"
                    class="px-4 py-3 flex justify-between items-center hover:bg-gray-50"
                  >
                    <div>
                      <span class="font-mono text-sm">{{ model.id }}</span>
                      <span
                        v-for="endpoint in model.endpoints"
                        :key="endpoint"
                        class="ml-2 px-2 py-0.5 text-xs rounded bg-gray-200 text-gray-600"
                      >
                        {{ endpoint }}
                      </span>
                    </div>
                    <div class="text-right">
                      <span
                        :class="[
                          'font-medium',
                          model.price >= 0.1 ? 'text-orange-600' : 'text-green-600'
                        ]"
                      >
                        ${{ model.price.toFixed(4) }}
                      </span>
                      <span class="text-gray-400 text-sm">/次</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Pricing Tab -->
          <div v-if="activeTab === 'pricing'" class="p-6">
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">模型匹配</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">单次价格</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">描述</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                  <tr v-for="pricing in pricingList" :key="pricing.id">
                    <td class="px-4 py-3 text-sm font-mono">{{ pricing.model_pattern }}</td>
                    <td class="px-4 py-3 text-sm">
                      <input
                        v-model.number="pricing.price_per_request"
                        type="number"
                        step="0.01"
                        class="w-24 rounded border px-2 py-1"
                        @change="handleUpdatePricing(pricing)"
                      />
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-500">{{ pricing.description }}</td>
                    <td class="px-4 py-3 text-sm">
                      <button
                        @click="handleDeletePricing(pricing.id)"
                        class="text-red-600 hover:text-red-800"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Add Pricing -->
            <div class="mt-6 border-t pt-6">
              <h3 class="text-lg font-medium mb-4">添加模型定价</h3>
              <div class="flex gap-4">
                <input
                  v-model="newPricing.pattern"
                  type="text"
                  class="flex-1 rounded-md border-gray-300 shadow-sm px-3 py-2 border"
                  placeholder="模型匹配 (如 gemini-* 或 gpt-4*)"
                />
                <input
                  v-model.number="newPricing.price"
                  type="number"
                  step="0.01"
                  class="w-32 rounded-md border-gray-300 shadow-sm px-3 py-2 border"
                  placeholder="价格"
                />
                <input
                  v-model="newPricing.description"
                  type="text"
                  class="w-48 rounded-md border-gray-300 shadow-sm px-3 py-2 border"
                  placeholder="描述"
                />
                <button
                  @click="handleAddPricing"
                  class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                >
                  添加
                </button>
              </div>
            </div>

            <!-- Test Pricing -->
            <div class="mt-6 border-t pt-6">
              <h3 class="text-lg font-medium mb-4">测试模型价格</h3>
              <div class="flex gap-4 items-center">
                <input
                  v-model="testModel"
                  type="text"
                  class="flex-1 rounded-md border-gray-300 shadow-sm px-3 py-2 border"
                  placeholder="输入模型名称测试价格"
                  @keyup.enter="handleCheckPrice"
                />
                <button
                  @click="handleCheckPrice"
                  class="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700"
                >
                  查询
                </button>
                <span v-if="testPrice !== null" class="text-lg font-medium">
                  价格: ${{ testPrice.toFixed(4) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Import Tab -->
          <div v-if="activeTab === 'import'" class="p-6">
            <div class="space-y-6">
              <div>
                <h3 class="text-lg font-medium mb-4">批量导入 API Keys</h3>
                <p class="text-sm text-gray-500 mb-4">
                  每行一个 Key，格式：<code class="bg-gray-100 px-1">key,余额</code> 或只写 key（默认余额 0.24）
                </p>
                <textarea
                  v-model="importText"
                  rows="10"
                  class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 px-3 py-2 border font-mono text-sm"
                  placeholder="sk-xxx1,0.24&#10;sk-xxx2,0.40&#10;sk-xxx3"
                ></textarea>
              </div>
              <div class="flex gap-4 items-center">
                <div>
                  <label class="text-sm text-gray-500">默认余额:</label>
                  <input
                    v-model.number="defaultBalance"
                    type="number"
                    step="0.01"
                    class="ml-2 w-24 rounded border px-2 py-1"
                  />
                </div>
                <button
                  @click="handleImport"
                  class="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700"
                >
                  导入
                </button>
              </div>
              <div v-if="importResult" class="bg-gray-50 rounded-md p-4">
                <h4 class="font-medium mb-2">导入结果</h4>
                <p>总计: {{ importResult.total }}</p>
                <p class="text-green-600">成功: {{ importResult.added }}</p>
                <p class="text-orange-600">重复: {{ importResult.duplicates }}</p>
                <p class="text-red-600">错误: {{ importResult.errors }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  setAuthToken,
  getStats,
  getKeys,
  addKey,
  deleteKey,
  importKeys,
  getPricing,
  addPricing,
  updatePricing,
  deletePricing,
  checkModelPrice,
  syncAllKeys,
  syncSingleKey,
  getUpstreamModels
} from './api'

const isLoggedIn = ref(false)
const adminKey = ref('sk-api-exchange-admin')
const loginError = ref('')

const stats = ref({})
const keys = ref([])
const pricingList = ref([])
const activeTab = ref('keys')
const filterStatus = ref(null)

const newKey = ref({ key: '', balance: 0.24 })
const newPricing = ref({ pattern: '', price: 0.08, description: '' })
const testModel = ref('')
const testPrice = ref(null)

const importText = ref('')
const defaultBalance = ref(0.24)
const importResult = ref(null)
const syncing = ref(false)
const syncResult = ref(null)
const modelCategories = ref([])
const modelsTotal = ref(0)
const loadingModels = ref(false)

// 分页
const currentPage = ref(1)
const pageSize = ref(50)
const totalKeys = ref(0)
const totalPages = ref(0)

async function login() {
  try {
    setAuthToken(adminKey.value)
    await getStats()
    isLoggedIn.value = true
    loginError.value = ''
    localStorage.setItem('adminKey', adminKey.value)
    loadData()
  } catch (e) {
    loginError.value = '登录失败，请检查密钥'
  }
}

async function loadData() {
  await Promise.all([loadStats(), loadKeys(), loadPricing()])
}

async function loadStats() {
  try {
    stats.value = await getStats()
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

async function loadKeys() {
  try {
    const data = await getKeys(filterStatus.value, currentPage.value, pageSize.value)
    keys.value = data.keys || []
    totalKeys.value = data.total || 0
    totalPages.value = data.total_pages || 0
  } catch (e) {
    console.error('Failed to load keys:', e)
  }
}

function goToPage(page) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    loadKeys()
  }
}

async function loadPricing() {
  try {
    pricingList.value = await getPricing()
  } catch (e) {
    console.error('Failed to load pricing:', e)
  }
}

async function handleAddKey() {
  if (!newKey.value.key) return
  try {
    await addKey(newKey.value.key, newKey.value.balance)
    newKey.value = { key: '', balance: 0.24 }
    await loadData()
  } catch (e) {
    alert('添加失败: ' + e.message)
  }
}

async function handleDeleteKey(keyId) {
  if (!confirm('确定删除此 Key？')) return
  try {
    await deleteKey(keyId)
    await loadData()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

async function handleAddPricing() {
  if (!newPricing.value.pattern) return
  try {
    await addPricing(newPricing.value.pattern, newPricing.value.price, newPricing.value.description)
    newPricing.value = { pattern: '', price: 0.08, description: '' }
    await loadPricing()
  } catch (e) {
    alert('添加失败: ' + e.message)
  }
}

async function handleUpdatePricing(pricing) {
  try {
    await updatePricing(pricing.id, pricing.price_per_request, pricing.description)
  } catch (e) {
    alert('更新失败: ' + e.message)
  }
}

async function handleDeletePricing(pricingId) {
  if (!confirm('确定删除此定价？')) return
  try {
    await deletePricing(pricingId)
    await loadPricing()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

async function handleCheckPrice() {
  if (!testModel.value) return
  try {
    const result = await checkModelPrice(testModel.value)
    testPrice.value = result.price
  } catch (e) {
    alert('查询失败: ' + e.message)
  }
}

async function handleImport() {
  const lines = importText.value.trim().split('\n').filter(l => l.trim())
  if (lines.length === 0) return

  const keysToImport = lines.map(line => {
    const parts = line.trim().split(',')
    // 去除所有空格
    const key = parts[0].trim().replace(/\s+/g, '')
    const balance = parts[1] ? parseFloat(parts[1].trim()) : defaultBalance.value
    return { key, balance }
  }).filter(item => item.key.startsWith('sk-'))

  if (keysToImport.length === 0) {
    alert('没有有效的 Key（Key 必须以 sk- 开头）')
    return
  }

  try {
    importResult.value = await importKeys(keysToImport)
    await loadData()
  } catch (e) {
    alert('导入失败: ' + e.message)
  }
}

async function handleSyncAll() {
  if (syncing.value) return
  syncing.value = true
  syncResult.value = null
  try {
    syncResult.value = await syncAllKeys()
    await loadData()
  } catch (e) {
    alert('同步失败: ' + e.message)
  } finally {
    syncing.value = false
  }
}

async function handleSyncSingle(keyId) {
  try {
    await syncSingleKey(keyId)
    await loadData()
  } catch (e) {
    alert('同步失败: ' + e.message)
  }
}

async function loadModels() {
  loadingModels.value = true
  try {
    const data = await getUpstreamModels()
    modelCategories.value = data.categories || []
    modelsTotal.value = data.total || 0
  } catch (e) {
    console.error('Failed to load models:', e)
  } finally {
    loadingModels.value = false
  }
}

onMounted(() => {
  const savedKey = localStorage.getItem('adminKey')
  if (savedKey) {
    adminKey.value = savedKey
    login()
  }
})
</script>
