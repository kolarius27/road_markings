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
import geopandas as gpd

def main():
    # loading files
    ruian_path = "data/ruian/praha/praha_ruian.shp"
    roads_path = "data/ruian/casti/Praha 11/ulicni_sit_p11.shp"
    crosswalks_path = "data/ruian/casti/Praha 11/praha11_prechody.shp"
    mestska_cast = "Praha 11"

    # checking if path exists
    ortho_path = os.path.join("data/ortofoto/", mestska_cast)
    if not os.path.exists(ortho_path):
        os.mkdir(ortho_path)

    # get city county geometry
    prague_data = gpd.read_file(ruian_path)
    county_data = prague_data.loc('NAZEV'==mestska_cast)

    # create roads geometry
    roads_data = gpd.read_file(roads_path)
    roads_clip = roads_data.clip(county_data['geometry'])
    roads_geom = gpd.GeoSeries(roads_clip)
    roads_buffer = roads_geom.buffer(distance=7)

    # envelope
    county_envelope = my_envelope(county_data, 0)

    # soup
    browser_driver = webdriver.Chrome("C:/Drivers/Chrome/chromedriver.exe")

    browser_driver.get("https://www.geoportalpraha.cz/cs/data/otevrena-data/A1324401-980B-44C0-80D6-5353AFEC437E")

    content = browser_driver.page_source
    soup = BeautifulSoup(content)

    # for every link in soup with 'jgw'
    for link in soup.findAll('a', href=True, attrs={'class': 'open-data-icon-rastr open-data-link'}):
        filename_jgw = link.get('data-pt-title')
        # download jgw
        if filename_jgw[-3:] == 'jgw':
            URL_jgw = link.get('href')
            response_jgw = requests.get(URL_jgw)
            filepath_jgw = os.path.join(ortho_path, filename_jgw)
            if not os.path.exists(filepath_jgw):
                open(filepath_jgw, "wb").write(response_jgw.content)
            with open(filepath_jgw, "r") as f:
                lines = f.readlines()

        # create envelope

        # intersect

        # if intersect is true, download jpg
            # clip by roads geometry

    # create screenshots


def my_envelope(data, dist):
    geoseries = gpd.GeoSeries(data)
    envelope = geoseries.envelope
    buffer = gpd.GeoSeries(envelope).buffer(distance=dist)
    return buffer


def jgw2poly(lines):
    pass


if __name__ == '__main__':
    main()