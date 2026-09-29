import http from '../services/http'

export interface SearchItem {
  id: number
  title: string
  subtitle: string
  url: string
  can_open: boolean
  access_level?: string
  note?: string
}

export interface SearchGroup {
  type: string
  label: string
  items: SearchItem[]
}

export interface SearchResponse {
  query_too_short: boolean
  min_length?: number
  groups: SearchGroup[]
}

export const globalSearch = async (q: string) => (await http.get<SearchResponse>('/search/', { params: { q } })).data
