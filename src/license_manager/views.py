from django.shortcuts import render
from django.db.models import F, Q
from django.utils.html import format_html

from dal import autocomplete

from .models import Software, License, LicenseKey, LicensedSoftware


class LicenseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # TODO: check permissions
        if not self.request.user.is_authenticated:
            return License.objects.none()
        software_id = self.forwarded.get('software', None)
        platform_id = self.forwarded.get('platform', None)
        license_id = self.forwarded.get('license', None)
        platforms = [LicensedSoftware.PLATFORM_ALL]
        if software_id and platform_id:
            platforms.append(platform_id)
            qs = License.objects.annotate(remaining=F('total') - F('used_total'))
            f = Q(softwares=software_id) & Q(licensedsoftware__platform__in=platforms)
            sub_f = Q(remaining__gt=0)
            if license_id:
                sub_f |= Q(pk=license_id)
            return qs.filter(f & sub_f).order_by('-used_total')
        else:
            return License.objects.none()

    def get_result_label(self, item):
        current_lic = self.forwarded.get('license', None)
        text = '<strong>{0}</strong>'
        if current_lic and current_lic == item.pk:
            text += ' (current)'
        text += '<br>Total: {1}&nbsp;&nbsp;Used: {2}'
        return format_html(text, item.description, item.total, item.used_total)


class SoftwareAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Software.objects.none()
        software_family = self.forwarded.get('software_family', None)
        qs = Software.objects.all()
        if software_family:
            qs = qs.filter(software_family=software_family)
        return qs


class LicenseKeyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LicenseKey.objects.none()
        software_id = self.forwarded.get('software', None)
        license_id = self.forwarded.get('license', None)
        platform_id = self.forwarded.get('platform', None)
        license_key_id = self.forwarded.get('license_key', None)
        return LicenseKey.objects.get_available_keys(software_id, license_id, platform_id, license_key_id)

    def get_result_label(self, item):
        text = '''{}<br>
            <strong>Platform:</strong> {}&nbsp;&nbsp;
            <strong>Type:</strong> {}'''
        return format_html(
            text, item.serial_key,
            item.licensed_software.get_platform_display(),
            item.get_activation_type_display(),
        )
