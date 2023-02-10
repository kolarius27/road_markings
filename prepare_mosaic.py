#import arcpy
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
import requests
import os
from osgeo import ogr
from osgeo import gdal
from rasterio import merge
from rasterio import mask
from rasterio import open as rio_open
import fiona
from pathlib import Path
from shapely import Polygon, Point


def my_envelope(minX, maxX, minY, maxY):

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


def raster2mosaic(path, shp):
    path_new = Path(path)
    output_path = os.path.join(path_new, 'mosaic.tif')
    raster_files = list(path_new.iterdir())
    raster_to_mosaic = []

    for p in raster_files:
        raster, output_meta = clip_raster(p, shp)
        raster_to_mosaic.append(raster)
    print(raster_to_mosaic)

    mosaic, output = merge.merge(raster_to_mosaic)

    # output_meta = raster.meta.copy()
    output_meta.update(
        {"driver": "GTiff",
         "height": mosaic.shape[1],
         "width": mosaic.shape[2],
         "transform": output,
         }
    )

    with rio_open(output_path, 'w', **output_meta) as m:
        m.write(mosaic)

    for f in raster_files:
        os.remove(f)


def clip_raster(raster, shapefile):
    with fiona.open(shapefile, 'r') as shp:
        shapes = [feature['geometry'] for feature in shp]

    with rio_open(raster) as src:
        out_image, out_transform = mask.mask(src, shapes, crop=True)
        out_meta = src.meta.copy()

    out_meta.update(
        {"driver": "GTiff",
         "height": out_image.shape[1],
         "width": out_image.shape[2],
         "transform": out_transform,
         }
    )

    split_path = os.path.split(raster)

    output_raster = os.path.join(split_path[0], split_path[1][:-4] + '_clip.tif')
    print(output_raster)

    with rio_open(output_raster, 'w', **out_meta) as dat:
        dat.write(out_image)

    os.remove(raster)

    return raster, out_meta


if __name__ == '__main__':
    ruian_path = "data/ruian/praha/praha_ruian.shp"
    roads_path = "data/ruian/casti/Praha 11/ulicni_sit_p11.shp"
    mestska_cast = "Praha 11"
    ortho_path = os.path.join("data/ortofoto/", mestska_cast)
    if not os.path.exists(ortho_path):
        os.mkdir(ortho_path)

    driver = ogr.GetDriverByName('ESRI Shapefile')

    open_ruian = driver.Open(ruian_path, 0)

    layer_ruian = open_ruian.GetLayer(0)

    layer_ruian.SetAttributeFilter("NAZEV = '{}'".format(mestska_cast))

    feature_ruian = layer_ruian.GetNextFeature()
    geom_ruian = feature_ruian.geometry().Clone()

    #print(layer_ruian.GetFeatureCount())

    #feature_ruian = layer_ruian.GetFeature(0)

    #geom_ruian = feature_ruian.GetGeometryRef()

    minX, maxX, minY, maxY = geom_ruian.GetEnvelope()

    print(minX, maxX, minY, maxY)

    envelope_ruian = my_envelope(minX, maxX, minY, maxY)


    if len(os.listdir(ortho_path)) == 0:

        browser_driver = webdriver.Chrome("C:/Drivers/Chrome/chromedriver.exe")

        browser_driver.get("https://www.geoportalpraha.cz/cs/data/otevrena-data/A1324401-980B-44C0-80D6-5353AFEC437E")

        content = browser_driver.page_source
        soup = BeautifulSoup(content)

        for link in soup.findAll('a', href=True, attrs={'class': 'open-data-icon-rastr open-data-link'}):
            filename_jgw = link.get('data-pt-title')
            #print(filename_jgw)
            if filename_jgw[-3:] == 'jgw':
                URL_jgw = link.get('href')
                response_jgw = requests.get(URL_jgw)
                filepath_jgw = os.path.join(ortho_path, filename_jgw)
                if not os.path.exists(filepath_jgw):
                    open(filepath_jgw, "wb").write(response_jgw.content)
                with open(filepath_jgw, "r") as f:
                    lines = f.readlines()
                centreX = float(lines[4][:-2])
                centreY = float(lines[5][:-2])
                pixelX = float(lines[0][:-2])
                pixelY = float(lines[3][:-2])
                tile_minX = centreX - pixelX/2
                tile_maxX = centreX + 625.0 - pixelX/2
                tile_minY = centreY - 500.0 - pixelY/2
                tile_maxY = centreY - pixelY/2

                #raster_WKT = 'POLYGON ((' + str(tile_maxX) + ' ' + str(tile_maxY) + ', ' \
                #                          + str(tile_minX) + ' ' + str(tile_maxY) + ', ' \
                #                          + str(tile_minX) + ' ' + str(tile_minY) + ', ' \
                #                          + str(tile_maxX) + ' ' + str(tile_minY) + ', ' \
                #                          + str(tile_maxX) + ' ' + str(tile_maxY) + '))'

                envelope_ortho = my_envelope(tile_minX, tile_maxX, tile_minY, tile_maxY)

                intersect = envelope_ortho.Intersects(geom_ruian)
                #print(intersect)

                if intersect is True:
                    filepath_jpg = filepath_jgw[:-3] + 'jpg'
                    filepath_tif = filepath_jgw[:-3] + 'tif'
                    URL_jpg = URL_jgw[:-3] + 'jpg'
                    response_jpg = requests.get(URL_jpg)
                    if not os.path.exists(filepath_jpg):
                        open(filepath_jpg, "wb").write(response_jpg.content)
                    ortho_ds = gdal.Open(filepath_jpg)
                    ortho_ds = gdal.Translate(filepath_tif, ortho_ds)
                    ortho_ds = None
                    os.remove(filepath_jpg)

                os.remove(filepath_jgw)
                envelope_ortho = None
        open_ruian = None
        layer_ruian = None
        feature_ruian = None
        geom_ruian = None
        envelope_ruian = None

    raster2mosaic(ortho_path, roads_path)












