from bs4 import BeautifulSoup
import pandas as pd
from shapely.geometry import box
from shapely.geometry import Polygon, MultiPolygon
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
import geopandas as gpd
import shutil
from rasterio.plot import show
from rasterio.merge import merge
from rasterio.windows import Window
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.features import rasterize
import rasterio as rio
import matplotlib.pyplot as plt
import numpy as np
import glob


def main():
    # city county
    mestska_cast = "Praha 3"
    crosswalks_name = mestska_cast.replace(' ', '') + "_prechody.shp"
    sikme_pruhy_name = mestska_cast.replace(' ', '') + "_sikmepruhy.shp"

    # create dirs
    create_dirs(mestska_cast)

    # loading files
    ruian_path = "data/ruian/praha/praha_ruian.shp"
    roads_path = "data/ruian/praha/roads_praha_krovak.shp"
    roads_buffer_path = "data/ruian/praha/roads_buffer_praha_krovak.shp"
    jgw_path = "data/_jgws/praha_jgw.shp"
    crosswalks_path = os.path.join("data", mestska_cast, "crosswalks", crosswalks_name)
    sikme_pruhy_path = os.path.join("data", mestska_cast, "crosswalks", sikme_pruhy_name)


    # get city county geometry
    prague_data = gpd.read_file(ruian_path)
    county_data = prague_data.loc[prague_data['NAZEV'] == mestska_cast]
    county_geom = county_data.iloc[0]['geometry']

    # get roads buffer geometry by county
    roads_buffer_data = gpd.GeoDataFrame.from_file(roads_buffer_path)
    roads_buffer_geom = roads_buffer_data.loc[roads_buffer_data['NAZEV'] == mestska_cast]['geometry']

    # envelope
    county_envelope = my_envelope(county_geom, 20, 'envelope')

    # for every link in soup with 'jgw'
    jgw_shp = list_of_jgws(jgw_path)

    jgw_subset = subset_of_jgw(jgw_shp, county_envelope)
    
    # download images
    prepare_ortophotos(jgw_subset, mestska_cast)
    print('orthophotos downloaded')

    # clip by buffer
    clip_orthophotos(jgw_subset, roads_buffer_geom)
    print('ortophotos clipped')

    # create screenshots
    if os.path.exists(crosswalks_path) is True:
        crosswalks = gpd.GeoDataFrame.from_file(crosswalks_path)
        
        create_screenshots(jgw_subset, crosswalks)
        print('screens completed')
        # save crosswalks
        crosswalks.to_file(crosswalks_path)
        print('crosswalks saved')



def create_dirs(county_name):
    county_dir = os.path.join("data", county_name)
    if not os.path.exists(county_dir):
        os.mkdir(county_dir)
    for folder in ['crosswalks', 'ortofoto', 'roads_orto']:
        folder_path = os.path.join(county_dir, folder)
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)


def my_envelope(geom, dist, shape):
    minX, minY, maxX, maxY = geom.bounds

    if shape == 'square':
        dX = maxX - minX
        dY = maxY - minY
        cX = minX + dX/2
        cY = minY + dY/2
        if dX > dY:
            delta = dX/2
        else:
            delta = dY/2
        minX = cX - delta - dist
        minY = cY - delta - dist
        maxX = cX + delta + dist
        maxY = cY + delta + dist
        boundary = box(minX, minY, maxX, maxY)
        return boundary
    
    elif shape == 'envelope':
        boundary = box(minX, minY, maxX, maxY)
        return boundary.buffer(distance=dist)


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


def list_of_jgws(shapefile):
    if not os.path.exists(shapefile):
        # soup
        browser_driver = webdriver.Chrome("C:/Drivers/Chrome/chromedriver.exe")

        browser_driver.get("https://www.geoportalpraha.cz/cs/data/otevrena-data/A1324401-980B-44C0-80D6-5353AFEC437E")

        content = browser_driver.page_source
        soup = BeautifulSoup(content)

        url_list = []
        file_list = []
        geom_list =[]

        for link in soup.findAll('a', href=True, attrs={'class': 'open-data-icon-rastr open-data-link'}):
            filename_jgw = link.get('data-pt-title')
            # download jgw
            if filename_jgw[-3:] == 'jgw':
                URL_jgw = link.get('href')
                response_jgw = requests.get(URL_jgw)
                filepath_jgw = os.path.join("data/_jgws", filename_jgw)
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
    else:
        print('jgw list already created')
        return gpd.GeoDataFrame.from_file(shapefile)


def subset_of_jgw(jgw_shp, envelope):
    bbox = envelope.bounds
    # print(bbox)
    return jgw_shp.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]


