<template>
  <section class="page" data-module="manifest">
    <header class="page-head">
      <div>
        <h2>单证处理管理</h2>
        <p class="page-desc">维护单证，围绕单证编号、单证类型、关联航次、申报箱量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="toggleCreate">
          {{ showCreate ? '收起登记' : '登记单证' }}
        </button>
        <button class="btn" type="button" @click="exportRows">导出单证处理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="filter-bar create-panel" @submit.prevent="submitCreate">
      <label v-for="field in rules?.form_fields ?? []" :key="field" class="filter-item">
        <span>{{ field }}<em v-if="rules?.required_fields.includes(field)" class="required-mark">*</em></span>
        <input v-model.trim="form[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="toggleCreate">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="transition in rules?.transitions ?? []"
              :key="transition.action"
              class="link"
              type="button"
              :disabled="!canRun(row, transition)"
              :title="canRun(row, transition) ? '' : `当前状态不允许${transition.action}`"
              @click="runAction(transition.action, row)"
            >
              {{ transition.action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无单证处理数据，可先登记单证</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条单证处理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

type TransitionRule = {
  action: string
  target: string
  from_statuses: string[]
}

type ManifestRules = {
  form_fields: string[]
  required_fields: string[]
  statuses: string[]
  initial_status: string
  transitions: TransitionRule[]
}

const ENDPOINT = '/api/manifest'
const columns = ["单证编号", "单证类型", "关联航次", "申报箱量", "申报人", "提交时间", "审核人员", "单证状态"]
const stats = [{"label": "待提交单证", "value": 0}, {"label": "已提交单证", "value": 0}, {"label": "退回单证数", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

// 必填项与流转前提只认 /rules 下发的那一份，页面不再自写判断。
const rules = ref<ManifestRules | null>(null)
const showCreate = ref(false)
const form = reactive<Record<string, string>>({})

function canRun(row: Row, transition: TransitionRule): boolean {
  return transition.from_statuses.includes(String(row.status ?? ''))
}

function toggleCreate() {
  showCreate.value = !showCreate.value
  for (const field of rules.value?.form_fields ?? []) {
    form[field] = ''
  }
  errorMessage.value = ''
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function submitCreate() {
  errorMessage.value = ''
  const required = rules.value?.required_fields ?? []
  const missing = required.filter((field) => !form[field]?.trim())
  if (missing.length) {
    errorMessage.value = `缺少必填字段：${missing.join('、')}`
    return
  }
  const values: Record<string, string> = {}
  for (const field of rules.value?.form_fields ?? []) {
    values[field] = form[field]
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '单证登记未生效，请稍后重试')
    }
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单证登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '单证处理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单证处理操作失败'
  }
}

async function loadRules() {
  const response = await request(`${ENDPOINT}/rules`)
  if (!response.ok) {
    throw new Error('单证判断规则读取失败')
  }
  rules.value = await response.json()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('单证列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单证处理列表读取失败'
  }
}

onMounted(async () => {
  try {
    await loadRules()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单证判断规则读取失败'
  }
  await reload()
})
</script>

<style scoped>
.create-panel {
  flex-wrap: wrap;
  align-items: flex-end;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--border-color, #d9e1ec);
  border-radius: 8px;
  background: #f8fafc;
}

.required-mark {
  margin-left: 2px;
  color: #d4473a;
  font-style: normal;
}

.link:disabled {
  color: #aab4c2;
  cursor: not-allowed;
}
</style>
