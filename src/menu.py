"""
This file was generated with the custommenu management command, it contains
the classes for the admin menu, you can customize this class as you want.

To activate your custom menu add the following to your settings.py::
    ADMIN_TOOLS_MENU = 'pvn_lms.menu.CustomMenu'
"""

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from admin_tools.menu import items, Menu


class CustomMenu(Menu):
    """
    Custom Menu for pvn_lms admin site.
    """
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)
        self.children += [
            items.MenuItem(_('Dashboard'), reverse('admin:index')),
            items.Bookmarks(),
            items.AppList(
                _('Administration'),
                models=('django.contrib.*', 'filer.*', )
            ),
            items.ModelList(
                _('Asset Manager'),
                (
                    'asset_manager.models.Asset',
                    'asset_manager.models.Exchange',
                    'asset_manager.models.Office',
                    'asset_manager.models.Location',
                    'asset_manager.models.Manufacturer',
                    'asset_manager.models.Supplier',
                    'asset_manager.models.Type',
                ),
            ),
            items.ModelList(
                _('License Manager'),
                (
                    'license_manager.models.License',
                    'license_manager.models.LicenseAssignment',
                    'license_manager.models.LicenseSummary',
                    'license_manager.models.Platform',
                    'license_manager.models.SoftwareFamily',
                    'license_manager.models.Software',
                    'license_manager.models.Supplier',
                ),
            ),
        ]

    def init_with_context(self, context):
        """
        Use this method if you need to access the request context.
        """
        return super(CustomMenu, self).init_with_context(context)
