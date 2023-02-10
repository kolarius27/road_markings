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
from shapely import box
import geopandas as gpd

def main():
    # city county
    mestska_cast = "Praha 11"
    crosswalks_name = mestska_cast.replace(' ', '') + "_prechody.shp"
    sikme_pruhy_name = mestska_cast.replace(' ', '') + "_sikmepruhy.shp"

    # loading files
    ruian_path = "data/ruian/praha/praha_ruian.shp"
    roads_path = "data/ruian/praha/roads_praha_krovak.shp"
    jgw_path = "data/_jgws/praha_jgw.shp"
    crosswalks_path = os.path.join("data", mestska_cast, crosswalks_name)
    sikme_pruhy_path = os.path.join("data", mestska_cast, sikme_pruhy_name)

    # checking if path exists
    ortho_path = os.path.join("data", mestska_cast, "ortofoto")
    if not os.path.exists(ortho_path):
        os.mkdir(ortho_path)

    # get city county geometry
    prague_data = gpd.read_file(ruian_path)
    county_data = prague_data.loc('NAZEV'==mestska_cast)

    # create roads geometry
    roads_data = gpd.read_file(roads_path)
    roads_clip = roads_data.clip(county_data)
    roads_geom = gpd.GeoSeries(roads_clip)
    roads_buffer = roads_geom.buffer(distance=7)

    # envelope
    county_envelope = my_envelope(county_data, 20)

    # soup
    browser_driver = webdriver.Chrome("C:/Drivers/Chrome/chromedriver.exe")

    browser_driver.get("https://www.geoportalpraha.cz/cs/data/otevrena-data/A1324401-980B-44C0-80D6-5353AFEC437E")

    content = browser_driver.page_source
    soup = BeautifulSoup(content)

    # for every link in soup with 'jgw'
    if not os.path.exists(jgw_path):
        list_of_jgws(soup, jgw_path)
        print('done')
    else:
        print('List of jgws is already created.')
    


        # if intersect is true, download jpg
            # clip by roads geometry

    # create screenshots


def my_envelope(data, dist):
    geoseries = gpd.GeoSeries(data)
    envelope = geoseries.envelope
    buffer = gpd.GeoSeries(envelope).buffer(distance=dist)
    return buffer


def jgw2poly(lines):
    centreX = float(lines[4][:-2])
    centreY = float(lines[5][:-2])
    pixelX = float(lines[0][:-2])
    pixelY = float(lines[3][:-2])
    minX = centreX - pixelX/2
    maxX = centreX + 625.0 - pixelX/2
    minY = centreY - 500.0 - pixelY/2
    maxY = centreY - pixelY/2
    return box(minX, minY, maxX, maxY)

def list_of_jgws(soup, shapefile):
    url_list = []
    file_list = []
    geom_list =[]

    for link in soup.findAll('a', href=True, attrs={'class': 'open-data-icon-rastr open-data-link'}):
        filename_jgw = link.get('data-pt-title')
        # download jgw
        if filename_jgw[-3:] == 'jgw':
            URL_jgw = link.get('href')
            response_jgw = requests.get(URL_jgw)
            filepath_jgw = os.path.join("_jgws", filename_jgw)
            if not os.path.exists(filepath_jgw):
                open(filepath_jgw, "wb").write(response_jgw.content)
            with open(filepath_jgw, "r") as f:
                lines = f.readlines()
            jgw_envelope = jgw2poly(lines)

            URL_jpg = URL_jgw[:-3] + 'jpg'

            url_list.append(URL_jpg)
            file_list.append(filepath_jgw)
            geom_list.append(jgw_envelope)
            print(filename_jgw, URL_jpg, jgw_envelope)

    gdf = gpd.GeoDataFrame({'url': url_list, 'jgw': file_list, 'geometry': geom_list}, crs="EPSG:5514")
    gdf.to_file(shapefile)



if __name__ == '__main__':
    main()