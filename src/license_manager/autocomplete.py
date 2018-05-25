from django.db.models import F, Q
from django.utils.html import format_html
from django.contrib.auth.models import User

from dal import autocomplete

from .models import Software, Platform, License, LicenseKey


class LicenseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # TODO: check permissions
        if not self.request.user.is_authenticated:
            return License.objects.none()
        software_id = self.forwarded.get('software', None)
        software_ids = self.forwarded.get('softwares', None)
        if software_ids and software_id not in software_ids:
            software_ids.append(software_id)
        if not software_ids:
            software_ids = [software_id]

        platform_id = self.forwarded.get('platform', None)
        license_id = self.forwarded.get('license', None)
        if software_ids and platform_id and Software.objects.filter(pk__in=software_ids, platforms=platform_id).exists():
            f = Q(softwares__in=software_ids)
            sub_f = Q(remaining__gt=0)
            if license_id:
                sub_f |= Q(pk=license_id)
            return License.objects.filter(f & sub_f).order_by('remaining')
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
        platform_id = self.forwarded.get('platform', None)
        qs = Software.objects.all()
        if software_family:
            qs = qs.filter(software_family=software_family)
        if platform_id:
            qs = qs.filter(platforms=platform_id)
        if self.q:
            qs = qs.filter(Q(software_family__name__icontains=self.q) | Q(name__icontains=self.q))
        return qs


class LicenseKeyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LicenseKey.objects.none()
        software_id = self.forwarded.get('software', None)
        platform_id = self.forwarded.get('platform', None)
        license_id = self.forwarded.get('license', None)
        license_key_id = self.forwarded.get('license_key', None)
        return LicenseKey.objects.get_available_keys(software_id, license_id, platform_id, license_key_id)

    def get_result_label(self, item):
        text = '''{}<br>
            <strong>Type:</strong> {}'''
        return format_html(
            text, item.serial_key,
            item.get_activation_type_display(),
        )


class PlatformAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LicenseKey.objects.none()
        qs = Platform.objects.all()
        software_id = self.forwarded.get('software', None)
        if software_id:
            try:
                sw = Software.objects.get(pk=software_id)
                qs = sw.platforms.all()
            except:
                return Platform.objects.none()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return User.objects.none()
        if self.q:
            return User.objects.filter(username__startswith=self.q)
        return User.objects.all()
