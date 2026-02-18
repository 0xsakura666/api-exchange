import axios from 'axios'

const API_BASE = import.meta.env.PROD ? '' : ''

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
})

export function setAuthToken(token) {
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

export async function getStats() {
  const response = await api.get('/admin/stats')
  return response.data
}

export async function getKeys(status = null, page = 1, pageSize = 50) {
  const params = { page, page_size: pageSize }
  if (status) params.status = status
  const response = await api.get('/admin/keys', { params })
  return response.data
}

export async function addKey(key, balance) {
  const response = await api.post('/admin/keys', { key, balance })
  return response.data
}

export async function deleteKey(keyId) {
  const response = await api.delete(`/admin/keys/${keyId}`)
  return response.data
}

export async function importKeys(keys) {
  const response = await api.post('/admin/keys/import', { keys })
  return response.data
}

export async function getPricing() {
  const response = await api.get('/admin/pricing')
  return response.data
}

export async function addPricing(modelPattern, pricePerRequest, description) {
  const response = await api.post('/admin/pricing', {
    model_pattern: modelPattern,
    price_per_request: pricePerRequest,
    description
  })
  return response.data
}

export async function updatePricing(pricingId, pricePerRequest, description) {
  const response = await api.put(`/admin/pricing/${pricingId}`, {
    model_pattern: '',
    price_per_request: pricePerRequest,
    description
  })
  return response.data
}

export async function deletePricing(pricingId) {
  const response = await api.delete(`/admin/pricing/${pricingId}`)
  return response.data
}

export async function checkModelPrice(model) {
  const response = await api.get('/admin/pricing/check', { params: { model } })
  return response.data
}

export async function getUpstreamModels() {
  const response = await api.get('/admin/models')
  return response.data
}

export async function deleteInvalidKeys() {
  const response = await api.delete('/admin/keys/invalid/batch')
  return response.data
}

export async function getTokens() {
  const response = await api.get('/admin/tokens')
  return response.data
}

export async function createToken(name) {
  const response = await api.post('/admin/tokens', { name })
  return response.data
}

export async function toggleToken(tokenId, enabled) {
  const response = await api.put(`/admin/tokens/${tokenId}/toggle`, null, { params: { enabled } })
  return response.data
}

export async function deleteToken(tokenId) {
  const response = await api.delete(`/admin/tokens/${tokenId}`)
  return response.data
}

export default api
