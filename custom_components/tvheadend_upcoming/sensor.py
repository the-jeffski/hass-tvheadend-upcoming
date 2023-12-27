# TVHeadend Sensors
# Show upcoming Recordings

# -*- coding: utf-8 -*-

import sys
import time
import requests
import re


def fetch_data(a, url, recs):
    d = {
        'start': 0,
        'limit': recs,
        'sort': 'start_real',
        'dir': 'ASC',
        'groupBy': 'false',
        'groupDir':
        'ASC', 'duplicates': 0
    }

    r = requests.post('%s/api/dvr/entry/grid_upcoming?sort=start' %
                      url, data=d, auth=a)

    if not r.ok:
        return {'status': requests.status_codes._codes[r.status_code][0]}

    s = {
        'count': r.json()['total']
    }

    if r.json()['entries']:
        from datetime import timedelta
        s['data'] = []
        for e in r.json()['entries']:
            _s = {
                'status': e.get('status'),
                'channelname': e.get('channelname'),
                'disp_title': e.get('disp_title'),
                'disp_subtitle': e.get('disp_subtitle'),
                'disp_description': e.get('disp_description'),
                'channel_icon': e.get('channel_icon'),
                'start': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.get('start'))),
                'duration': e.get('duration'),
                'episode_disp': e.get('episode_disp'),
                'image': e.get('image'),
            }
            s['data'].append(_s)
    else:
        s['status'] = 'idle'

    return s


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage %s <user> <pass> <url>' % sys.argv[0])
        sys.exit(1)
    d = fetch_data(requests.auth.HTTPDigestAuth(
        sys.argv[1], sys.argv[2]), sys.argv[3], 3)
    print(d)
    sys.exit(0)
else:
    import logging
    import voluptuous as vol
    import homeassistant.helpers.config_validation as cv
    from datetime import timedelta
    from homeassistant.helpers.entity import Entity
    from homeassistant.components.sensor import PLATFORM_SCHEMA
    from homeassistant.const import (
        ATTR_ATTRIBUTION, CONF_NAME,
        CONF_URL, CONF_USERNAME, CONF_PASSWORD
    )

    _LOGGER = logging.getLogger(__name__)

    CONF_REC_COUNT = 'count'
    CONF_ATTRIBUTION = 'TVHeadend'
    ICON = 'mdi:record-rec'
    SCAN_INTERVAL = timedelta(seconds=300)
    DEFAULT_NAME = 'TVHeadend'

    PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_REC_COUNT, default=1): cv.positive_int,
    })

    def setup_platform(hass, config, add_entities, discovery_info=None):
        """Set up the Planned Recordings sensor."""
        add_entities([
            HtsSensor(
                config.get(CONF_URL),
                config.get(CONF_USERNAME),
                config.get(CONF_PASSWORD),
                config.get(CONF_NAME),
                config.get(CONF_REC_COUNT),
            ),
        ])

    class HtsSensor(Entity):
        """Representation of a hts sensor."""

        def __init__(self, url, usr, passwd, name, cnt):
            """Initialize the sensor."""
            self._url = url
            self._fetch = fetch_data
            self._name = 'TVHeadend Upcoming'
            self._cnt = cnt
            self._auth = requests.auth.HTTPDigestAuth(usr, passwd)
            self._data = self._fetch(self._auth, self._url, self._cnt)

        @property
        def should_poll(self):
            """No polling needed for a demo sensor."""
            return True

        @property
        def name(self):
            """Return the name of the sensor."""
            return self._name

        @property
        def state(self):
            """Return the state of the sensor."""
            return str(self._data['count'])

        @property
        def icon(self):
            """Return icon."""
            return ICON

        @property
        def extra_state_attributes(self):
            """Return the state attributes."""
            attributes = {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                'url': self._url
            }

            _data = self._data
            _LOGGER.info(_data)
            card_json = [
                {
                    'title_default': '$title',
                    'line1_default': '$episode',
                    'line2_default': '$studio',
                    'line3_default': '$runtime $date $time',
                    'line4_default': '$number'
                }
            ]

            if 'data' in _data.keys():
                for d in _data.pop('data'):
                    card_item = {}
                    card_item['airdate'] = d['start']
                    card_item['title'] = d['disp_title']
                    if match := re.search('Season (\d{1,3}(?!\d)|\d\d\d??)', d['episode_disp'], re.IGNORECASE):
                        season_num = "S" + (match.group(1).zfill(2))
                    else:
                        season_num = ''
                    if match := re.search('Episode (\d{1,3}(?!\d)|\d\d\d??)', d['episode_disp'], re.IGNORECASE):
                        episode_num = "E" + (match.group(1).zfill(2))
                    else:
                        episode_num = ''    
                    card_item['number'] = season_num + episode_num
                    card_item['episode'] = d['disp_subtitle']
                    card_item['description'] = d['disp_description']
                    card_item['runtime'] = d['duration'] // 60
                    card_item['studio'] = d['channelname']
                    card_item['poster'] = d['channel_icon']

                    card_json.append(card_item)

            attributes.update(_data)

            attributes['data'] = card_json

            return attributes

        def update(self):
            """Get the latest data from the API."""
            try:
                self._data = self._fetch(self._auth, self._url, self._cnt)
                _LOGGER.debug("Data = %s", self._data)
            except ValueError as err:
                _LOGGER.error("Check tvh %s", err.args)
                raise
