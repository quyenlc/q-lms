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

from license_manager.views import LicenseAutocomplete, LicensedSoftwareAutocomplete

urlpatterns = [
    url(r'^', include('filer.server.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^admin_tools/', include('admin_tools.urls')),
    url(r'^license-autocomplete/', LicenseAutocomplete.as_view(), name='license-autocomplete'),
    url(r'^licensedsoftware-autocomplete/', LicensedSoftwareAutocomplete.as_view(), name='licensedsoftware-autocomplete'),
    url(r'^account/', include('social_django.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

admin.site.site_header = 'Punch Entertainment'
admin.site.site_title = 'Punch Entertainment'
