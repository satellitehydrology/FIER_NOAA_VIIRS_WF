import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from tensorflow.keras import models
import tensorflow as tf
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.colors

import urllib
import json
import ssl

import datetime as dt
import pandas as pd
from scipy import interpolate
import time


def perf_qm_quick(hist_real_wf_stack, hist_syn_wf_stack, fct_syn_wf_stack, qm_mask, nbins=100):
    """
    :param hist_real_wf_stack: Historical real water fraction as reference to get the scales
    :param hist_syn_wf_stack: Historical synthesized water fraction to get the scales
    :param fct_syn_wf_stack: Forecasted synthesized water fraction to be scaled
    :param qm_mask: Mask of where quantile scaling will be performed, based on the pre-generated correlation between
                    historical observed and synthesized water fractions (Default is Spearman's correlation)
    :param nbins: Number of bins to get the quantile (default: 100)
    :return: Quantile-caled forecasted synthesized water fraction
    """

    binmid = np.arange(0, 1. + 1. / nbins, 1. / nbins)

    obs = hist_real_wf_stack.values
    syn = hist_syn_wf_stack.values

    qobs = np.nanquantile(obs, binmid, axis=0)
    qsyn = np.nanquantile(syn, binmid, axis=0)

    for ct_r in np.arange(fct_syn_wf_stack.shape[1]):
        for ct_c in np.arange(fct_syn_wf_stack.shape[2]):

            if qm_mask[ct_r, ct_c].values == True:
                bin_fct_syn = np.interp(fct_syn_wf_stack[:, ct_r, ct_c], qsyn[:, ct_r, ct_c], binmid)
                fct_syn_wf_stack[:, ct_r, ct_c] = np.interp(bin_fct_syn, binmid, qobs[:, ct_r, ct_c])

    fct_syn_wf_stack[fct_syn_wf_stack > 100] = 100
    fct_syn_wf_stack[fct_syn_wf_stack < 0] = 0

    return fct_syn_wf_stack


def perf_qm_month_quick(hist_real_wf_stack, hist_syn_wf_stack, fct_syn_wf_stack, qm_mask, nbins=100):
    """
    :param hist_real_wf_stack: Historical real water fraction as reference to get the scales
    :param hist_syn_wf_stack: Historical synthesized water fraction to get the scales
    :param fct_syn_wf_stack: Forecasted synthesized water fraction to be scaled
    :param qm_mask: Mask of where quantile scaling will be performed, based on the pre-generated correlation between
                    historical observed and synthesized water fractions (Default is Spearman's correlation)
    :param nbins: Number of bins to get the quantile (default: 100)
    :return: Quantile-scaled forecasted synthesized water fraction
    """
    binmid = np.arange(0, 1. + 1. / nbins, 1. / nbins)

    obs = hist_real_wf_stack.values
    syn = hist_syn_wf_stack.values
    hist_mon = pd.to_datetime(hist_real_wf_stack.time.values).month

    fct_time = fct_syn_wf_stack.time
    fct_mon = pd.to_datetime(fct_syn_wf_stack.time.values).month
    uniq_fct_mon = np.unique(fct_mon)

    for uniq_mon in uniq_fct_mon:

        obs_mon = obs[hist_mon == uniq_mon, :, :]
        syn_mon = syn[hist_mon == uniq_mon, :, :]
        fct_syn_mon = fct_syn_wf_stack[fct_mon == uniq_mon, :, :]

        qobs = np.nanquantile(obs_mon, binmid, axis=0)
        qsyn = np.nanquantile(syn_mon, binmid, axis=0)

        for ct_r in range(fct_syn_wf_stack.shape[1]):
            for ct_c in range(fct_syn_wf_stack.shape[2]):

                if qm_mask[ct_r, ct_c].values == True:
                    bin_fct_syn = np.interp(fct_syn_wf_stack[fct_mon==uniq_mon, ct_r, ct_c], qsyn[:, ct_r, ct_c], binmid)
                    fct_syn_wf_stack[fct_mon==uniq_mon, ct_r, ct_c] = np.interp(bin_fct_syn, binmid, qobs[:, ct_r, ct_c])

    fct_syn_wf_stack[fct_syn_wf_stack > 100] = 100
    fct_syn_wf_stack[fct_syn_wf_stack < 0] = 0

    return fct_syn_wf_stack



