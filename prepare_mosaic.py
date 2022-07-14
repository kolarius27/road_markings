import arcpy
from bs4 import BeautifulSoup
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