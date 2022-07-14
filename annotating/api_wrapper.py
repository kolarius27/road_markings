import os
import json
import requests
from osgeo import ogr
import re

URL = "https://www.geoportalpraha.cz/cs/data/otevrena-data/468E977C-DE78-480D-B3D9-43A19BF1CD77"
#URL_jgw = "https://opendata.iprpraha.cz/CUR/ORT/ORT_CIR/S_JTSK/{identifier}.jgw"
URL_jgw = "https://opendata.iprpraha.cz/CUR/ORT/ORT_CIR/S_JTSK/Bero_0-0-11.jgw"
URL_jpg = "https://opendata.iprpraha.cz/CUR/ORT/ORT_CIR/S_JTSK/{identifier}.jpg"


def envelope_to_polygon(minX, maxX, minY, maxY):
    # Create ring
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(minX, minY)
    ring.AddPoint(maxX, minY)
    ring.AddPoint(maxX, maxY)
    ring.AddPoint(minX, maxY)
    ring.AddPoint(minX, minY)

    # Create polygon
    poly_envelope = ogr.Geometry(ogr.wkbPolygon)
    poly_envelope.AddGeometry(ring)
    return poly_envelope


def get_json(url):
    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError(r.text)
    return r.text.splitlines()


def jgw_to_envelope(lines):
    centreX = float(lines[4][:-2])
    centreY = float(lines[5][:-2])
    pixelX = float(lines[0][:-2])
    pixelY = float(lines[3][:-2])
    minX = centreX - pixelX / 2
    maxX = centreX + 625.0 - pixelX / 2
    minY = centreY - 500.0 - pixelY / 2
    maxY = centreY - pixelY / 2
    return minX, maxX, minY, maxY


def get_features_from_bbox(bbox):
    """Return all features for bounding box"""

    url = URL.format(bbox=",".join(str(f) for f in bbox))
    features = []
    while True:
        r_json = get_json(url)
        features += r_json["features"]
        more_features = False
        for link in r_json['links']:
            if link['rel'] == 'next':
                url = link['href']
                more_features = True

        if not more_features:
            break

    print(f"  found {len(features)} features for bounding box {bbox}")
    return features


if __name__ == '__main__':
