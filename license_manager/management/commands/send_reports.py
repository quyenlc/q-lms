from datetime import timedelta
from django.db.models import F
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.template.loader import get_template
from license_manager.models import License, LicenseAssignment


class Command(BaseCommand):
    help = '''Send license reports to designated email addresses:
    - Licenses expiring soon
    - Licenses available to use
    - Softwares using without licenses'''
    today = timezone.now()

    def add_arguments(self, parser):
        default_subject = 'License Reports ' + self.today.strftime("%d %B, %Y %H:%M:%S")
        default_sender = 'lms@punch.local'
        parser.add_argument(
            '-s', '--subject', type=str,
            default=default_subject,
            help='Set subject of email')
        parser.add_argument(
            '-t', '--to', type=str, nargs='+', required=True,
            help='Email addresses to send the reports')
        parser.add_argument(
            '-f', '--from', type=str, default=default_sender,
            help='Email addresss of the sender. Default: %s' % default_sender)
        parser.add_argument(
            '-u', '--unlicensed', action='store_true', help='Include unlicensed softwares')

    def handle(self, *args, **options):
        WARNING_DAYS = 30
        warning_date = timezone.now().date() + timedelta(WARNING_DAYS)
        expiring_licenses = License.objects.filter(
            license_type=License.LICENSE_SUBSCRIPTION,
            ended_date__lt=warning_date)
        available_licenses = (License.objects.annotate(remaining=F('total') - F('used_total'))
                                             .filter(total__gt=F('used_total'))
                                             .exclude(
                                                license_type=License.LICENSE_SUBSCRIPTION,
                                                ended_date__lt=timezone.now().date())
                                             .order_by('description'))
        if options['unlicensed']:
            unlicensed_softwares = LicenseAssignment.get_unlicensed_softwares()
        else:
            unlicensed_softwares = None
        t = get_template('email/license_reports.html')
        summary_html = t.render({
            'today': self.today.strftime("%d %B, %Y"),
            'expiring_licenses': expiring_licenses,
            'available_licenses': available_licenses,
            'unlicensed_softwares': unlicensed_softwares
        })
        send_mail(
            options['subject'],
            'Not support plain text reports',
            options['from'],
            options['to'],
            html_message=summary_html,
            fail_silently=False)
        self.stdout.write(self.style.SUCCESS('Successfully sent email reports'))
