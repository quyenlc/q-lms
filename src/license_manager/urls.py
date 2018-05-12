from django.conf.urls import url
from . import views

urlpatterns = [
    url('^license-autocomplete/', views.LicenseAutocomplete.as_view(), name='license-autocomplete'),
]
