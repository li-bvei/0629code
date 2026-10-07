from django.conf import settings
from django.db import models


class Task(models.Model):
    """案件のタスク。P3 から「毎日の計画」の項目も同じモデルで扱う（別のタスク仕組みは作らない）。

    - 毎日の計画の項目：work_date（作業日）と responsible_employee（本人）を持つ。case は任意（社内作業は空）。
    - 従来の案件タスク：work_date が空で case が必須（従来どおり）。
    - 結転：未完了の項目を別の日へ送ると、元の項目は status=carried_over のまま元の日に残り、
      新しい項目の carried_from が元の項目を指す（元の日付の痕跡を残す）。
    """

    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_PAUSED = 'paused'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CARRIED_OVER = 'carried_over'

    STATUS_CHOICES = [
        (STATUS_PENDING, '未開始'),
        (STATUS_IN_PROGRESS, '進行中'),
        (STATUS_COMPLETED, '完了'),
        (STATUS_PAUSED, '一時停止'),
        (STATUS_CANCELLED, '取消'),
        (STATUS_CARRIED_OVER, '結転済み'),
    ]
    # 未完了（結転・報告で「未完了」とするもの）
    OPEN_STATUSES = (STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_PAUSED)

    PRIORITY_HIGH = 'high'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_LOW = 'low'
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH, '高'),
        (PRIORITY_NORMAL, '中'),
        (PRIORITY_LOW, '低'),
    ]

    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='tasks',
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    responsible_employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        related_name='tasks',
        blank=True,
        null=True,
    )
    sort_order = models.PositiveIntegerField(default=0)
    due_date = models.DateField(blank=True, null=True)
    completed_at = models.DateField(blank=True, null=True)
    # --- 毎日の計画（P3） ---
    work_date = models.DateField('作業日', blank=True, null=True, db_index=True)
    priority = models.CharField('優先度', max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    result_note = models.TextField('結果メモ', blank=True, default='')
    carried_from = models.OneToOneField(
        'self',
        verbose_name='結転元',
        on_delete=models.SET_NULL,
        related_name='carried_to',
        blank=True,
        null=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='登録者',
        on_delete=models.SET_NULL,
        related_name='+',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_tasks'
        ordering = ['sort_order', 'id']
        indexes = [models.Index(fields=['responsible_employee', 'work_date'], name='task_plan_owner_date_idx')]

    def __str__(self):
        return self.title

    @property
    def is_plan_item(self):
        return self.work_date is not None


class DailyWorkReport(models.Model):
    """1 日の業務報告（社内に保存するだけ。メール・チャット等へは送らない）。

    生成時の計画項目のスナップショット（snapshot）と生成文（generated_text）を残し、利用者が編集するのは
    final_text だけ。後から計画項目を変えても、保存済みの報告は変わらない。
    下書きは再生成できる（スナップショットと文を作り直す）。確定すると再生成できないが、本文は編集できる。
    """

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CHOICES = [(STATUS_DRAFT, '下書き'), (STATUS_CONFIRMED, '確定')]

    employee = models.ForeignKey(
        'employees.Employee', verbose_name='担当者', on_delete=models.PROTECT, related_name='daily_reports',
    )
    report_date = models.DateField('報告日')
    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    snapshot = models.JSONField('生成時の計画項目', default=dict, blank=True)
    generated_text = models.TextField('生成文', blank=True)
    final_text = models.TextField('報告本文', blank=True)
    generated_at = models.DateTimeField('生成日時', null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='生成者', on_delete=models.SET_NULL, related_name='+',
        null=True, blank=True,
    )
    confirmed_at = models.DateTimeField('確定日時', null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='確定者', on_delete=models.SET_NULL, related_name='+',
        null=True, blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='最終編集者', on_delete=models.SET_NULL, related_name='+',
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_work_reports'
        ordering = ['-report_date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'report_date'], name='daily_report_one_per_employee_day'),
        ]
        verbose_name = '業務報告'
        verbose_name_plural = '業務報告'

    def __str__(self):
        return f'{self.report_date} {self.employee_id}'
