from django import forms
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.conf.urls import url
from django.contrib import admin
from django.contrib import messages
from django.db.models import F, Q
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import PermissionDenied
from django.template.response import SimpleTemplateResponse, TemplateResponse

from dal import autocomplete
from dal import forward
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter

import nested_admin

from .models import (
    Supplier, SoftwareFamily, Software, LicenseImage, LicenseKey,
    Platform, License, LicensedSoftware, LicenseAssignment, LicenseSummary)
from .actions import delete_license_assignments


class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact']
    search_fields = ['name']


class SoftwareFamilyAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


class SoftwareForm(forms.ModelForm):
    class Meta:
        model = Software
        fields = '__all__'
        widgets = {
            'platforms': autocomplete.ModelSelect2Multiple(
                url='platform_autocomplete',
            ),
        }


class SoftwareAdmin(admin.ModelAdmin):
    form = SoftwareForm
    list_display = ['__str__', 'version', 'get_platforms']
    search_fields = ['name', 'version', 'software_family__name']
    select_related = ('software_family',)

    def get_platforms(self, obj):
        names = [platform.name for platform in obj.platforms.all()]
        return ', '.join(names)
    # get_platforms.allow_tags = True
    get_platforms.short_description = 'Platforms'


class LicenseKeyForm(forms.ModelForm):
    def clean_platforms(self):
        platforms = self.cleaned_data.get('platforms', None)
        if not platforms:
            return None
        # import pdb; pdb.set_trace()
        sw = self.instance.licensed_software.software
        platform_ids = list(sw.platforms.all())
        for p in platforms:
            if not sw.platforms.filter(pk=p.pk).exists():
                raise forms.ValidationError("%s is not available on %s platform" % (str(sw), p.name))

        return platforms

    class Meta:
        model = LicenseKey
        fields = '__all__'
        widgets = {
            'platforms': autocomplete.ModelSelect2Multiple(
                url='platform_autocomplete',
                forward=['software'],
            ),
        }


class LicenseKeyInline(nested_admin.NestedTabularInline):
    model = LicenseKey
    form = LicenseKeyForm
    extra = 1
    classes = ['collapse']


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


class LicensedSoftwareInline(nested_admin.NestedStackedInline):
    model = LicensedSoftware
    form = LicensedSoftwareForm
    min_num = 1
    extra = 1
    inlines = [LicenseKeyInline]


class LicenseImageInline(admin.TabularInline):
    model = LicenseImage
    extra = 1
    verbose_name = 'image'
    verbose_name_plural = 'images'


class PlatformAdmin(admin.ModelAdmin):
    model = Platform
    list_display = ['name']
    search_fields = ['name']


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


