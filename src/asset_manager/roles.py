from rolepermissions.roles import AbstractUserRole


class Locker(AbstractUserRole):
    available_permissions = {
        'change_asset': True,
        'assign_asset': True,
    }


class Purchaser(AbstractUserRole):
    available_permissions = {
        'create_asset': True,
        'change_asset': True,
    }
