from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from googleapiclient.discovery import build
from google.oauth2 import service_account

SERVICE_ACCOUNT_FILE = 'service-account-key.json'
OAUTH_SCOPES = ['https://www.googleapis.com/auth/admin.directory.user.readonly']
DELEGATED_SUBJECT = 'tung.vu@punch.vn'
DOMAIN = 'punch.vn'
ORGANIZATION_UNIT = 'punch-staff'


class Command(BaseCommand):
    help = '''Sync users from GSuite domain'''

    def add_arguments(self, parser):
        parser.add_argument(
            '-k', '--key', type=str,
            default=SERVICE_ACCOUNT_FILE,
            help='Service account private key file')
        parser.add_argument(
            '-d', '--domain', type=str,
            default=DOMAIN,
            help='Domain of Gsuite')
        parser.add_argument(
            '-s', '--scopes',
            type=str, nargs='+',
            default=OAUTH_SCOPES,
            help='Scopes of oauth request.')
        parser.add_argument(
            '-u', '--subject', type=str, required=True,
            help='The email address of the user to for which to request delegated access.')
        parser.add_argument(
            '-o', '--ou', type=str,
            default=ORGANIZATION_UNIT,
            help='Organization unit path of the users.')

    def create_directory_service(self, **options):
        """Build and returns an Admin SDK Directory service object authorized with the service accounts
        that act on behalf of the given user.

        Returns:
          Admin SDK directory service object.
        """
        credentials = service_account.Credentials.from_service_account_file(
            options['key'],
            scopes=options['scopes'],
            subject=options['subject'])

        return build('admin', 'directory_v1', credentials=credentials)

    def get_gsuit_users(self, **options):
        service = self.create_directory_service(**options)
        next_page = None
        users = []
        while True:
            request = service.users().list(
                domain=options['domain'],
                query="orgUnitPath=/%s" % options['ou'],
                # showDeleted=True,
                pageToken=next_page,
            )
            response = request.execute()
            next_page = response.get('nextPageToken', None)
            users += response.get('users', [])
            if not next_page:
                break
        return users

    def create_django_users(self, gsuite_users, **options):
        for user in gsuite_users:
            email = user['primaryEmail']
            dj_user = User.objects.filter(email=email).first()

            if dj_user:
                if options['verbosity'] > 1:
                    self.stdout.write(self.style.NOTICE('User with email %s already exists' % email))
                if user['suspended'] and dj_user.is_active:
                    dj_user.is_active = False
                    dj_user.save()
                    self.stdout.write(self.style.WARNING('User %s was deactivated' % email))
                continue

            if user['suspended']:
                continue

            name = user['name']
            first_name = name['givenName']
            last_name = name['familyName']
            creation_time = user['creationTime']
            username = email[:email.index('@')]
            User.objects.create(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                date_joined=creation_time,
            )
            self.stdout.write(self.style.SUCCESS('Created user: %s' % name['fullName']))

    def handle(self, *args, **options):
        self.create_django_users(self.get_gsuit_users(**options), **options)
