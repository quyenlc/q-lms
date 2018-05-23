from django import forms
from django.contrib.auth.models import User

from dal import autocomplete
from dal import forward

from .models import (
    Software, LicenseKey, Platform,
    License, LicensedSoftware, LicenseAssignment)


class SoftwareForm(forms.ModelForm):
    class Meta:
        model = Software
        fields = '__all__'
        widgets = {
            'platforms': autocomplete.ModelSelect2Multiple(
                url='platform_autocomplete',
            ),
        }


class LicenseKeyForm(forms.ModelForm):
    # def clean_platforms(self):
    #     platforms = self.cleaned_data.get('platforms', None)
    #     if not platforms:
    #         return None
    #     sw = self.instance.licensed_software.software
    #     for p in platforms:
    #         if not sw.platforms.filter(pk=p.pk).exists():
    #             raise forms.ValidationError("%s is not available on %s platform" % (str(sw), p.name))

    #     return platforms

    class Meta:
        model = LicenseKey
        fields = '__all__'
        widgets = {
            'platforms': autocomplete.ModelSelect2Multiple(
                url='platform_autocomplete',
                forward=['software'],
            ),
        }


class LicensedSoftwareForm(forms.ModelForm):
    def clean_software(self):
        license = self.cleaned_data.get('license', None)
        software = self.cleaned_data.get('software', None)

        if license.software_family_id != software.software_family_id:
            raise forms.ValidationError("Software has same software family as license.")
        return software

    class Meta:
        model = LicensedSoftware
        fields = '__all__'
        widgets = {
            'software': autocomplete.ModelSelect2(
                url='software_autocomplete',
                forward=['software_family'],
                attrs={'data-html': True}
            ),
        }


class LicenseForm(forms.ModelForm):
    total = forms.IntegerField(min_value=1)

    def clean_ended_date(self):
        ended_date = self.cleaned_data.get('ended_date', None)
        license_type = self.cleaned_data.get('license_type', None)
        if not ended_date and license_type == License.LICENSE_SUBSCRIPTION:
            raise forms.ValidationError('End date must be set when license type is subscription-based')

        started_date = self.cleaned_data.get('started_date', None)
        if started_date and ended_date:
            delta = ended_date - started_date
            if delta.days < 0:
                raise forms.ValidationError('End date must be after start date')
            if delta.days < 30:
                raise forms.ValidationError('End date is too close to start date. Must be at least 30 days away.')

        purchased_date = self.cleaned_data.get('purchased_date', None)
        if purchased_date and ended_date:
            delta = ended_date - purchased_date
            if delta.days < 0:
                raise forms.ValidationError('End date must be after purchasing date')
            if delta.days < 30:
                raise forms.ValidationError('End date is too closed to purchasing date. Must be at least 30 days away.')
        return ended_date

    def clean_started_date(self):
        started_date = self.cleaned_data.get('started_date', None)
        license_type = self.cleaned_data.get('license_type', None)
        if not started_date and license_type == License.LICENSE_SUBSCRIPTION:
            raise forms.ValidationError('Start date must be set when license type is subscription-based')

        purchased_date = self.cleaned_data.get('purchased_date', None)
        if purchased_date and started_date and purchased_date > started_date:
            raise forms.ValidationError('Start date must be after purchasing date')

        return started_date

    def clean_total(self):
        total = self.cleaned_data.get('total', None)
        if self.instance.pk:
            used_total = self.instance.used_total
            if total < used_total:
                raise forms.ValidationError('Total must be greater than used total.')
        return total

    def clean_oem_device(self):
        license_type = self.cleaned_data.get('license_type', None)
        oem_device = self.cleaned_data.get('oem_device', None)
        if license_type == License.LICENSE_OEM and not oem_device:
            raise forms.ValidationError('OEM device is required for OEM licenes')
        return oem_device

    class Meta:
        model = License
        fields = '__all__'


class LicenseAssignmentForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(LicenseAssignmentForm, self).__init__(*args, **kwargs)
        license_widget = self.fields['license'].widget.widget
        license_key_widget = self.fields['license_key'].widget.widget
        license_forward = ['software', 'platform']
        license_key_forward = ['software', 'platform', 'license']
        if self.instance.pk:
            license_forward.append(
                forward.Const(self.instance.license_id, 'license'))
            license_key_forward.append(
                forward.Const(self.instance.license_key_id, 'license_key'))
        license_widget.forward = license_forward
        license_key_widget.forward = license_key_forward

    def clean_platform(self):
        platform = self.cleaned_data.get('platform', None)
        if not platform:
            return None
        sw = self.cleaned_data.get('software', None)
        if not sw.platforms.filter(pk=platform.pk).exists():
            raise forms.ValidationError("%s is not available on %s platform" % (str(sw), str(platform)))
        return platform

    def clean_license(self):
        lic = self.cleaned_data.get('license', None)

        if not lic:
            return None

        soft = self.cleaned_data.get('software', None)
        if soft and not lic.softwares.filter(pk=soft.id):
            raise forms.ValidationError("License mismatch")

        is_create = True if not self.instance else False
        has_changed = 'license' in self.changed_data
        if (is_create or has_changed) and (lic.total - lic.used_total == 0):
            raise forms.ValidationError("Not enough license")

        return lic

    def clean_license_key(self):
        lic_key = self.cleaned_data.get('license_key', None)
        if not lic_key:
            return None

        platform = self.cleaned_data.get('platform', None)
        if not lic_key.platforms.filter(pk=platform.pk).exists():
            raise forms.ValidationError("Platform mismatch")

        soft = self.cleaned_data.get('software', None)
        lic = self.cleaned_data.get('license', None)
        lic_soft = lic_key.licensed_software
        if (not soft or not lic or lic_soft.license_id != lic.pk or lic_soft.software_id != soft.pk):
            raise forms.ValidationError("License key mismatch")

        is_create = True if not self.instance else False
        has_changed = 'license_key' in self.changed_data
        if (is_create or has_changed) and not lic_key.is_available():
            raise forms.ValidationError("License key unavailable")
        return lic_key

    class Meta:
        model = LicenseAssignment
        fields = '__all__'
        widgets = {
            'user': autocomplete.ModelSelect2(
                url='user_autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
            'software': autocomplete.ModelSelect2(
                url='software_autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
            'platform': autocomplete.ModelSelect2(
                url='platform_autocomplete',
                forward=['software'],
                attrs={
                    'data-minimum-results-for-search': 5,
                }
            ),
            'license': autocomplete.ModelSelect2(
                url='license_autocomplete',
                attrs={'data-html': True}
            ),
            'license_key': autocomplete.ModelSelect2(
                url='license_key_autocomplete',
                attrs={'data-html': True}
            ),
        }

    class Media:
        js = (
            'license_manager/linked_data.js',
        )


class LicenseBulkAssignForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            url="user_autocomplete",
            attrs={
                'data-placeholder': 'Select one or more users',
            }
        )
    )
    platform = forms.ModelChoiceField(
        queryset=Platform.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="platform_autocomplete",
            attrs={
                'data-placeholder': 'Select a platform',
            }
        )
    )
    softwares = forms.ModelMultipleChoiceField(
        queryset=Software.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            url="software_autocomplete",
            forward=['platform'],
            attrs={
                'data-placeholder': 'Select one or more softwares',
            }
        )
    )

    def clean_softwares(self):
        softwares = self.cleaned_data.get('softwares', None)
        if not softwares:
            return None
        platform = self.cleaned_data.get('platform', None)
        invalid_softwares = softwares.exclude(platforms=platform)
        if invalid_softwares:
            names = [str(sw) for sw in invalid_softwares]
            raise forms.ValidationError("%s is/are not available on %s" % (', '.join(names), platform.name))
        return softwares

    class Media:
        css = {
            'all': ('admin/css/widgets.css',),
        }
        js = (
            'license_manager/bulk_assign_form/linked_data.js',
        )
