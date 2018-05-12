from django import forms
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.conf.urls import url
from django.contrib import admin
from django.contrib import messages
from django.db.models import F, Q
from django.contrib.auth.models import User
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import PermissionDenied
from django.template.response import SimpleTemplateResponse, TemplateResponse

from dal import autocomplete
from dal import forward
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter

from .models import (
    Supplier, SoftwareFamily, Software,
    License, LicensedSoftware, LicenseAssignment, LicenseSummary)
from .actions import delete_license_assignments


class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact']
    search_fields = ['name']


class SoftwareFamilyAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


class SoftwareAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'version']
    search_fields = ['name', 'version', 'software_family__name']


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
                url='licensedsoftware-autocomplete',
                forward=['software_family'],
                attrs={'data-html': True}
            )
        }


class LicensedSoftwareInline(admin.TabularInline):
    model = LicensedSoftware
    form = LicensedSoftwareForm
    min_num = 1


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


class LicenseAdmin(admin.ModelAdmin):
    save_as = True
    form = LicenseForm
    inlines = [LicensedSoftwareInline]
    list_display = [
        'description', 'get_display_softwares',
        'license_number', 'total', 'linked_used_total',
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


class LicenseAssignmentForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(LicenseAssignmentForm, self).__init__(*args, **kwargs)
        license_widget = self.fields['license'].widget.widget
        if self.instance.pk:
            license_widget.forward = ['software', forward.Const(self.instance.license_id, 'license')]
        else:
            license_widget.forward = ['software']

    def clean_license(self):
        lic = self.cleaned_data.get('license', None)

        if not lic:
            return None

        soft = self.cleaned_data.get('software', None)
        if soft and not lic.softwares.filter(pk=soft.id):
            raise forms.ValidationError("Invalid license")
        is_create = True if not self.instance else False
        if is_create and (lic.total - lic.used_total == 0):
            raise forms.ValidationError("Not enough license")

        return lic

    class Meta:
        model = LicenseAssignment
        fields = '__all__'
        widgets = {
            'license': autocomplete.ModelSelect2(
                url='license-autocomplete',
                attrs={'data-html': True}
            )
        }

    class Media:
        js = (
            'license_manager/linked_data.js',
        )


class LicenseBulkAssignForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=FilteredSelectMultiple(
            "users",
            is_stacked=False,
        )
    )
    softwares = forms.ModelMultipleChoiceField(
        queryset=Software.objects.all(),
        widget=FilteredSelectMultiple(
            "softwares",
            is_stacked=False,
        )
    )

    class Media:
        css = {
            'all': ('admin/css/widgets.css',),
        }


class LicenseAssignmentAdmin(admin.ModelAdmin):
    form = LicenseAssignmentForm
    list_display = ['id', 'user', 'software', 'linked_license', 'get_serial_key']
    list_select_related = ['user', 'software', 'license']
    list_filter = (
        ('user', RelatedDropdownFilter),
        ('software__software_family', RelatedDropdownFilter),
        ('software', RelatedDropdownFilter),
        ('license', RelatedDropdownFilter),
    )
    actions = [delete_license_assignments]

    def get_serial_key(self, obj):
        if obj.license:
            licensed_software = LicensedSoftware.objects.get(license_id=obj.license, software=obj.software)
            return licensed_software.serial_key
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
                licenses = {}
                for sw in form.cleaned_data['softwares']:
                    licenses[sw.id] = list(License.objects.annotate(remaining=F('total') - F('used_total'))
                                                      .filter(softwares=sw, remaining__gt=0)
                                                      .values('id', 'description', 'remaining'))
                assignments = []
                for user in form.cleaned_data['users']:
                    for sw in form.cleaned_data['softwares']:
                        license = None
                        if licenses[sw.id]:
                            license = licenses[sw.id][0]
                            if license['remaining'] > 0:
                                license['remaining'] -= 1
                            if license['remaining'] == 0:
                                del licenses[sw.id][0]
                        assignments.append({
                            'user': user,
                            'software': sw,
                            'license': license})

                if '_confirmed' in request.POST:
                    for assignment in assignments:
                        license_id = None
                        if assignment['license']:
                            license_id = assignment['license']['id']
                        obj = LicenseAssignment(
                            user_id=assignment['user'].pk,
                            software_id=assignment['software'].pk,
                            license_id=license_id,
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
            fieldsets=[(None, {'fields': ('users', 'softwares',)})],
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
admin.site.register(License, LicenseAdmin)
admin.site.register(LicenseAssignment, LicenseAssignmentAdmin)
admin.site.register(LicenseSummary, LicenseSummaryAdmin)
