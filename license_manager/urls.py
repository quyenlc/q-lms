from django.urls import path
from . import views

urlpatterns = [
    path('license-autocomplete/', views.LicenseAutocomplete.as_view(), name='license-autocomplete'),
]