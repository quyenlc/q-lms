from django.db import models
from django.db import IntegrityError
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import HStoreField
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    location = models.ForeignKey('Office', on_delete=models.PROTECT)

    def __str__(self):
        return self.user.username


class Supplier(models.Model):
    name = models.CharField(max_length=100, unique=True)
    contact = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Manufacturer(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Type(models.Model):
    name = models.CharField(verbose_name="Type name",
                            max_length=100, unique=True)
    kitting_required = models.BooleanField()
    user_searchable = models.BooleanField(default=True)

    class Meta:
        verbose_name = "asset type"

    def __str__(self):
        return self.name


class Location(models.Model):
    office = models.ForeignKey(
        'Office', on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    floor = models.PositiveIntegerField(
        blank=True, null=True, default=None,
    )
    room = models.PositiveIntegerField(
        blank=True, null=True, default=None,
    )
    managers = models.ManyToManyField(
        'auth.User', related_name='managing_locations')

    def __str__(self):
        return '%s - %s' % (self.office.name, self.name)

    class Meta:
        unique_together = (('office', 'name'),)


class Office(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Asset(models.Model):
    EXCELLENCE = 1
    GOOD = 3
    FAIR = 3
    BROKEN = 3
    LOST = 4
    REPARING = 5
    DISPOSED = 6
    AUCTIONED = 7
    NOT_FOUND = 8

    STATUSES_NEW = (
        (EXCELLENCE, 'Excellence'),
        (GOOD, 'Good'),
        (FAIR, 'Fair'),
    )

    STATUSES_ALL = STATUSES_NEW + (
        (BROKEN, 'Broken'),
        (NOT_FOUND, 'Not found'),
        (LOST, 'Lost'),
        (REPARING, 'Reparing'),
        (DISPOSED, 'Disposed'),
        (AUCTIONED, 'Auctioned'),
    )

    BRAND_NEW = 1
    COMPENSATED = 2
    REUSED = 3
    ORIGINS = (
        (BRAND_NEW, 'Brand new'),
        (REUSED, 'Secondhand'),
        (COMPENSATED, 'Compensated'),
    )

    old_code = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=100)
    asset_type = models.ForeignKey('Type', on_delete=models.PROTECT)
    supplier = models.ForeignKey(
        'Supplier', blank=True, null=True,
        on_delete=models.PROTECT,
    )
    manufacturer = models.ForeignKey(
        'Manufacturer', blank=True, null=True,
        on_delete=models.PROTECT,
    )
    # specifications = HStoreField(blank=True, null=True)
    purchased_date = models.DateField(blank=True, null=True)
    warranty_start_date = models.DateField(blank=True, null=True)
    warranty_end_date = models.DateField(blank=True, null=True)

    # state
    origin = models.IntegerField(choices=ORIGINS, default=BRAND_NEW)
    status = models.IntegerField(choices=STATUSES_ALL, default=EXCELLENCE)
    assigned = models.BooleanField(default=False)
    holder = models.ForeignKey(
        'auth.User', blank=True, null=True,
        on_delete=models.PROTECT,
    )
    location = models.ForeignKey(
        'Location', blank=False, null=True,
        on_delete=models.PROTECT,
    )
    # logging
    # exchange_count = models.PositiveIntegerField(blank=True, default=0)
    # last_exchange = models.OneToOneField(
    #     'Exchange', blank=True, null=True,
    #     on_delete=models.PROTECT, related_name='+',
    # )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    available_at = models.DateField(editable=False, null=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def clean(self):
        validation_errors = {}
        if self.warranty_end_date <= self.warranty_start_date:
            validation_errors['warranty_end_date'] = ValidationError(
                _('Warranty end date must be greater than warranty start date'),
            )
        if self.warranty_start_date < self.purchased_date:
            validation_errors['warranty_start_date'] = ValidationError(
                _('Warranty start date must be greater than or equal purchased date'),
            )
        if validation_errors:
            raise ValidationError(validation_errors)

    def is_recently_exchanged(self):
        fresh_period = timezone.timedelta(minutes=5)
        return (self.last_exchange and
                timezone.now() - self.last_exchange.ended_at < fresh_period)

    def get_holder(self):
        if self.holder:
            return self.holder.username
    get_holder.short_description = 'Holder'
    get_holder.admin_order_field = ('holder__username',)

    def get_code(self):
        return "%s%05d" % (settings.AMS_ASSET_ID_PREFIX, self.id)
    get_code.short_description = 'Code'

    class Meta:
        permissions = (
            ('assign_asset', 'Can assign asset to user or location'),
        )


class Exchange(models.Model):
    REASON_EXCHANGE = 1
    REASON_RETURN = 2
    REASON_BROKEN = 3
    REASON_LOST = 4
    REASON_RESIGNING = 5
    REASON_ONBOARDING = 6
    REASON_REQUESTED = 7
    REASON_OTHER = 8
    REASONS = (
        (REASON_RETURN, 'No longer needed'),
        (REASON_EXCHANGE, 'Exchange'),
        (REASON_BROKEN, 'Broken'),
        (REASON_LOST, 'Lost'),
        (REASON_RESIGNING, 'Leave company'),
        (REASON_OTHER, 'Other'),
    )

    REASONS_ADMIN = REASONS + (
        (REASON_ONBOARDING, 'New employee'),
        (REASON_REQUESTED, 'Requested'),
    )

    STATUS_PENDING = 1
    STATUS_CANCELLED = 2
    STATUS_REJECTED = 3
    STATUS_TAKEN = 4

    STATUSES = (
        (STATUS_PENDING, 'Waiting for receiver'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_TAKEN, 'Taken'),
    )

    asset = models.ForeignKey('Asset', on_delete=models.PROTECT)
    sender = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, related_name='+',
    )
    receiver = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, related_name='+',
    )

    source = models.ForeignKey(
        'Location', on_delete=models.PROTECT,
        related_name='+', blank=True, null=True,
    )

    destination = models.ForeignKey(
        'Location', on_delete=models.PROTECT,
        related_name='+', blank=True, null=True,
    )
    reason = models.PositiveIntegerField(
        choices=REASONS_ADMIN, default=REASON_EXCHANGE,
    )

    status = models.PositiveIntegerField(
        choices=STATUSES, default=STATUS_PENDING)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    ended_by = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT,
        related_name='+', blank=True, null=True,
    )
    kitting_required = models.BooleanField()
    kitting_by = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT,
        related_name='+', blank=True, null=True,
    )
    kitting_started_at = models.DateTimeField(blank=True, null=True)
    kitting_completed_at = models.DateTimeField(blank=True, null=True)
    kitting_dued_at = models.DateTimeField(blank=True, null=True)
    comment = models.TextField(blank=True)

    class Meta:
        permissions = (
            ('kitting_asset', 'Can update kitting due date, comment, assignee, status.'),
            ('change_kitting_due_date', 'Can update kitting due date.'),
        )

    def is_fresh(self):
        fresh_period = timezone.timedelta(minutes=5)
        return (self.started_at and
                timezone.now() - self.started_at < fresh_period)

    def get_asset_name(self):
        return self.asset.name
    get_asset_name.short_description = 'Asset Name'
    get_asset_name.admin_order_field = 'asset__name'

    def get_asset_id(self):
        return self.asset.get_id()
    get_asset_id.short_description = 'Asset ID'
    get_asset_id.admin_order_field = 'asset__id'

    def get_sender(self):
        return self.sender.username
    get_sender.short_description = 'From'
    get_sender.admin_order_field = ('sender.name',)

    def get_receiver(self):
        return self.receiver.username
    get_receiver.short_description = 'To'
    get_receiver.admin_order_field = ('receiver.name',)

    # def next_status(self, request, next_status):
    #     if self.pk and next_status > self.status:
    #         self.status = next_status
    #         self.ended_at = timezone.now()
    #         self.ended_by = request.user
    #         if next_status == self.TAKEN:
    #             if self.to_group:
    #                 self.asset.group_holder = self.to_group
    #                 self.asset.holder = None
    #             if self.to_user:
    #                 self.asset.holder = self.to_user
    #                 self.asset.group_holder = None
    #             self.asset.last_exchange = self
    #             self.asset.save()
    #         self.save()