class LicenseAdmin(nested_admin.NestedModelAdmin):
    save_as = True
    form = LicenseForm
    # inlines = [LicensesSoftwareInline, LicenseImageInline]
    inlines = [LicensedSoftwareInline]
    list_display = [
        'description', 'get_display_softwares',
        'license_number', 'total', 'linked_used_total', 'remaining',
        'supplier', 'purchased_date', 'started_date', 'ended_date']
    list_select_related = ['supplier']
    exclude = ['description']
    readonly_fields = ['description', 'used_total']
    list_filter = (
        ('software_family', RelatedDropdownFilter),
        'license_type', 'ended_date', 'started_date',
    )
    autocomplete_fields = ['supplier', 'software_family']

    def get_fields(self, request, obj):
        if obj:
            return [
                'description', 'software_family', 'license_type', 'oem_device',
                'total', 'used_total', 'license_number', 'supplier',
                'purchased_date', 'started_date', 'ended_date', 'note']
        else:
            return [
                'software_family', 'license_type', 'oem_device',
                'total', 'license_number', 'supplier', 'purchased_date',
                'started_date', 'ended_date', 'note']

    def remaining(self, obj):
        return obj.remaining


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
                # 'data-close-on-select': 'false',
                # 'data-minimum-input-length': 3,
                'data-placeholder': 'Select one or more users',
            }
        )
    )
    platform = forms.ModelChoiceField(
        queryset=Platform.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="platform_autocomplete",
            attrs={
                # 'data-close-on-select': 'true',
                # 'data-minimum-input-length': 3,
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
                # 'data-close-on-select': 'false',
                # 'data-minimum-input-length': 3,
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


class LicenseAssignmentAdmin(admin.ModelAdmin):
    form = LicenseAssignmentForm
    list_display = ['id', 'user', 'software', 'platform', 'linked_license', 'get_serial_key']
    list_select_related = ['user', 'software', 'platform', 'license', 'license_key', 'software__software_family']
    list_filter = (
        ('user', RelatedDropdownFilter),
        ('software__software_family', RelatedDropdownFilter),
        ('software', RelatedDropdownFilter),
        ('license', RelatedDropdownFilter),
        ('platform', RelatedDropdownFilter),
    )
    ordering = ('user__username',)
    actions = [delete_license_assignments]

    def get_serial_key(self, obj):
        if obj.license_key:
            return obj.license_key.serial_key
        else:
            return None
    get_serial_key.short_description = "Serial Key"

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        urlpatterns = super(LicenseAssignmentAdmin, self).get_urls()
        my_urls = [
            url(r'^bulk_assign/', self.admin_site.admin_view(self.bulk_assign_view), name='%s_%s_bulk_assign' % info)
        ]
        return my_urls + urlpatterns

    def get_actions(self, request):
        actions = super(LicenseAssignmentAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def bulk_assign_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        opts = self.model._meta
        if request.method != 'POST':
            form = LicenseBulkAssignForm()
        else:
            form = LicenseBulkAssignForm(request.POST)
            if form.is_valid():
                maps = {}
                licenses = {}
                license_keys = {}
                softwares = form.cleaned_data['softwares']
                platform = form.cleaned_data['platform']
                rels = (LicensedSoftware.objects.select_related('license')
                                                .annotate(remaining=F('license__total') - F('license__used_total'))
                                                .filter(software__in=softwares, remaining__gt=0)
                                                .exclude(license__license_type=License.LICENSE_OEM)
                                                .order_by('remaining'))
                for obj in rels:
                    if obj.software_id in maps:
                        maps[obj.software_id].append(obj.license_id)
                    else:
                        maps[obj.software_id] = [obj.license_id]

                    if obj.license_id not in licenses:
                        obj.license.remaining = obj.remaining
                        licenses[obj.license_id] = obj.license

                    pk = "{}_{}".format(obj.software_id, obj.license_id)
                    license_keys[pk] = list(LicenseKey.objects.filter(licensed_software=obj.pk, platforms=platform).order_by('activation_type'))

                assignments = []
                for user in form.cleaned_data['users']:
                    for sw in softwares:
                        lic = None
                        lic_key = None
                        if sw.id in maps:
                            while maps[sw.id]:
                                lic_id = maps[sw.id][0]
                                if lic_id in licenses and licenses[lic_id].remaining > 0:
                                    lic = licenses[lic_id]
                                    lic.remaining -= 1
                                    break
                                else:
                                    del maps[sw.id][0]
                                    continue
                        if lic:
                            pk = "{}_{}".format(sw.id, lic.id)
                            if pk in license_keys and license_keys[pk]:
                                lic_key = license_keys[pk][0]
                                if lic_key.activation_type == LicenseKey.ACTIVATION_TYPE_SINGLE:
                                    del license_keys[pk][0]

                        assignments.append({
                            'user': user,
                            'software': sw,
                            'license': lic,
                            'license_key': lic_key,
                        })

                if '_confirmed' in request.POST:
                    with transaction.atomic():
                        for assignment in assignments:
                            license = assignment['license']
                            license_key = assignment['license_key']
                            obj = LicenseAssignment(
                                user_id=assignment['user'].pk,
                                software_id=assignment['software'].pk,
                                platform_id=platform.pk,
                                license_id=license.pk if license else None,
                                license_key_id=license_key.pk if license_key else None
                            )
                            obj.save()
                    post_url = reverse(
                        'admin:%s_%s_changelist' % (opts.app_label, opts.model_name),
                        current_app=self.admin_site.name,
                    )
                    self.message_user(
                        request,
                        "Successfully assigned softwares and licenses for users",
                        messages.SUCCESS
                    )
                    return HttpResponseRedirect(post_url)
                else:
                    context = {
                        **self.admin_site.each_context(request),
                        'users': form.cleaned_data['users'],
                        'softwares': form.cleaned_data['softwares'],
                        'platform': platform,
                        'assignments': assignments,
                        'opts': opts,
                        'media': self.media,
                        'has_change_permission': self.has_change_permission(request, None),
                    }
                    return TemplateResponse(
                        request,
                        "admin/%s/%s/bulk_assign_confirmation.html" % (opts.app_label, opts.model_name),
                        context
                    )

        adminForm = admin.helpers.AdminForm(
            form=form,
            fieldsets=[(None, {'fields': ('users', 'platform', 'softwares')})],
            prepopulated_fields={},
            model_admin=self)
        media = self.media + adminForm.media
        context = {
            **self.admin_site.each_context(request),
            'adminform': adminForm,
            'opts': opts,
            'media': media,
            'has_change_permission': self.has_change_permission(request, None),
        }
        return TemplateResponse(
            request,
            "admin/%s/%s/bulk_assign.html" % (opts.app_label, opts.model_name),
            context
        )


class LicenseSummaryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/license_summary_change_list.html'
    list_display = ('description',)
    list_filter = (
        ('software_family', RelatedDropdownFilter),
    )

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context,
        )
        try:
            qs = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response

        response.context_data['license_summary'] = License.get_license_summary(qs)
        return response

admin.site.register(Supplier, SupplierAdmin)
admin.site.register(SoftwareFamily, SoftwareFamilyAdmin)
admin.site.register(Software, SoftwareAdmin)
admin.site.register(Platform, PlatformAdmin)
admin.site.register(License, LicenseAdmin)
admin.site.register(LicenseAssignment, LicenseAssignmentAdmin)
admin.site.register(LicenseSummary, LicenseSummaryAdmin)