def perf_qm(fct_syn_wf_stack, qm_scaling_path, qm_mask):
    """
    This function quantile-scales the synthesized water fraction pixel-by-pixel based one the
    historical observed and synthesized water fractions

    :param fct_syn_wf_stack: Synthesized forecasted water fractions without quantile scaling
    :param qm_scaling_path: Path to the pre-fitted quantile scaling function
    :param qm_mask: Mask of where quantile scaling will be performed, based on the pre-generated correlation between
                    historical observed and synthesized water fractions (Default is Spearman's correlation)
    :return: Quantile-scaled synthesized forecasted water fractions
    """
    wf2quant_funcs = np.load(qm_scaling_path + 'wf2quant_funcs.npy', allow_pickle=True).item()
    quant2wf_funcs = np.load(qm_scaling_path + 'quant2wf_funcs.npy', allow_pickle=True).item()

    for ct_r in np.arange(fct_syn_wf_stack.shape[1]):
        for ct_c in np.arange(fct_syn_wf_stack.shape[2]):
            if qm_mask[ct_r, ct_c].values==True: #don't ignore ".values==True" part, otherwise will fail to get into the process
                try:
                     wf2quant = wf2quant_funcs['r'+str(ct_r)+'_c'+str(ct_c)]
                     quant2wf = quant2wf_funcs['r'+str(ct_r)+'_c'+str(ct_c)]
                except:
                    if fct_syn_wf_stack[0,ct_r,ct_c] > 100:
                        fct_syn_wf_stack[0,ct_r,ct_c] = 100
                    elif fct_syn_wf_stack[0,ct_r,ct_c] < 0:
                        fct_syn_wf_stack[0,ct_r,ct_c] = 0
                    continue
            else:
                continue

            temp = quant2wf(wf2quant(fct_syn_wf_stack[0,ct_r,ct_c]))
            if temp>100:
                temp = 100
            elif temp<0:
                temp = 0

            fct_syn_wf_stack[0,ct_r,ct_c] = temp

    return fct_syn_wf_stack


def perf_qm_mon(fct_syn_wf_stack, fct_date, qm_scaling_path, qm_mask):
    #import traceback #For printing error message
    """
    This function climatologically quantile-scales the synthesized water fraction pixel-by-pixel based one the
    historical observed and synthesized water fractions

    :param fct_syn_wf_stack: Synthesized forecasted water fractions without quantile scaling
    :param fct_date: Forecasting date
    :param qm_scaling_path: Path to the pre-fitted quantile scaling function
    :param qm_mask: Mask of where quantile scaling will be performed, based on the pre-generated correlation between
                    historical observed and synthesized water fractions (Default is pearson correlation)
    :return: Quantile-scaled synthesized forecasted water fractions
    """

    wf2quant_funcs = np.load(qm_scaling_path + 'wf2quant_mon_funcs.npy', allow_pickle=True).item()
    quant2wf_funcs = np.load(qm_scaling_path + 'quant2wf_mon_funcs.npy', allow_pickle=True).item()

    if type(fct_date)==str:
        fct_date = pd.to_datetime(fct_date)
    fct_mon = fct_date.month


    for ct_r in np.arange(fct_syn_wf_stack.shape[1]):
        for ct_c in np.arange(fct_syn_wf_stack.shape[2]):
            if qm_mask[ct_r, ct_c].values==True: #don't ignore ".values==True" part, otherwise will fail to get into the process
                try:
                    wf2quant = wf2quant_funcs['mon'+str(fct_mon)+'_r'+str(ct_r)+'_c'+str(ct_c)]
                    quant2wf = quant2wf_funcs['mon'+str(fct_mon)+'r'+str(ct_r)+'_c'+str(ct_c)] #Need to fix the KEY string
                except: # Exception: #For printing error message
                    #traceback.print_exc()  #For printing error message
                    if fct_syn_wf_stack[0,ct_r,ct_c] > 100:
                        fct_syn_wf_stack[0,ct_r,ct_c] = 100
                    elif fct_syn_wf_stack[0,ct_r,ct_c] < 0:
                        fct_syn_wf_stack[0,ct_r,ct_c] = 0
                    continue

            else:
                continue
            temp = quant2wf(wf2quant(fct_syn_wf_stack[0,ct_r,ct_c]))
            if temp>100:
                temp = 100
            elif temp<0:
                temp = 0

            fct_syn_wf_stack[0,ct_r,ct_c] = temp

    return fct_syn_wf_stack
