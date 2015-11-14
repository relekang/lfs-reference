import httplib
import json
import string
import urllib
from new import instancemethod
from random import choice

from django.conf import settings
from django.contrib.auth.models import User
from fs_ref.core.util import parse_name


def generate_password(length=8, chars=string.letters + string.digits):
    pw = ''.join([choice(chars) for i in range(length)])
    return pw


class LfsAuthenticationBackend:

    URL = settings.LFS_URL
    PATH = '/wsScripts/cgiip.exe/WService=wslfshtml/remote-auth.r'
    HEADERS = {
        "Content-type": "application/x-www-form-urlencoded",
        "Accept": "text/plain"
    }

    def load_json(self, response):
        response = response.replace('<!-- Generated by Webspeed: http://www.webspeed.com/ -->', '')
        response = response.replace('\xe4', 'a').replace('\xf6', 'o').strip()
        return json.loads(response)

    def authenticate(self, username, password):
        if settings.DEBUG and User.objects.filter(username=username).count() == 1:
            return User.objects.get(username=username)

        user = None
        params = urllib.urlencode({
            'username': username,
            'password': password,
            'token': settings.LFS_TOKEN
        })

        connection = httplib.HTTPConnection(self.URL)
        connection.request("POST", self.PATH, params, self.HEADERS)
        response = connection.getresponse().read()
        connection.close()
        user_info = self.load_json(response)['user']

        if not bool(user_info['auth']):
            return None

        try:
            user = User.objects.get(username=username)
        except (TypeError, User.DoesNotExist):
            if user_info['user_group'] == 'INT' or settings.DEBUG:
                user = User(username=username)
                user.save()
                profile = user.profile
                profile.language = user_info['language'].lower()
                profile.save()
                user.is_active = True

                name = parse_name(user_info['name'])
                user.first_name = name['first']
                user.last_name = name['last']
                user.save()

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


USER_ATTR_NAME = getattr(settings, 'LOCAL_USER_ATTR_NAME', '_current_user')

try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local
_thread_locals = local()



def _do_set_current_user(user_fun):
    setattr(_thread_locals, USER_ATTR_NAME,
            instancemethod(user_fun, _thread_locals, type(_thread_locals)))


def _set_current_user(user=None):
    _do_set_current_user(lambda self: user)


class LocalUserMiddleware(object):
    def process_request(self, request):
        # request.user closure; asserts laziness; memoization is implemented in
        # request.user (non-data descriptor)
        _do_set_current_user(lambda self: getattr(request, 'user', None))
        if get_current_user().is_authenticated():
            request.session['django_language'] = get_current_user().profile.language


def get_current_user():
    current_user = getattr(_thread_locals, USER_ATTR_NAME, None)
    return current_user() if current_user else current_user