def prepare_ortophotos(subset, county_name):
    destination = os.path.join("data", county_name, "ortofoto")
    list_jpg = []
    list_jgw = []

    for _, row in subset.iterrows():
        input_jgw_path = row['jgw']
        filename_jgw = os.path.split(input_jgw_path)[1]
        filepath_jgw = os.path.join(destination, filename_jgw)
        if not os.path.exists(filepath_jgw):
            shutil.copyfile(input_jgw_path, filepath_jgw)
        else:
            print(filename_jgw, ' already copied')

        filename_jpg = filename_jgw[:-3] + 'jpg'
        filepath_jpg = os.path.join(destination, filename_jpg)
        if not os.path.exists(filepath_jpg):
            URL_jpg = row['url']
            response_jpg = requests.get(URL_jpg)
            open(filepath_jpg, "wb").write(response_jpg.content)
        else:
            print(filename_jpg, ' already downloaded')

        list_jgw.append(filepath_jgw)
        list_jpg.append(filepath_jpg)

    subset['new_jgw'] = list_jgw
    subset['jpg'] = list_jpg



def merge_orthophotos(subset, extent):
    rasters = subset['jpg']
    raster_to_mosaic = [rio.open(r) for r in rasters]

    mosaic, transform = merge(raster_to_mosaic, bounds=extent.bounds)

    out_meta = update_meta(raster_to_mosaic[0], mosaic, transform)

    return mosaic, out_meta


def clip_orthophotos(subset, geoms):
    for jpg, s_geom in zip(subset['jpg'], subset['geometry']):
        split_jpg = jpg.split('\\')
        output_tif = os.path.join(split_jpg[0], split_jpg[1], 'roads_orto', split_jpg[-1][:-3] + 'tif')
        if not os.path.exists(output_tif):
            intersect_geom = False
            for geom in geoms:
                intersect_geom = geom.intersects(s_geom)
            if intersect_geom is True:
                print(jpg)
                mosaic, meta = clip_orthophoto(jpg, geoms)
                with rio.open(output_tif, 'w', **meta) as dst:
                    dst.write(mosaic)


def clip_orthophoto(raster_path, poly):
    with rio.open(raster_path) as src:
        mosaic, transform = mask(src, poly, crop=False)
        out_meta = update_meta(src, mosaic, transform)
    return mosaic, out_meta


def update_meta(raster, mosaic, output):
    meta = raster.meta.copy()
    meta.update(
        {
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": output,
            "crs": "EPSG:5514"
        }
    )
    return meta


def create_img(img_path ,mosaic, meta, fid, row):
    geom = row['geometry'].boundary
    geometry = gpd.GeoSeries([geom])
    # fig = plt.figure(frameon=False)
    # ax = fig.add_axes([0, 0, 1, 1])
    # ax.axis('off')


    red = rasterize(((g, 255) for g in geometry), transform=meta['transform'], out=mosaic[0].copy(), all_touched=True)
    green = rasterize(((g, 0) for g in geometry), transform=meta['transform'], out=mosaic[1].copy(), all_touched=True)
    blue = rasterize(((g, 0) for g in geometry), transform=meta['transform'], out=mosaic[2].copy(), all_touched=True)
    image = np.array([red, green, blue])
    # show(image, transform=meta['transform'], ax=ax, cmap='Spectral')
    # geometry.plot(ax=ax, facecolor='none', edgecolor='red')
    # plt.savefig(img_path, bbox_inches='tight', pad_inches = 0)
    with rio.open(img_path, 'w', **meta) as dst:
        dst.write(image)
    # plt.show()


def check_files(list_of_features, folder, extension):
    if len(list_of_features) == len(glob.glob(os.path.join(folder, '*.{}'.format(extension)))):
        return True
    else:
        return False



def create_screenshots(subset, crosswalks):
    img_list = []
    i=0
    
    for fid, row in crosswalks.iterrows():
        mestska_cast = row['Mest_cast']
        img_name = 'img/{}_{}.jpg'.format(mestska_cast.replace(' ', ''), fid)
        img_path = os.path.join('data', mestska_cast, 'crosswalks', img_name)

        if not os.path.exists(img_path):
            extent = my_envelope(row['geometry'], 5, 'square')
            subset_crosswalks = subset_of_jgw(subset, extent)
            if subset_crosswalks.shape[0] > 1:
                mosaic, meta = merge_orthophotos(subset_crosswalks, extent)
            else:
                # ext_feature = gpd.GeoDataFrame(geometry=extent, crs="EPSG:5514")
                mosaic, meta = clip_orthophoto(subset_crosswalks.iloc[0]['jpg'], [extent])

            create_img(mosaic, meta, fid, row)

        img_list.append(img_name)
        i+=1
        print(i)

    crosswalks['img'] = img_list


if __name__ == '__main__':
    main()