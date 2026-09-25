<template>
  <section class="page" data-module="manifest">
    <header class="page-head">
      <div>
        <h2>单证处理管理</h2>
        <p class="page-desc">维护单证，围绕单证编号、单证类型、关联航次、申报箱量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记单证</button>
        <button class="btn" type="button" @click="exportRows">导出单证处理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

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
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
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
import { computed, onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>

type ManifestRules = {
  module: string
  fields: string[]
  required_fields: string[]
  statuses: string[]
  actions: { name: string; target: string; abnormal: boolean }[]
}

const ENDPOINT = '/api/manifest'
// 单证该填哪些项、什么时候能流转，只以后端 /api/manifest/rules 为唯一来源，
// 页面不再自己抄一份，保证与校验接口结论同源。
const columns = ref<string[]>([])
const actions = ref<string[]>([])
const stats = [{"label": "待提交单证", "value": 0}, {"label": "已提交单证", "value": 0}, {"label": "退回单证数", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = computed(() => columns.value.slice(0, 3))

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '单证登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('单证处理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单证处理操作失败'
  }
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

async function loadRules() {
  const rules = await fetchJson<ManifestRules>(`${ENDPOINT}/rules`)
  columns.value = rules.fields
  actions.value = rules.actions.map((item) => item.name)
}

onMounted(async () => {
  errorMessage.value = ''
  try {
    await loadRules()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '单证规则读取失败'
    return
  }
  await reload()
})
</script>
