import os
import json
import requests
from osgeo import ogr
import re
from bs4 import BeautifulSoup
import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np


def envelope_to_polygon(minX, maxX, minY, maxY):
    return Polygon([(minX, minY), (maxX, minY), (maxX, maxY), (minX, maxY)])


def get_jgw(url):
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


def get_polygons_from_url(url_main, url_jgw, poly_path):
    if not os.path.exists(poly_path):
        main_html = requests.get(url_main)
        content = main_html.text
        soup = BeautifulSoup(content)
        polygons = []
        filenames = []
        for div in soup.findAll('div', attrs={'class': 'col-lg-4 col-md-6'})[1:]:
            filename = div.find('strong').get_text()
            filenames.append(filename)
            jgw = get_jgw(url_jgw.format(identifier=filename))
            minX, maxX, minY, maxY = jgw_to_envelope(jgw)
            polygons.append(envelope_to_polygon(minX, maxX, minY, maxY))
        grid = gpd.GeoDataFrame({'name': filenames, 'geometry': polygons})
        grid.to_file(poly_path)
    else:
        print(f"  grid {poly_path} already created")


def get_features_from_bbox(bbox):
    """Return all features for bounding box"""

    url = URL.format(bbox=",".join(str(f) for f in bbox))
    features = []
    while True:
        r_json = get_jgw(url)
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
    URL = "https://www.geoportalpraha.cz/cs/data/otevrena-data/468E977C-DE78-480D-B3D9-43A19BF1CD77"
    URL_jgw = "https://opendata.iprpraha.cz/CUR/ORT/ORT/S_JTSK/{identifier}.jgw"
    URL_jpg = "https://opendata.iprpraha.cz/CUR/ORT/ORT/S_JTSK/{identifier}.jpg"

    grid_shp = 'grid.shp'

    get_polygons_from_url(URL, URL_jgw, grid_shp)


