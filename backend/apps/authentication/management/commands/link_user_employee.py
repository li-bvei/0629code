from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction

from apps.authentication.management.base import SafeCommand
from apps.employees.models import Employee


class Command(SafeCommand):
    help = (
        'User と Employee を1対1で関連付ける。username と担当者名（またはID）で指定し、'
        'DBのIDを前提にしない。既定 dry-run。'
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--plan', action='store_true', help='現在の User / Employee 一覧を表示するだけ')
        parser.add_argument('--map', action='append', default=[], help='username:担当者名 または username:#担当者ID')
        parser.add_argument('--create-employee', action='append', default=[], help='username:新規担当者名')
        parser.add_argument('--unlink', action='append', default=[], help='username（関連を解除）')

    def show_plan(self):
        User = get_user_model()
        self.stdout.write('--- User（認証情報は表示しない）---')
        for u in User.objects.order_by('id'):
            emp = getattr(u, 'employee', None) if hasattr(u, 'employee') else None
            self.stdout.write(
                f'id={u.pk} username={u.username} 氏名={u.last_name}{u.first_name} '
                f'active={u.is_active} staff={u.is_staff} superuser={u.is_superuser} '
                f'employee={emp.name if emp else "-"}'
            )
        self.stdout.write('--- Employee ---')
        for e in Employee.objects.order_by('id'):
            self.stdout.write(f'id={e.pk} 氏名={e.name} active={e.is_active} user={e.user.username if e.user_id else "-"}')

    def find_employee(self, ref):
        if ref.startswith('#'):
            try:
                return Employee.objects.get(pk=int(ref[1:]))
            except (ValueError, Employee.DoesNotExist) as exc:
                raise CommandError(f'担当者が見つかりません: {ref}') from exc
        matches = list(Employee.objects.filter(name=ref))
        if len(matches) != 1:
            raise CommandError(f'担当者名「{ref}」の一致件数が {len(matches)} 件です（1件である必要があります）。#ID で指定してください。')
        return matches[0]

    def handle(self, *args, **options):
        if options['plan'] or not (options['map'] or options['create_employee'] or options['unlink']):
            self.show_plan()
            return
        operations = []
        for item in options['map']:
            username, _, ref = item.partition(':')
            user = self.get_user(username)
            employee = self.find_employee(ref)
            if employee.user_id and employee.user_id != user.pk:
                raise CommandError(f'{employee.name} は既に別のユーザー（{employee.user.username}）に関連付いています。')
            existing = Employee.objects.filter(user=user).exclude(pk=employee.pk).first()
            if existing:
                raise CommandError(f'{username} は既に {existing.name} に関連付いています（先に --unlink）。')
            operations.append(('link', user, employee))
        for item in options['create_employee']:
            username, _, name = item.partition(':')
            user = self.get_user(username)
            if not name:
                raise CommandError('担当者名が空です。')
            if Employee.objects.filter(user=user).exists():
                raise CommandError(f'{username} は既に担当者に関連付いています。')
            if Employee.objects.filter(name=name).exists():
                raise CommandError(f'担当者「{name}」は既に存在します。--map で関連付けてください。')
            operations.append(('create', user, name))
        for username in options['unlink']:
            user = self.get_user(username)
            employee = Employee.objects.filter(user=user).first()
            if employee is None:
                raise CommandError(f'{username} には関連付いた担当者がいません。')
            operations.append(('unlink', user, employee))

        for op, user, target in operations:
            label = target if isinstance(target, str) else f'{target.name}（id={target.pk}）'
            self.stdout.write(f'{op}: {user.username}（id={user.pk}） ↔ {label}')
        if not self.confirm(options, f'{len(operations)} 件の関連付けを変更します。'):
            return
        with transaction.atomic():
            for op, user, target in operations:
                if op == 'link':
                    target.user = user
                    target.save(update_fields=['user', 'updated_at'])
                    employee = target
                elif op == 'create':
                    employee = Employee.objects.create(name=target, user=user)
                else:
                    employee = target
                    employee.user = None
                    employee.save(update_fields=['user', 'updated_at'])
                self.audit('user_employee_link', obj=employee, extra={'op': op, 'username': user.username})
        self.stdout.write(self.style.SUCCESS('変更しました。'))
