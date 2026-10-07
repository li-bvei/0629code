// 業務フロー（P4）を持つ案件の表示用関数。フローを持たない案件は従来の 13 段階（caseStatus.ts）のまま。
import type { Case, CaseStatus, CaseTypeMaster, WorkflowStageOption } from '../types/api'
import { getCaseDisplayStatus } from './caseStatus'

type CaseLike = Pick<Case, 'status'> & Partial<Pick<Case, 'workflow_template' | 'workflow_stage' | 'workflow_stage_name' | 'workflow_stages'>>

export const isWorkflowCase = (item: CaseLike | null | undefined) => Boolean(item?.workflow_template)

/** 一覧などで表示する進捗名：フローを持つ案件は段階名、従来の案件は 13 段階の名称。 */
export const caseProgressLabel = (item: CaseLike | null | undefined) => {
  if (!item) return '-'
  if (item.workflow_stage_name) return item.workflow_stage_name
  return getCaseDisplayStatus(item.status)
}

/** ステッパーに並べる段階（取下げは例外表示なので含めない）。 */
export const stageSteps = (item: CaseLike | null | undefined): WorkflowStageOption[] => (
  (item?.workflow_stages ?? []).filter((stage) => !stage.is_withdrawn)
)

export const currentStepIndex = (item: CaseLike | null | undefined) => {
  const steps = stageSteps(item)
  const index = steps.findIndex((stage) => stage.id === item?.workflow_stage)
  return index
}

export const isWithdrawnStage = (item: CaseLike | null | undefined) => (
  (item?.workflow_stages ?? []).some((stage) => stage.id === item?.workflow_stage && stage.is_withdrawn)
)

/** 変更先の候補：同じフローの有効な段階（現在の段階以外）。取下げ・取下げからの復帰も選べる。 */
export const stageChoices = (item: CaseLike | null | undefined): WorkflowStageOption[] => (
  (item?.workflow_stages ?? []).filter((stage) => stage.is_active && stage.id !== item?.workflow_stage)
)

/** 受付・案件作成で申請区分が必要か（種別が未選択なら従来どおり必要として扱う）。 */
export const needsApplicationCategory = (caseType: Pick<CaseTypeMaster, 'requires_application_category'> | null | undefined) => (
  caseType ? caseType.requires_application_category !== false : true
)

export const STATUS_FOR_STAGE_TAG: Partial<Record<CaseStatus, 'info' | 'success' | 'warning' | 'danger' | 'primary'>> = {
  accepted: 'primary',
  completed: 'success',
  withdrawn: 'info',
}
