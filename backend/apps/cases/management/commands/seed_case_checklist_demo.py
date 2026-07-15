from django.core.management.base import BaseCommand

from apps.cases.demo_data import seed_standard_case_checklist_templates


class Command(BaseCommand):
    help = 'Compatibility command. Import standard case checklist templates.'

    def handle(self, *args, **options):
        result = seed_standard_case_checklist_templates()
        self.stdout.write(self.style.SUCCESS(
            'Standard case checklist templates imported: '
            f"{result['templates_created']} templates created, "
            f"{result['templates_updated']} templates updated, "
            f"{result['template_items_created']} template items created, "
            f"{result['template_items_updated']} template items updated."
        ))