import tensorflow as tf
from tensorflow.python.platform import gfile
from tensorflow.core.protobuf import saved_model_pb2
from tensorflow.python.util import compat

def load_model_from_pb(model_path):
    """Load a model from a saved_model.pb file."""
    model_filename = os.path.join(model_path, 'saved_model.pb')
    print(f"Loading model from {model_filename}")
    
    with tf.compat.v1.Session() as sess:  # Use compat.v1 for TensorFlow 2.x compatibility
        with gfile.FastGFile(model_filename, 'rb') as f:
            data = compat.as_bytes(f.read())
            sm = saved_model_pb2.SavedModel()
            sm.ParseFromString(data)
            tf.import_graph_def(sm.meta_graphs[0].graph_def)
        print(f"Model successfully loaded from {model_filename}")
    return sess.graph
import tensorflow as tf
import os

def load_and_verify_saved_model(model_path):
    """
    Load and verify a SavedModel from a given directory.
    """
    try:
        model = tf.saved_model.load(model_path)
        print(f"Model successfully loaded from {model_path}")
        # List available signatures
        print("Available Signatures:")
        for signature in model.signatures:
            print(signature)
        return model
    except Exception as e:
        print(f"Failed to load model from {model_path}: {e}")
        raise

# Example usage:
# load_and_verify_saved_model('path/to/saved_model_directory')

import tensorflow as tf
import os
import json
import urllib.request
import datetime as dt
import pandas as pd
import xarray as xr
import numpy as np
import ssl
import time
import matplotlib.pyplot as plt

