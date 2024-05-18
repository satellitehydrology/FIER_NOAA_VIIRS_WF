import os
import folium
import folium.plugins as plugins
import streamlit as st
from streamlit_folium import folium_static
from PIL import Image
from xyzservices.lib import TileProvider

from syn_noaa2 import *
import urllib
import json
import xarray as xr
import numpy.ma as ma
import pandas as pd
from scipy import interpolate
import matplotlib.pyplot as plt
import datetime
import branca
import branca.colormap as cm
import ssl
import time

# Initialize basemap
basemap = TileProvider.from_qms("OpenTopoMap")

if 'AOI_str' not in st.session_state:
    st.session_state.AOI_str = 'MississippiRiver'

# Page Configuration
st.set_page_config(layout="wide")

# Title and Description
st.title("Forecasting Inundation Extents using REOF analysis (FIER) – VIIRS/ABI Water Fraction")

row1_col1, row1_col2 = st.columns([2, 1])
# Set up Geemap
with row1_col1:
    m = folium.Map(
        zoom_start=4,
        location=(36.52, -89.55),
        control_scale=True,
    )

    plugins.Fullscreen(position='topright').add_to(m)
    folium.TileLayer(basemap).add_to(m)
    m.add_child(folium.LatLngPopup())
    folium.LayerControl().add_to(m)

with row1_col2:
    st.subheader('Determine Region of Interest')
    with st.form('Select Region'):
        region = st.selectbox(
            'Determine region:',
            ('Mississippi River', 'Red River'),
        )
        submitted = st.form_submit_button("Submit")
        if submitted:
            AOI_str = region.replace(" ", "")
            st.session_state.AOI_str = AOI_str
            st.write(st.session_state.AOI_str)

    run_type = st.radio('National Water Model Forecast Configurations:',
                        ('Medium-Range (archived 8-day forecasts)', 
                         'Bias-corrected Medium-Range (archived 8-day forecasts)', 
                         'Short-Range', 'Medium-Range', 'Long-Range'))

    with st.form("FIER with NWM Analysis Simulation"):
        if run_type == 'Analysis Simulation':
            in_run_type = 'analysis_assim'

            ssl._create_default_https_context = ssl._create_stdlib_context
            webURL = urllib.request.urlopen('https://nwmdata.nohrsc.noaa.gov/latest/forecasts/' + in_run_type + '/streamflow?&station_id=7469342')
            data = webURL.read()
            encoding = webURL.info().get_content_charset('utf-8')
            JSON_object = json.loads(data.decode(encoding))
            exp_fct_data = pd.DataFrame(JSON_object[0]["data"])["forecast-time"]
            exp_fct_time = pd.to_datetime(exp_fct_data)
            first_date = exp_fct_time[0]
            first_datestr = first_date.strftime('%Y-%m-%d')
            last_date = exp_fct_time[len(exp_fct_time)-1]
            last_datestr = last_date.strftime('%Y-%m-%d')
            date = st.date_input(
                "Select the date with available NWM forecast (" + first_datestr + " to " + last_datestr + " UTC):",
                value=first_date,
                min_value=first_date,
                max_value=last_date,
            )
            submitted = st.form_submit_button("Submit")
            if submitted:
                AOI_str = st.session_state.AOI_str
                bounds = run_fier(AOI_str, str(date), in_run_type)
                st.write(AOI_str)

                if region == 'Mississippi River':
                    location = [36.62, -89.15] 
                elif region == 'Red River':
                    location = [48.44, -97.17]

                m = folium.Map(
                    zoom_start=8,
                    location=location,
                    control_scale=True,
                )

                # Introduce delay if necessary
                time.sleep(2)

                image_path = 'Output/water_fraction.png'
                if not os.path.exists(image_path):
                    st.error(f"No such file or directory: '{image_path}'")
                else:
                    folium.raster_layers.ImageOverlay(
                        image=image_path,
                        bounds=bounds,
                        opacity=0.5,
                        name='Water Fraction Map',
                        show=True,
                    ).add_to(m)

                    colormap = cm.LinearColormap(colors=['blue', 'green', 'red'],
                                                 vmin=0, vmax=100,
                                                 caption='Water Fraction (%)')
                    m.add_child(colormap)

                    plugins.Fullscreen(position='topright').add_to(m)
                    folium.TileLayer(basemap).add_to(m)
                    m.add_child(folium.LatLngPopup())
                    folium.LayerControl().add_to(m)

        # Repeat similar checks and logic for other run_type conditions here...

    try:
        with open('Output/output.nc', 'rb') as f:
            st.download_button('Download Latest Run Output',
                               f,
                               file_name='water_fraction_%s_%s.nc' % (AOI_str, date),
                               mime="application/netcdf")
    except FileNotFoundError:
        st.error("Output file not found. Ensure the FIER process has completed successfully.")

with row1_col1:
    folium_static(m, height=600, width=900)
    st.write('Disclaimer: This is a test version of FIER using VIIRS-derived water fraction maps over selected regions in US.')
    url = "https://uofh-my.sharepoint.com/:p:/g/personal/cchang37_cougarnet_uh_edu/ERVoJqA2BIZHgf2BYUwLiSsBFTTeOpyKYsCjSB0PlbdaSw?e=8Phoq3"
    url_1 = "https://www.sciencedirect.com/science/article/pii/S0034425720301024?casa_token=kOYlVMMWkBUAAAAA:fiFM4l6BUzJ8xTCksYUe7X4CcojddbO8ybzOSMe36f2cFWEXDa_aFHaGeEFlN8SuPGnDy7Ir8w"
    st.write("Reference: [Chang et al. (2023)](%s), [Chang et al. (2020)](%s)" % (url, url_1))
    st.write("This app has been developed by Chi-Hung Chang  & Son Do at University of Houston with supports from NOAA JPSS program.")
    st.write("Kel Markert at the Brigham Young University is also acknowledged for the development of this App.")

    uh = Image.open("logo/uh_logo_2.png")
    noaa = Image.open("logo/noaa_logo.png")
    st.image([uh, noaa], width=100)
