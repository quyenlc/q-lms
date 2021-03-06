"""pvn_lms URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, url
    2. Add a URL to urlpatterns:  url('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf.urls import include, url
from django.conf import settings
from django.conf.urls.static import static

from autocomplete import (
    PlatformAutocomplete,
    LicenseAutocomplete,
    SoftwareAutocomplete,
    LicenseKeyAutocomplete,
    UserAutocomplete,
)

urlpatterns = [
    url(r'^', include('filer.server.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^filer/', include('filer.urls')),
    url(r'^admin_tools/', include('admin_tools.urls')),
    url(r'^autocomplete/license_key/', LicenseKeyAutocomplete.as_view(), name='license_key_autocomplete'),
    url(r'^autocomplete/license/', LicenseAutocomplete.as_view(), name='license_autocomplete'),
    url(r'^autocomplete/software/', SoftwareAutocomplete.as_view(), name='software_autocomplete'),
    url(r'^autocomplete/platform/', PlatformAutocomplete.as_view(), name='platform_autocomplete'),
    url(r'^autocomplete/user/', UserAutocomplete.as_view(), name='user_autocomplete'),
    url(r'^account/', include('social_django.urls')),
    url(r'^nested_admin/', include('nested_admin.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

admin.site.site_header = 'PunchVN Infosys'
admin.site.site_title = 'PunchVN Infosys'
