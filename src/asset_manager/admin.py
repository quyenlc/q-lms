from collections import OrderedDict

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth.models import User, Permission
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from django.template.response import TemplateResponse
from django.db.models import Q

from .models import (
    Type, Location, Manufacturer, Supplier,
    Office, Profile, Asset, Exchange
)


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name = 'profile'
    verbose_name_plural = 'profile'
    fk_name = 'user'


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_location')
    list_select_related = ('profile', )

    def get_location(self, instance):
        return instance.profile.location
    get_location.short_description = 'Location'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(UserAdmin, self).get_inline_instances(request, obj)


class TypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'kitting_required', 'user_searchable')
    list_filter = ('kitting_required',)


class LocationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'office', 'name', 'floor', 'room')
    list_editable = (
        'office', 'name', 'floor', 'room')
    actions = ['test_action']
    filter_horizontal = ('managers',)

    def test_action(self, request, queryset):
        return queryset.delete()
    test_action.short_description = "Test Action"


class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


class SupplierAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'contact')


# class LocationInline(admin.TabularInline):
#     model = Location
#     verbose_name_plural = 'Locations within the branch'
#     extra = 0


class OfficeAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')
    # inlines = [
    #     LocationInline
    # ]


def get_permitted_locations_for_user(user, location_type=None):
    query = Q(management_group__in=user.groups.all())
    if location_type:
        query &= Q(location_type=location_type)
    return Location.objects.filter(query)


class AssetAdmin(admin.ModelAdmin):
    list_display = (
        'get_code', 'name', 'asset_type', 'old_code',
        'supplier', 'manufacturer',
        'status', 'location'
    )

    fieldsets = (
        ('Basic infos', {
            'fields': ('old_code', 'name', 'asset_type', 'origin')
        }),
        ('Additional infos', {
            'fields': ('supplier', 'manufacturer')
        }),
        ('Important dates', {
            'fields': ('purchased_date', 'warranty_start_date', 'warranty_end_date')
        }),
        (None, {
            'fields': ('note',)
        })
    )

    def assign_to_location(self, request, queryset):
        # TODO: On the first POST request: redirect to location assign page
        # The page must have:
        # - A list of selected assets
        # - A form with
        #   - `Location` fields
        #   - `Receiver` fields
        #       - Will be changed when the location changes
        #       - Will be the list of managers of the selected location
        #   - a submit button

        # TODO: When user submit the form
        # - Check if the form is valid
        # - If the form is valid
        #   - Create an exchange record with:
        #       - The current user as the sender
        #       - The selected user as the receiver
        #       - The selected location as the destination
        #       - Exchange type is "location_assigning"
        #   - If current user is the manager of destination location
        #       - Mark the exchange is complete
        #       - Assign the asset to the location
        pass

    def assign_to_user(self, request, queryset):
        # TODO: On the first POST request: redirect to user assign page
        # The page must have:
        # - A list of selected assets
        # - A form with
        #   - `Receiver` fields
        #   - a submit button

        # TODO: When user submit the form
        # - Check if the form is valid
        # - If the form is valid
        #   - Create an exchange record with:
        #       - The current user as the sender
        #       - The selected user as the receiver
        #       - Exchange type is "user_assigning"
        # - If current user is the receiver
        #   - Mark the exchange is complete
        #   - Assign asset to the user
        pass

    def hand_over(self, request, queryset):
        # TODO: On the first POST request: redirect to hand over page
        # The page must have:
        # - A list of selected assets
        # - A form with
        #   - `Receiver` fields
        #       - Receivers are only the users with assign_asset permission
        #   - a submit button
        # TODO: When user submit the form
        # - Check if the form is valid
        # - If the form is valid
        #   - Create an exchange record with:
        #       - The current user as the sender
        #       - The selected user as the receiver
        #       - Exchange type is "releasing"
        pass

    def save_model(self, request, obj, form, change):
        if not change:
            obj.holder = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Select all unassigning assets with the user is the holder
        # also select all the assets have location managed by the user
        # exclude all exchanging assets
        return qs.filter(
            Q(assigned=False, holder=request.user) |
            Q(location__in=request.user.managing_locations.all())
        )

    def get_actions(self, request):
        """
        Override this funciton to remove the actions from the changelist view
        """
        actions = admin.ModelAdmin.get_actions(self, request)

        # if user has assign_asset permission
        # return two actions: Assign selected assets to a location and Assign selected assets to an user
        # else
        # return one action: Hand over
        if self.has_view_permission(request) and \
                not self._has_change_only_permission(request):
            # If the user doesn't have delete permission return an empty
            # OrderDict otherwise return only the default admin_site actions
            if not self.has_delete_permission(request):
                # TODO: remove delete action?
                return OrderedDict()
            else:
                return OrderedDict(
                    (name, (func, name, desc))
                    for func, name, desc in actions.values()
                    if name in dict(self.admin_site.actions).keys()
                )

        return actions

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Manufacturer, ManufacturerAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(Office, OfficeAdmin)
admin.site.register(Type, TypeAdmin)
admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Asset, AssetAdmin)
admin.site.register(Exchange)
