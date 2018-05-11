from django.shortcuts import render
from django.db.models import F, Q
from django.utils.html import format_html

from dal import autocomplete

from .models import Software, License, LicenseAssignment


class LicenseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # TODO: check permissions
        if not self.request.user.is_authenticated:
            return License.objects.none()
        software_id = self.forwarded.get('software', None)
        license_id = self.forwarded.get('license', None)

        if software_id:
            qs = License.objects.annotate(remaining=F('total') - F('used_total')).filter(softwares=software_id).order_by('-used_total')
            if license_id:
                return qs.filter(Q(remaining__gt=0) | Q(pk=license_id))
            else:
                return qs.filter(remaining__gt=0)
        else:
            return License.objects.none()

    def get_result_label(self, item):
        current_lic = self.forwarded.get('license', None)
        text = '<strong>{0}</strong>'
        if current_lic and current_lic == item.pk:
            text += ' (current)'
        text += '<br>Total: {1}&nbsp;&nbsp;Used: {2}'
        return format_html(text, item.description, item.total, item.used_total)


class LicensedSoftwareAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        software_family = self.forwarded.get('software_family', None)
        qs = Software.objects.all()
        if software_family:
            qs = qs.filter(software_family=software_family)
        return qs
