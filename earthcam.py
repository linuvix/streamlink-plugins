"""
$description A network of live webcams for tourism and entertainment.
$url earthcam.com
$type live, vod
$metadata author
$metadata category
$metadata title
$notes Only works for the cams hosted on EarthCam
"""

import re
from urllib.parse import urlparse

from streamlink.logger import getLogger
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.plugin.api import validate
from streamlink.stream.hls import HLSStream
from streamlink.utils.parse import parse_qsd
from streamlink.utils.url import update_scheme


log = getLogger(__name__)


@pluginmatcher(
    re.compile(r"https?://(?:www\.)?earthcam\.com/"),
)
class EarthCam(Plugin):
    # Headers required by EarthCam's video CDN (videos-*.earthcam.com).
    # Without Referer/Origin the HLS playlist returns 403 Forbidden.
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.earthcam.com/",
        "Origin": "https://www.earthcam.com",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def _get_streams(self):
        # Apply headers globally to this session so they are used for
        # - the HTML page request
        # - the HLS playlist request
        # - every subsequent .ts / .m4s segment request
        self.session.http.headers.update(self._HEADERS)

        data = self.session.http.get(
            self.url,
            schema=validate.Schema(
                re.compile(r"""var\s+json_base\s*=\s*(?P<json>{.*?});""", re.DOTALL),
                validate.none_or_all(
                    validate.get("json"),
                    validate.parse_json(),
                    {
                        "cam": {
                            str: {
                                "live_type": str,
                                "html5_streamingdomain": str,
                                "html5_streampath": str,
                                "group": str,
                                "location": str,
                                "title": str,
                                "liveon": str,
                                "defaulttab": str,
                            },
                        },
                    },
                    validate.get("cam"),
                ),
            ),
        )
        if not data:
            return

        cam_name = parse_qsd(urlparse(self.url).query).get("cam") or next(iter(data.keys()), None)
        cam_data = data.get(cam_name)
        if not cam_data:
            return

        # exclude everything other than live video streams
        if cam_data["live_type"] != "flashvideo" or cam_data["liveon"] != "true" or cam_data["defaulttab"] != "live":
            return

        log.debug(f"Found cam {cam_name}")
        hls_domain = cam_data["html5_streamingdomain"]
        hls_playpath = cam_data["html5_streampath"]

        self.author = cam_data["group"]
        self.category = cam_data["location"]
        self.title = cam_data["title"]

        if hls_playpath:
            hls_url = update_scheme("https://", f"{hls_domain}{hls_playpath}")
            log.debug(f"HLS URL: {hls_url}")
            yield from HLSStream.parse_variant_playlist(self.session, hls_url).items()


__plugin__ = EarthCam
