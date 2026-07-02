import type { Reminder } from '../types/api'
import { formatDate, formatDateTime } from './date'

export interface ReminderDisplay {
  target: string
  deadlineType: string
  baseDate: string
  notifyAt: string
  remainingText: string
  caseId: number
  caseNumber: string
  status: string
}

const pad = (value: number) => String(value).padStart(2, '0')

export const toDateKey = (date: Date) => [
  date.getFullYear(),
  pad(date.getMonth() + 1),
  pad(date.getDate()),
].join('-')

const dateKeyToTime = (value: string) => {
  const date = new Date(`${value.slice(0, 10)}T00:00:00`)
  return Number.isNaN(date.getTime()) ? null : date.getTime()
}

export const diffDaysFromToday = (dateKey?: string | null) => {
  if (!dateKey) return null

  const targetTime = dateKeyToTime(dateKey)
  if (targetTime === null) return null

  const todayTime = dateKeyToTime(toDateKey(new Date()))
  if (todayTime === null) return null

  return Math.round((targetTime - todayTime) / 86400000)
}

export const formatRemainingDays = (dateKey?: string | null, useDeadlinePrefix = false) => {
  const days = diffDaysFromToday(dateKey)
  if (days === null) return '-'
  if (days === 0) return '今日'
  if (days < 0) return `期限切れ${Math.abs(days)}日`
  return useDeadlinePrefix ? `期限まであと${days}日` : `あと${days}日`
}

export const parseReminderNote = (note?: string | null) => {
  const result: Record<string, string> = {}
  if (!note) return result

  note.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim()
    if (!trimmed) return

    const separatorIndex = trimmed.includes('：')
      ? trimmed.indexOf('：')
      : trimmed.indexOf(':')
    if (separatorIndex <= 0) return

    const key = trimmed.slice(0, separatorIndex).trim()
    const value = trimmed.slice(separatorIndex + 1).trim()
    if (key && value) result[key] = value
  })

  return result
}

export const getReminderDateKey = (reminder: Reminder) => reminder.remind_at?.slice(0, 10) || ''

export const getReminderDisplay = (reminder: Reminder): ReminderDisplay => {
  const note = parseReminderNote(reminder.note)
  const baseDateKey = note['基準日']
  const fallbackDateKey = getReminderDateKey(reminder)
  const target = note['氏名'] || note['会社名'] || reminder.title || '-'
  const deadlineType = note['期限種別'] || '-'
  const baseDate = baseDateKey
    ? formatDate(baseDateKey)
    : note['基準月'] || '-'
  const remainingBaseDate = baseDateKey || fallbackDateKey

  return {
    target,
    deadlineType,
    baseDate,
    notifyAt: formatDateTime(reminder.remind_at),
    remainingText: formatRemainingDays(remainingBaseDate, Boolean(baseDateKey)),
    caseId: reminder.case,
    caseNumber: reminder.case_number || '-',
    status: reminder.is_done ? '完了' : '未完了',
  }
}
