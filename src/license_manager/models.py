from django.db import models
from django.db import transaction
from django.db import IntegrityError
from django.db.models import F
from django.contrib.auth.models import User
from django.utils import timezone

from filer.fields.image import FilerImageField
from filer.models.imagemodels import Image


class Supplier(models.Model):
    name = models.CharField(max_length=100, unique=True)
    contact = models.TextField(blank=True)

    def __str__(self):
        return self.name


class SoftwareFamily(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Software Families'


class SoftwareManager(models.Manager):
    def get_queryset(self):
        return super(SoftwareManager, self).get_queryset().select_related('software_family')


class Software(models.Model):
    users = models.ManyToManyField(User, through='LicenseAssignment')
    software_family = models.ForeignKey('SoftwareFamily', on_delete=models.PROTECT)
    name = models.CharField(
        max_length=50, blank=True,
        help_text='Could leave empty if software name and family name are the same.')
    version = models.CharField(
        max_length=50, blank=True,
        help_text='''Schematic version.<br>Could use glob symbol * for version matching (eg: 12.*).<br>
            Empty value also matches all versions.''')
    platforms = models.ManyToManyField('Platform')

    # Override default manager
    objects = SoftwareManager()

    def get_full_name(self):
        return "{} {}".format(self.software_family.name, self.name)

    def __str__(self):
        return self.get_full_name()

    class Meta:
        unique_together = ('name', 'version')


class Platform(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class LicenseManager(models.Manager):
    def get_queryset(self):
        queryset = super(LicenseManager, self).get_queryset()
        return queryset.annotate(remaining=F('total') - F('used_total'))


class License(models.Model):
    LICENSE_PERPETUAL = 1
    LICENSE_SUBSCRIPTION = 2
    LICENSE_OEM = 3

    LICENSE_TYPES = (
        (LICENSE_PERPETUAL, 'Perpetual'),
        (LICENSE_SUBSCRIPTION, 'Subscription-based'),
        (LICENSE_OEM, 'OEM'),
    )

    softwares = models.ManyToManyField(Software, through='LicensedSoftware')
    users = models.ManyToManyField(User, through='LicenseAssignment')
    images = models.ManyToManyField(Image, through='LicenseImage')

    description = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    software_family = models.ForeignKey('SoftwareFamily', on_delete=models.PROTECT)
    total = models.PositiveIntegerField()
    used_total = models.PositiveIntegerField(blank=True, null=True, default=0)
    license_type = models.PositiveIntegerField(
        choices=LICENSE_TYPES, default=LICENSE_PERPETUAL,
        help_text='''Perpetual only requires payment once.<br>
            Subscription-based license requires payment monthly or annualy.<br>
            OEM license comes with purchased devices.''')
    oem_device = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='''Name or model of OEM device (eg: Dell Latitude 7240).<br>
            This field is required for OEM license and will be ignored otherwise.''')
    supplier = models.ForeignKey('Supplier', blank=True, null=True, on_delete=models.PROTECT)
    license_number = models.CharField(max_length=100, blank=True)
    management_website = models.URLField(blank=True)
    # max_device = models.PositiveIntegerField(default=1)
    purchased_date = models.DateField(blank=True, null=True)
    started_date = models.DateField(blank=True, null=True)
    ended_date = models.DateField(blank=True, null=True)
    note = models.TextField(blank=True)

    # Override default manager
    objects = LicenseManager()

    def assign(self, amount=1):
        with transaction.atomic():
            lic = License.objects.select_for_update().get(pk=self.id)
            if lic.total - lic.used_total >= amount:
                lic.used_total += amount
                lic.save()
            else:
                raise IntegrityError("Not enough license.")

    def unassign(self, amount=1):
        with transaction.atomic():
            lic = License.objects.select_for_update().get(pk=self.id)
            if lic.used_total >= amount:
                lic.used_total -= amount
                lic.save()
            else:
                raise IntegrityError("Could not unassign license, unassign amount is too large.")

    def get_license_summary(queryset=None):
        if not queryset:
            queryset = License.objects.all()
        summary = {}
        for lic in queryset:
            softwares = lic.softwares.all()
            skey = lic.software_family.name
            for sw in softwares:
                skey += '_' + str(sw.pk)
            if skey not in summary:
                summary[skey] = {
                    'software_family': lic.software_family.name,
                    'softwares': softwares,
                    'total': lic.total,
                    'used_total': lic.used_total,
                    'remaining': lic.total - lic.used_total
                }
            else:
                summary[skey]['total'] += lic.total
                summary[skey]['used_total'] += lic.used_total
                summary[skey]['remaining'] = summary[skey]['total'] - summary[skey]['used_total']
        return sorted(summary.items())

    def get_remaining_days(self):
        days = (self.ended_date - timezone.now().date()).days
        if days < 0:
            days = 0
        return days

    def save(self, *args, **kwargs):
        self.description = "{} {} Licenses".format(
            self.software_family.name, self.get_license_type_display())
        if self.license_type == self.LICENSE_OEM:
            self.description += " for {}".format(self.oem_device)
        qs = License.objects.filter(
            license_type=self.license_type,
            software_family=self.software_family,)
        if self.pk:
            qs = qs.filter(pk__lt=self.pk)
        count = qs.count()
        self.description += " #{0:03d}".format(count+1)
        super(License, self).save(*args, **kwargs)

    def __str__(self):
        return self.description


class LicenseImage(models.Model):
    image = FilerImageField()
    license = models.ForeignKey('License')

    def __str__(self):
        return "Image ID: %d" % (self.image_id)


class LicensedSoftware(models.Model):
    license = models.ForeignKey('License', on_delete=models.CASCADE)
    software = models.ForeignKey('Software', on_delete=models.CASCADE)

    def __str__(self):
        return str(self.software)

    class Meta:
        unique_together = ("license", "software")


class LicenseKeyManager(models.Manager):
    def get_available_keys(self, software_id, license_id, platform_id, include_id=None):
        if not(software_id and license_id and platform_id):
            return self.none()
        filter_assignment = {
            'license_id': license_id,
            'software_id': software_id,
            'license_key__activation_type': LicenseKey.ACTIVATION_TYPE_SINGLE,
        }
        ids = list(LicenseAssignment.objects.filter(**filter_assignment).values_list('license_key_id', flat=True))
        if include_id and include_id in ids:
            ids.remove(include_id)
        return (self.select_related('licensed_software')
                    .exclude(pk__in=ids)
                    .filter(
                        platforms=platform_id,
                        licensed_software__license_id=license_id,
                        licensed_software__software_id=software_id)
                    .order_by('activation_type'))


class LicenseKey(models.Model):
    ACTIVATION_TYPE_SINGLE = 1
    ACTIVATION_TYPE_VOLUME = 2
    ACTIVATION_TYPE_SERVER = 3

    ACTIVATION_TYPES = (
        (ACTIVATION_TYPE_SINGLE, 'Single'),
        (ACTIVATION_TYPE_VOLUME, 'Volume'),
        (ACTIVATION_TYPE_SERVER, 'Server'),
    )
    licensed_software = models.ForeignKey(
        'LicensedSoftware', on_delete=models.CASCADE)
    serial_key = models.CharField(max_length=200)
    activation_type = models.PositiveIntegerField(
        choices=ACTIVATION_TYPES, default=ACTIVATION_TYPE_VOLUME)
    platforms = models.ManyToManyField('Platform')

    # Override default manager
    objects = LicenseKeyManager()

    def is_available(self):
        if self.activation_type == self.ACTIVATION_TYPE_SINGLE and self.licenseassignment_set.all():
            return False
        else:
            return True

    def __str__(self):
        return self.serial_key

    class Meta:
        unique_together = ('licensed_software', 'serial_key')


class LicenseAssignment(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    software = models.ForeignKey('Software', on_delete=models.PROTECT)
    platform = models.ForeignKey('Platform', on_delete=models.PROTECT)
    license = models.ForeignKey(
        'License', blank=True, null=True, on_delete=models.PROTECT)
    license_key = models.ForeignKey(
        'LicenseKey', blank=True, null=True, on_delete=models.PROTECT)
    note = models.TextField(blank=True)

    def __init__(self, *args, **kwargs):
        super(LicenseAssignment, self).__init__(*args, **kwargs)
        self.original_license_id = self.license_id

    def get_unlicensed_softwares():
        summary = {}
        qs = LicenseAssignment.objects.filter(license__isnull=True)
        for la in qs:
            if la.software_id not in summary:
                summary[la.software_id] = {
                    'software': la.software.get_full_name(),
                    'users': [la.user.username],
                    'count': 1,
                }
            else:
                summary[la.software_id]['users'].append(la.user.username),
                summary[la.software_id]['count'] += 1
        return sorted(summary.items())

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = True if not self.pk else False
            super(LicenseAssignment, self).save(*args, **kwargs)
            if is_new:
                if self.license_id:
                    self.license.assign()
            else:
                if self.original_license_id != self.license_id:
                    if self.original_license_id:
                        License.objects.get(pk=self.original_license_id).unassign()
                    if self.license_id:
                        self.license.assign()

    def delete(self):
        with transaction.atomic():
            super(LicenseAssignment, self).delete()
            if self.license_id:
                self.license.unassign()

    def __str__(self):
        return "{} for {}".format(self.software.get_full_name(), self.user.get_username())


class LicenseSummary(License):
    class Meta:
        proxy = True
        verbose_name = 'Licenses Summary'
        verbose_name_plural = 'Licenses Summary'
