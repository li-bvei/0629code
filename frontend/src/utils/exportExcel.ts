import { saveAs } from 'file-saver'
import * as XLSX from 'xlsx'

export type ExcelRow = Record<string, string | number | boolean | null | undefined>

export const createTimestamp = () => {
  const date = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    '_',
    pad(date.getHours()),
    pad(date.getMinutes()),
  ].join('')
}

export const exportRowsToExcel = (rows: ExcelRow[], sheetName: string, fileName: string) => {
  exportSheetsToExcel([{ rows, sheetName }], fileName)
}

export const exportSheetsToExcel = (sheets: Array<{ rows: ExcelRow[]; sheetName: string }>, fileName: string) => {
  const workbook = XLSX.utils.book_new()
  sheets.forEach((sheet) => {
    const worksheet = XLSX.utils.json_to_sheet(sheet.rows)
    XLSX.utils.book_append_sheet(workbook, worksheet, sheet.sheetName)
  })
  const buffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  saveAs(blob, fileName)
}