def run_fier(AOI_str, doi, in_run_type):
    # Path to read necessary data
    TF_model_path = 'AOI/' + AOI_str + '/TF_model/'
    qm_scaling_path = 'AOI/' + AOI_str + '/for_qm_scaling/'

    hist_real_stack_path = qm_scaling_path + 'hist_real_wf_trim.nc'
    hist_syn_stack_path = qm_scaling_path + 'hist_syn_wf_trim.nc'

    RSM_path = 'AOI/' + AOI_str + '/RSM/SM_hydro_App.nc'
    jrc_perm_water_path = 'AOI/' + AOI_str + '/RSM/JRC_perm_water.nc'
    qm_pr_r_mask_path = qm_scaling_path + 'qm_pr_r_mask.nc'
    qm_spr_r_mask_path = qm_scaling_path + 'qm_spr_r_mask.nc'

    # Path to archived NWM forecast
    nwm_archive_path = 'AOI/' + AOI_str + '/nwm_archive/medium_lt08_App.nc'
    nwm_bias_corrected_archive_path = 'AOI/' + AOI_str + '/nwm_archive/medium_lt08_App_biascorrected.nc'

    # Read necessary data
    xr_RSM = xr.load_dataset(RSM_path)
    hist_obs_wf = xr.load_dataarray(hist_real_stack_path, decode_coords='all')
    hist_syn_wf = xr.load_dataarray(hist_syn_stack_path, decode_coords='all')
    jrc_perm_water = xr.load_dataarray(jrc_perm_water_path, decode_coords='all')
    # qm_mask = xr.load_dataarray(qm_pr_r_mask_path)
    qm_mask = xr.load_dataarray(qm_spr_r_mask_path)
    nwm_archive = xr.load_dataarray(nwm_archive_path)
    nwm_bias_corrected_archive = xr.load_dataarray(nwm_bias_corrected_archive_path)

    wf_mean = xr_RSM.temporal_mean.values

    # Initialize fct_syn_wf to None
    fct_syn_wf = None

    for ct_mode in range(xr_RSM.sizes['mode']):
        mode = xr_RSM.spatial_modes.mode[ct_mode].values

        sm = xr_RSM.spatial_modes.sel(mode=mode)
        site = xr_RSM.hydro_site.sel(mode=mode).values
        nwm_site = xr_RSM.nwm_site.sel(mode=mode).values
        RTPC_std = xr_RSM.model_RTPC_std_sel.sel(mode=mode).values
        RTPC_mean = xr_RSM.model_RTPC_mean_sel.sel(mode=mode).values

        if in_run_type == 'archive':
            doi_fct_q = nwm_archive.sel(site=nwm_site).sel(time=pd.to_datetime(doi)).values
        elif in_run_type == 'biascorrection':
            doi_fct_q = nwm_bias_corrected_archive.sel(site=nwm_site).sel(time=pd.to_datetime(doi)).values
        else:
            ssl._create_default_https_context = ssl._create_stdlib_context
            webURL = urllib.request.urlopen('https://nwmdata.nohrsc.noaa.gov/latest/forecasts/' + in_run_type + '/streamflow?&station_id=' + str(nwm_site))
            data = webURL.read()
            encoding = webURL.info().get_content_charset('utf-8')
            JSON_object = json.loads(data.decode(encoding))

            fct_datetime = pd.to_datetime(pd.DataFrame(JSON_object[0]["data"])["forecast-time"])
            doi_indx0 = fct_datetime >= (dt.datetime.strptime(doi, '%Y-%m-%d'))
            doi_indx1 = (fct_datetime < (dt.datetime.strptime(doi, '%Y-%m-%d')) + dt.timedelta(days=1))
            doi_indx = doi_indx0 & doi_indx1

            doi_fct_datetime = fct_datetime[doi_indx]
            doi_fct_q = (pd.DataFrame(JSON_object[0]["data"])['value'][doi_indx] * 0.0283168).mean()

        # Attempt to load the model using the new high-level API function
        model_path = os.path.join(TF_model_path, f'site-{str(site)}_tpc{str(mode).zfill(2)}')
        try:
            model = tf.saved_model.load(model_path)
            print(f"Model loaded successfully from {model_path}.")
            infer = model.signatures["serving_default"]
        except Exception as e:
            print(f"Failed to load model from {model_path}: {e}")
            continue

        # Assuming 'serving_default' is the signature name, you can modify this as per your model
        in_good_hydro = tf.convert_to_tensor([doi_fct_q], dtype=tf.float32)
        est_tpc = infer(in_good_hydro)["output_0"].numpy() * RTPC_std + RTPC_mean

        est_tpc1 = np.tile(est_tpc[:, :, None], (1, sm.sizes['lat'], sm.sizes['lon']))
        sm1 = np.tile(sm.values[None, :, :], (est_tpc.shape[0], 1, 1))

        syn_wf_temp = sm1 * est_tpc1
        if fct_syn_wf is None:
            fct_syn_wf = syn_wf_temp
        else:
            fct_syn_wf = fct_syn_wf + syn_wf_temp

    if fct_syn_wf is not None:
        fct_syn_wf = fct_syn_wf + wf_mean

        st_time = time.time()
        map_fct_syn_wf = perf_qm_quick(hist_obs_wf, hist_syn_wf, fct_syn_wf, qm_mask)
        ed_time = time.time()
        print(ed_time - st_time)
        map_fct_syn_wf = np.where(jrc_perm_water == 1, 100, map_fct_syn_wf)

        # Create image
        folder_name = 'Output'
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        fig = plt.figure()
        plt.imshow(map_fct_syn_wf[0], cmap='jet', vmin=0, vmax=100, interpolation='none')
        plt.axis('off')
        plt.savefig(folder_name + '/water_fraction.png', bbox_inches='tight', dpi=600, pad_inches=0)
        plt.close()

        bounds = [[xr_RSM.lat.values.min(), xr_RSM.lon.values.min()],
                  [xr_RSM.lat.values.max(), xr_RSM.lon.values.max()]]

        out_file = xr.DataArray(
            data=map_fct_syn_wf,
            coords=dict(
                time=(["time"], [pd.to_datetime(doi)]),
                lat=(["lat"], xr_RSM.lat.values),
                lon=(["lon"], xr_RSM.lon.values)
            )
        )

        out_file.to_netcdf(folder_name + '/' + in_run_type + '_' + doi + '.nc')

        xr_RSM.close()

        return bounds
    else:
        print("No valid modes were processed.")
        return None


