from operator import itemgetter
from itertools import groupby
from urlparse import urljoin

import requests
from requests_oauthlib import OAuth1

from aggregator.plugins import Plugin


class APIReader(Plugin):
    """This plugins calls the zamboni API and aggregate the data before
    returning it.

    It needs to be subclassed, and shouldn't be used like that.
    Check GetAppInstalls for an example.
    """

    def __init__(self, parser=None, **kwargs):
        self.endpoint = kwargs['endpoint']
        self.oauth_key = kwargs.get('oauth_key', None)
        self.oauth_secret = kwargs.get('oauth_secret', None)
        if self.oauth_key and self.oauth_secret:
            self.oauth_header = OAuth1(self.oauth_key, self.oauth_secret)
        else:
            self.oauth_header = None

    def purge(self, start_date, end_date):
        params = {'key': self.type,
                  'recorded__gte': start_date.isoformat(),
                  'recorded__lte': end_date.isoformat()}
        res = requests.delete(self.endpoint, params=params,
                              auth=self.oauth_header)
        res.raise_for_status()

    def extract(self, start_date, end_date):

        data = []

        def _do_query(url, params=None):
            if not params:
                params = {}
            res = requests.get(url, params=params,
                               auth=self.oauth_header).json()
            data.extend(res['objects'])

            # we can have paginated elements, so we need to get them all
            if 'meta' in res and res['meta']['next']:
                _do_query(urljoin(url, res['meta']['next']))

        _do_query(self.endpoint, {
            'key': self.type,
            'recorded__gte': start_date.isoformat(),
            'recorded_lte': end_date.isoformat()})

        return self.aggregate(data)


class GetAppInstalls(APIReader):

    type = 'app.installs'

    def aggregate(self, items):
        # sort by date, addon and then by user.
        general_sort_key = lambda x: (x['date'],
                                      x['data']['addon_id'],
                                      x['anonymous'])
        items = sorted(items, key=general_sort_key)

        # group by addon
        dates = groupby(items, key=itemgetter('date'))

        for date, date_group in dates:
            addons = groupby(date_group, key=lambda x: x['data']['addon_id'])
            for addon_id, addon_group in addons:
                # for each addon, group by user.
                for anonymous, group in groupby(addon_group,
                                                key=lambda x: x['anonymous']):
                    count = sum([i['data']['installs'] for i in group])
                    yield {'_date': date,
                           '_type': type,
                           'add_on': addon_id,
                           'installs_count': count,
                           'anonymous': anonymous,
                           'type': self.type}
