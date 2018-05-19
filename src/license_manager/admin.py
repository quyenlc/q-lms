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
from django.utils.html import format_html

from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter

import nested_admin

from .models import (
    Supplier, SoftwareFamily, Software, LicenseImage, LicenseKey,
    Platform, License, LicensedSoftware, LicenseAssignment, LicenseSummary)
from .forms import (
    SoftwareForm, LicenseForm, LicenseKeyForm,
    LicensedSoftwareForm, LicenseAssignmentForm, LicenseBulkAssignForm
)
from .actions import delete_license_assignments


class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact']
    search_fields = ['name']


class SoftwareFamilyAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


class SoftwareAdmin(admin.ModelAdmin):
    form = SoftwareForm
    list_display = ['__str__', 'version', 'get_platforms']
    search_fields = ['name', 'version', 'software_family__name']
    select_related = ('software_family',)

    def get_platforms(self, obj):
        names = [platform.name for platform in obj.platforms.all()]
        return ', '.join(names)
    get_platforms.allow_tags = True
    get_platforms.short_description = 'Platforms'


class LicenseKeyInline(nested_admin.NestedTabularInline):
    model = LicenseKey
    form = LicenseKeyForm
    extra = 1
    classes = ['collapse']


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

    def get_display_softwares(self, obj):
        names = []
        for software in obj.softwares.all():
            names.append(str(software))
        return format_html("<br>".join(names))
    get_display_softwares.short_description = "Products"
    get_display_softwares.allow_tags = True

    def remaining(self, obj):
        return obj.remaining
    remaining.admin_order_field = 'remaining'

    def linked_used_total(self, obj):
        if obj.used_total == 0:
            return 0
        color = 'limegreen'
        if obj.used_total == obj.total:
            color = 'red'
        opts = obj._meta
        url = reverse(
            'admin:%s_%s_changelist' %
            (opts.app_label, 'licenseassignment')
        )
        url += '?license__id__exact=%d' % obj.pk
        return format_html(
            '<a href="{}" style="color: {}" title="Click here to see the users using this license."><strong>{}</strong></a>',
            url, color, obj.used_total
        )
    linked_used_total.short_description = 'used total'
    linked_used_total.admin_order_field = 'used_total'


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

    def linked_license(self, obj):
        if not obj.license_id:
            return
        url = reverse(
            'admin:%s_%s_changelist' %
            (obj._meta.app_label, 'license'),
            # args=[self.license_id]
        )
        url += '?pk__exact=%d' % obj.license_id
        return format_html('<a href="{}">{}</a>', url, obj.license)
    linked_license.short_description = 'license'
    linked_license.admin_order_field = 'license'

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
