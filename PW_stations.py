#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 25 15:50:20 2019

@author: shlomi
"""

import pandas as pd
import numpy as np

garner_path = work_yuval / 'garner'
ims_path = work_yuval / 'IMS_T'
gis_path = work_yuval / 'gis'
sound_path = work_yuval / 'sounding'
PW_stations_path = work_yuval / '1minute'
stations = pd.read_csv('stations.txt', header=0, delim_whitespace=True,
                       index_col='name')

# TODO: continue analyzing sounding data for tm ts formulas for season,hour
# TODO: check noon midnight correctness


def proc_1minute(path):
    stations = pd.read_csv(path + 'Zstations', header=0,
                           delim_whitespace=True)
    station_names = stations['NAME'].values.tolist()
    df_list = []
    for st_name in station_names:
        print('Proccessing ' + st_name + ' Station...')
        df = pd.read_csv(PW_stations_path + st_name, delim_whitespace=True)
        df.columns = ['date', 'time', 'PW']
        df.index = pd.to_datetime(df['date'] + 'T' + df['time'])
        df.drop(columns=['date', 'time'], inplace=True)
        df_list.append(df)
    df = pd.concat(df_list, axis=1)
    print('Concatanting to Xarray...')
    # ds = xr.concat([df.to_xarray() for df in df_list], dim="station")
    # ds['station'] = station_names
    df.columns = station_names
    ds = df.to_xarray()
    ds = ds.rename({'index': 'time'})
    # da = ds.to_array(name='PW').squeeze(drop=True)
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in ds.data_vars}
    print('Saving to PW_2007-2016.nc')
    ds.to_netcdf(work_path + 'PW_2007-2016.nc', 'w', encoding=encoding)
    print('Done!')
    # clean the data:
    # da = da.where(da >= 0, np.nan)
    # da = da.where(da < 100, np.nan)

    # plot the data:
    ds.to_array(dim='station').plot(x='time', col='station', col_wrap=4)
    # hist:
    # df=ds.to_dataframe()
    sl = (df > 0) & (df < 50)
    df[sl].hist(bins=30, grid=False, figsize=(15, 8))
    return


#def get_geo_data_from_gps_stations(gps_names):
#    import requests
#    from bs4 import BeautifulSoup as bs
#    user = "anonymous"
#    passwd = "shlomiziskin@gmail.com"
#    # Make a request to the endpoint using the correct auth values
#    auth_values = (user, passwd)
#    response = requests.get(url, auth=auth_values)
#    soup = bs(response.text, "lxml")
#    allLines = soup.text.split('\n')
#    X = [x for x in allLines if 'X coordinate' in x][0].split()[-1]
#    Y = [x for x in allLines if 'Y coordinate' in x][0].split()[-1]
#    Z = [x for x in allLines if 'Z coordinate' in x][0].split()[-1]
# 
## Convert JSON to dict and print
#print(response.json())
    
def read_stations_to_dataset(path, group_name='israeli', save=False,
                             names=None):
    import xarray as xr
    if names is None:
        stations = []
        for filename in sorted(path.glob('garner_trop_[!all_stations]*.nc')):
            st_name = filename.as_posix().split('/')[-1].split('.')[0].split('_')[-1]
            print('Reading station {}'.format(st_name))
            da = xr.open_dataarray(filename)
            da = da.dropna('time')
            stations.append(da)
        ds = xr.merge(stations)
    if save:
        savefile = 'garner_' + group_name + '_stations.nc'
        print('saving {} to {}'.format(savefile, path))
        ds.to_netcdf(path / savefile, 'w')
        print('Done!')
    return ds


def filter_stations(path, group_name='israeli', save=False):
    """filter bad values in trop products stations"""
    import xarray as xr
    from aux_gps import Zscore_xr
    filename = 'garner_' + group_name + '_stations.nc'
    print('Reading {}.nc from {}'.format(filename, path))
    ds = xr.open_dataset(path / filename)
    ds['zwd'].attrs['units'] = 'Zenith Wet Delay in cm'
    stations = [x for x in ds.data_vars.keys()]
    for station in stations:
        print('filtering station {}'.format(station))
        # first , remove negative values:
        ds[station] = ds[station].where(ds[station].sel(zwd='value') > 0)
        # get zscore of data and errors:
        zscore_val = Zscore_xr(ds[station].sel(zwd='value'), dim='time')
        zscore_sig = Zscore_xr(ds[station].sel(zwd='sigma'), dim='time')
        # filter for zscore <5 for data and <3 for error:
        ds[station] = ds[station].where(np.abs(zscore_val) < 5)
        ds[station] = ds[station].where(np.abs(zscore_sig) < 3)
    if save:
        filename = filename + '_filtered.nc'
        print('saving {} to {}'.format(filename, path))
        comp = dict(zlib=True, complevel=9)  # best compression
        encoding = {var: comp for var in ds.data_vars}
        ds.to_netcdf(path / filename, 'w', encoding=encoding)
        print('Done!')
    return ds

# def overlap_time_xr(*args, union=False):
#    """return the intersection of datetime objects from time field in *args"""
#    # caution: for each arg input is xarray with dim:time
#    time_list = []
#    for ts in args:
#        time_list.append(ts.time.values)
#    if union:
#        union = set.union(*map(set, time_list))
#        un = sorted(list(union))
#        return un
#    else:
#        intersection = set.intersection(*map(set, time_list))
#        intr = sorted(list(intersection))
#        return intr


def produce_geo_gps_stations(path, file='stations.txt', plot=True):
    import geopandas as gpd
    import xarray as xr
    stations_df = pd.read_csv(file, index_col='name',
                              delim_whitespace=True)
    isr_dem = xr.open_rasterio(path / 'israel_dem.tif')
    alt_list = []
    for index, row in stations_df.iterrows():
        lat = row['lat']
        lon = row['lon']
        alt = isr_dem.sel(band=1, x=lon, y=lat, method='nearest').values.item()
        alt_list.append(float(alt))
    stations_df['alt'] = alt_list
    isr = gpd.read_file(path / 'israel_demog2012.shp')
    isr.crs = {'init': 'epsg:4326'}
    stations = gpd.GeoDataFrame(stations_df,
                                geometry=gpd.points_from_xy(stations_df.lon,
                                                            stations_df.lat),
                                crs=isr.crs)
    stations_isr = gpd.sjoin(stations, isr, op='within')
    if plot:
        ax = isr.plot()
        stations_isr.plot(ax=ax, column='alt', cmap='Greens',
                          edgecolor='black', legend=True)
        for x, y, label in zip(stations_isr.lon, stations_isr.lat,
                               stations_isr.index):
            ax.annotate(label, xy=(x, y), xytext=(3, 3),
                        textcoords="offset points")
    return stations_isr


def get_minimum_distance(geo_ims, geo_gps, path, plot=True):
    def min_dist(point, gpd2):
        gpd2['Dist'] = gpd2.apply(
            lambda row: point.distance(
                row.geometry), axis=1)
        geoseries = gpd2.iloc[gpd2['Dist'].values.argmin()]
        geoseries.loc['distance'] = gpd2['Dist'].values.min()
        return geoseries
    min_list = []
    for gps_rows in geo_gps.iterrows():
        ims_min_series = min_dist(gps_rows[1]['geometry'], geo_ims)
        min_list.append(ims_min_series[['ID', 'name_hebrew', 'name_english',
                                        'lon', 'lat', 'alt', 'starting_date',
                                        'distance']])
    geo_df = pd.concat(min_list, axis=1).T
    geo_df['lat'] = geo_df['lat'].astype(float)
    geo_df['lon'] = geo_df['lon'].astype(float)
    geo_df['alt'] = geo_df['alt'].astype(float)
    geo_df.index = geo_gps.index
    stations_meta = ims_api_get_meta()
    # select ims_stations that appear in the geo_df (closest to gps stations):
    ims_selected = stations_meta.loc[stations_meta.stationId.isin(
        geo_df.ID.values.tolist())]
    # get the channel of temperature measurment of the selected stations:
    cid = []
    for index, row in geo_df.iterrows():
        channel = [irow['TD_channel'] for ind, irow in ims_selected.iterrows()
                   if irow['stationId'] == row['ID']]
        if channel:
            cid.append(channel[0])
        else:
            cid.append(None)
    # put the channel_id in the geo_df so later i can d/l the exact channel
    # for each stations needed for the gps station:
    geo_df['channel_id'] = cid
    geo_df['channel_id'] = geo_df['channel_id'].fillna(0).astype(int)
    geo_df['ID'] = geo_df.ID.astype(int)
    geo_df['distance'] = geo_df.distance.astype(float)
    geo_df['starting_date'] = pd.to_datetime(geo_df.starting_date)
    geo_df['gps_lat'] = geo_gps.lat
    geo_df['gps_lon'] = geo_gps.lon
    geo_df['gps_alt'] = geo_gps.alt
    geo_df['alt_diff'] = geo_df.alt - geo_gps.alt
    if plot:
        import geopandas as gpd
        isr = gpd.read_file(path / 'israel_demog2012.shp')
        isr.crs = {'init': 'epsg:4326'}
        geo_gps_new = gpd.GeoDataFrame(geo_df,
                                       geometry=gpd.points_from_xy(geo_df.lon,
                                                                   geo_df.lat),
                                       crs=isr.crs)
        ax = isr.plot()
        geo_gps.plot(ax=ax, color='green',
                     edgecolor='black', legend=True)
        for x, y, label in zip(geo_gps.lon, geo_gps.lat,
                               geo_gps.alt):
            ax.annotate(label, xy=(x, y), xytext=(3, 3),
                        textcoords="offset points")
        geo_gps_new.plot(ax=ax, color='red', edgecolor='black', legend=True)
        for x, y, label in zip(geo_gps_new.lon, geo_gps_new.lat,
                               geo_gps_new.alt):
            ax.annotate(label, xy=(x, y), xytext=(3, 3),
                        textcoords="offset points")
    return geo_df


def post_proccess_ims(da, unique_index=True, clim_period='dayofyear',
                      resample_method='ffill'):
    """fill in the missing time data for the ims temperature stations
    clim_period is the fine tuning of the data replaced, options are:
        month, weekofyear, dayofyear"""
    # da should be dattaarray and not dataset!
    import pandas as pd
    import numpy as np
    import xarray as xr
    from aux_gps import get_unique_index
    if unique_index:
        da = get_unique_index(da)
        print('dropped non-unique datetime index.')
    da = da.sel(TD='value')
    da = da.reset_coords(drop=True)
    if clim_period == 'month':
        grpby = 'time.month'
        print('long term monthly mean data replacment selected')
    elif clim_period == 'weekofyear':
        print('long term weekly mean data replacment selected')
        grpby = 'time.weekofyear'
    elif clim_period == 'dayofyear':
        print('long term daily mean data replacment selected')
        grpby = 'time.dayofyear'
    # first compute the climatology and the anomalies:
    print('computing anomalies:')
    climatology = da.groupby(grpby).mean('time')
    anom = da.groupby(grpby) - climatology
    # then comupte the diurnal cycle:
    print('computing diurnal change:')
    diurnal = anom.groupby('time.hour').mean('time')
    # assemble old and new time and comupte the difference:
    print('assembeling missing data:')
    old_time = pd.to_datetime(da.time.values)
    new_time = pd.date_range(da.time.min().item(), da.time.max().item(),
                             freq='10min')
    missing_time = pd.to_datetime(
        sorted(
            set(new_time).difference(
                set(old_time))))
    missing_data = np.empty((missing_time.shape))
    print('proccessing missing data...')
    for i in range(len(missing_data)):
        # replace data as to monthly long term mean and diurnal hour:
        # missing_data[i] = (climatology.sel(month=missing_time[i].month) +
        missing_data[i] = (climatology.sel({clim_period: getattr(missing_time[i],
                                                                 clim_period)}) +
                           diurnal.sel(hour=missing_time[i].hour))
    series = pd.Series(data=missing_data, index=missing_time)
    series.index.name = 'time'
    mda = series.to_xarray()
    mda.name = da.name
    new_data = xr.concat([mda, da], 'time')
    new_data = new_data.sortby('time')
    # copy attrs:
    new_data.attrs = da.attrs
    new_data.attrs['description'] = 'data was resampled to 5 mins from '\
                                    + 'original 10 mins and then '\
                                    + resample_method + ', missing data was '\
                                    'replaced by using ' + clim_period \
                                    + ' mean and hourly signal.'
    # put new_data and missing data into a dataset:
    dataset = new_data.to_dataset(name=new_data.name)
    dataset[new_data.name + '_missing'] = mda.rename({'time': 'missing_time'})
    # resample to 5min with resample_method: (interpolate is very slow)
    print('resampling to 5 mins using {}'.format(resample_method))
    # don't resample the missing data:
    dataset = dataset.resample(time='5min').ffill()
    print('done!')
    return dataset


def fix_T_height(path, geo_df, lapse_rate=6.5):
    """fix the temperature diffrence due to different height between the IMS
    and GPS stations"""
    # use lapse rate of 6.5 K/km = 6.5e-3 K/m
    import xarray as xr
    lr = 1e-3 * lapse_rate  # convert to K/m
    Tds = xr.open_dataset(path / 'IMS_TD_israeli_for_gps.nc')
    stations = [x for x in Tds.data_vars.keys() if 'missing' not in x]
    ds_list = []
    for st in stations:
        try:
            alt_diff = geo_df.loc[st, 'alt_diff']
            # correction is lapse_rate in K/m times alt_diff in meteres
            # if alt_diff is positive, T should be higher and vice versa
            Tds[st].attrs['description'] += ' The data was fixed using {} K/km '\
                                            'lapse rate bc the difference'\
                                            ' between the temperature station '\
                                            'and the gps station is {}'\
                                            .format(lapse_rate, alt_diff)
            Tds[st].attrs['lapse_rate_fix'] = lapse_rate
            ds_list.append(Tds[st] + lr * alt_diff)
        except KeyError:
            print('{} station not found in gps data'.format(st))
        continue
    ds = xr.merge(ds_list)
    # copy attrs:
    for da in ds:
        ds[da].attrs = Tds[da].attrs
    return ds


def produce_geo_df(gis_path=gis_path):
    print('getting IMS temperature stations metadata...')
    ims = produce_geo_ims(gis_path, filename='IMS_10mins_meta_data.xlsx',
                          closed_stations=False, plot=False)
    print('getting GPS stations ZWD from garner...')
    gps = produce_geo_gps_stations(gis_path, file='stations.txt', plot=False)
    print('combining temperature and GPS stations into one dataframe...')
    geo_df = get_minimum_distance(ims, gps, gis_path, plot=False)
    print('Done!')
    return geo_df


def produce_single_station_IPW(zwd, Tds, Tcoeffs=None, k2=22.1, k3=3.776e5):
    """input is zwd from gipsy or garner, Tds is the temperature of the
    station, Tcoeffs is the Ts-Tm relationsship dataarray"""
    import xarray as xr
    zwd.load()
    Tds.load()
    hours = dict(zip([12, 0], ['noon', 'midnight']))
    if 'season' in Tcoeffs.dims:
        seasons = Tcoeffs.season.values.tolist()
    if 'any_cld' in Tcoeffs.dims:
        any_clds = Tcoeffs.any_cld.values.tolist()
    if Tcoeffs is None:
        # Bevis 1992 relationship:
        Tcoeffs = xr.DataArray([0.72, 70.0], dims=['parameter'])
        Tcoeffs['parameter'] = ['slope', 'intercept']
    if len(Tcoeffs.dims) == 1 and 'parameter' in Tcoeffs.dims:
        print('Found whole data Ts-Tm relationship.')
        Tmul = Tcoeffs.sel(parameter='slope').values.item()
        Toff = Tcoeffs.sel(parameter='intercept').values.item()
        kappa_ds = kappa(Tds, Tmul, Toff, k2, k3)
        ipw = kappa_ds * zwd
        ipw.name = zwd.name
        kappa_dict = dict(zip(['T_multiplier', 'T_offset', 'k2', 'k3'],
                              [Tmul, Toff, k2, k3]))
        for k, v in kappa_dict.items():
            ipw.attrs[k] = v
        ipw = ipw.rename({'zwd': 'ipw'})
        ipw.attrs['name'] = 'IPW'
        ipw.attrs['long_name'] = 'Integrated Precipitable Water'
        ipw.attrs['units'] = 'kg / m^2'
        print('Done!')
    elif len(Tcoeffs.dims) == 2 and set(Tcoeffs.dims) == set(['hour', 'parameter']):
        print('Found hour Ts-Tm relationship slice.')
    elif len(Tcoeffs.dims) == 2 and set(Tcoeffs.dims) == set(['season', 'parameter']):
        print('Found season Ts-Tm relationship slice.')
    elif len(Tcoeffs.dims) == 2 and set(Tcoeffs.dims) == set(['any_cld', 'parameter']):
        print('Found clouds Ts-Tm relationship slice.')
    elif (len(Tcoeffs.dims) == 3 and set(Tcoeffs.dims) ==
          set(['any_cld', 'season', 'parameter'])):
        print('Found clouds and season Ts-Tm relationship slice.')
    elif (len(Tcoeffs.dims) == 3 and set(Tcoeffs.dims) ==
          set(['any_cld', 'hour', 'parameter'])):
        print('Found clouds and hour Ts-Tm relationship slice.')
        # no way to find clouds in historical data ??
        kappa_list = []
        Tcoeffs_list = []
        Tcoeffs_vals = []
        for hr_num in hours.keys():
            for any_cld in any_clds:
                print('working on any_cld {}, hour {}'.format(
                        any_cld, hours[hr_num]))
                Tmul = Tcoeffs.sel(any_cld=any_cld, hour=hours[hr_num],
                                   parameter='slope')
                Toff = Tcoeffs.sel(any_cld=any_cld, hour=hours[hr_num],
                                   parameter='intercept')
                sliced = Tds.where(Tds['time.season'] == season).dropna(
                        'time').where(Tds['time.hour'] == hr_num).dropna('time')
                kappa_part = kappa(sliced)
                kappa_keys = ['T_multiplier', 'T_offset', 'k2', 'k3']
                kappa_keys = [x + '_' + season + '_' + hours[hr_num] for x in
                              kappa_keys]
                Tcoeffs_list.append(kappa_keys)
                Tcoeffs_vals.append([Tmul.values.item(), Toff.values.item(),
                                     k2, k3])
                kappa_list.append(kappa_part)
    elif (len(Tcoeffs.dims) == 3 and set(Tcoeffs.dims) ==
          set(['hour', 'season', 'parameter'])):
        print('Found hour and season Ts-Tm relationship slice.')
        kappa_list = []
        Tcoeffs_list = []
        Tcoeffs_vals = []
        for hr_num in hours.keys():
            for season in seasons:
                print('working on season {}, hour {}'.format(
                        season, hours[hr_num]))
                Tmul = Tcoeffs.sel(season=season, hour=hours[hr_num],
                                   parameter='slope')
                Toff = Tcoeffs.sel(season=season, hour=hours[hr_num],
                                   parameter='intercept')
                sliced = Tds.where(Tds['time.season'] == season).dropna(
                        'time').where(Tds['time.hour'] == hr_num).dropna('time')
                kappa_part = kappa(sliced)
                kappa_keys = ['T_multiplier', 'T_offset', 'k2', 'k3']
                kappa_keys = [x + '_' + season + '_' + hours[hr_num] for x in
                              kappa_keys]
                Tcoeffs_list.append(kappa_keys)
                Tcoeffs_vals.append([Tmul.values.item(), Toff.values.item(),
                                     k2, k3])
                kappa_list.append(kappa_part)
    kappa_ds = xr.concat(kappa_list, 'time')
    ipw = kappa_ds * zwd
    ipw.name = zwd.name
    kappa_dict = dict(zip([item for sublist in Tcoeffs_list for item in sublist],
                          [item for sublist in Tcoeffs_vals for item in sublist]))
    for k, v in kappa_dict.items():
        ipw.attrs[k] = v
    ipw = ipw.rename({'zwd': 'ipw'})
    ipw.attrs['name'] = 'IPW'
    ipw.attrs['long_name'] = 'Integrated Precipitable Water'
    ipw.attrs['units'] = 'kg / m^2'
    print('Done!')
    ipw = ipw.reset_coords(drop=True)
    return ipw


def produce_IPW_field(geo_df, ims_path=ims_path, gps_path=garner_path,
                      savepath=None, lapse_rate=6.5, Tmul=0.72,
                      T_offset=70.2, k2=22.1, k3=3.776e5, station=None,
                      plot=True, hist=True):
    import xarray as xr
    """produce IPW field from zwd and T, for one station or all stations"""
    # IPW = kappa[kg/m^3] * ZWD[cm]
    print('fixing T data for height diffrences with {} K/km lapse rate'.format(
            lapse_rate))
    Tds = fix_T_height(ims_path, geo_df, lapse_rate)
    print(
        'producing kappa multiplier to T data with k2: {}, and k3: {}.'.format(
            k2,
            k3))
    Tds = kappa(Tds, Tmul, T_offset, k2, k3)
    kappa_dict = dict(zip(['T_multiplier', 'T_offset', 'k2', 'k3'],
                          [Tmul, T_offset, k2, k3]))
    garner_zwd = xr.open_dataset(gps_path /
                                 'garner_israeli_stations_filtered.nc')
    if station is not None:
        print('producing IPW field for station: {}'.format(station))
        try:
            ipw = Tds[station] * garner_zwd[station.upper()]
            ipw.name = station.upper()
            ipw.attrs['gps_lat'] = geo_df.loc[station, 'gps_lat']
            ipw.attrs['gps_lon'] = geo_df.loc[station, 'gps_lon']
            ipw.attrs['gps_alt'] = geo_df.loc[station, 'gps_alt']
            for k, v in kappa_dict.items():
                ipw.attrs[k] = v
        except KeyError:
            raise('{} station not found in garner gps data'.format(station))
        ds = ipw.to_dataset(name=ipw.name)
        ds = ds.rename({'zwd': 'ipw'})
        ds['ipw'].attrs['name'] = 'IPW'
        ds['ipw'].attrs['long_name'] = 'Integrated Precipitable Water'
        ds['ipw'].attrs['units'] = 'kg / m^2'
        print('Done!')
    else:
        print('producing IPW fields:')
        ipw_list = []
        for st in Tds:
            try:
                # IPW = kappa(T) * Zenith Wet Delay:
                ipw = Tds[st] * garner_zwd[st.upper()]
                ipw.name = st.upper()
                ipw.attrs['gps_lat'] = geo_df.loc[st, 'gps_lat']
                ipw.attrs['gps_lon'] = geo_df.loc[st, 'gps_lon']
                ipw.attrs['gps_alt'] = geo_df.loc[st, 'gps_alt']
                for k, v in kappa_dict.items():
                    ipw.attrs[k] = v
                ipw_list.append(ipw)
            except KeyError:
                print('{} station not found in garner gps data'.format(st))
            continue
        ds = xr.merge(ipw_list)
        ds = ds.rename({'zwd': 'ipw'})
        ds['ipw'].attrs['name'] = 'IPW'
        ds['ipw'].attrs['long_name'] = 'Integrated Precipitable Water'
        ds['ipw'].attrs['units'] = 'kg / m^2'
        print('Done!')
        if savepath is not None:
            filename = 'IPW_israeli_from_gps.nc'
            print('saving {} to {}'.format(filename, savepath))
            comp = dict(zlib=True, complevel=9)  # best compression
            encoding = {var: comp for var in ds.data_vars}
            ds.to_netcdf(savepath / filename, 'w', encoding=encoding)
            print('Done!')
        if plot:
            ds.sel(ipw='value').to_array(dim='station').sortby('station').plot(
                x='time',
                col='station',
                col_wrap=4,
                figsize=(15, 8))
        if hist:
            ds.sel(ipw='value').to_dataframe().hist(bins=100, grid=False,
                                                    figsize=(15, 8))
    return ds


def check_Tm_func(Tmul_num=10, Ts_num=6, Toff_num=15):
    """ check and plot Tm function to understand which bounds to put on Tmul
    Toff optimization, found:Tmul (0,1), Toff (0,150)"""
    import xarray as xr
    Ts = np.linspace(-10, 50, Ts_num) + 273.15
    Toff = np.linspace(-300, 300, Toff_num)
    Tmul = np.linspace(-3, 3, Tmul_num)
    Tm = np.empty((Ts_num, Tmul_num, Toff_num))
    for i in range(Ts_num):
        for j in range(Tmul_num):
            for k in range(Toff_num):
                Tm[i, j, k] = Ts[i] * Tmul[j] + Toff[k]
    da = xr.DataArray(Tm, dims=['Ts', 'Tmul', 'Toff'])
    da['Ts'] = Ts
    da['Tmul'] = Tmul
    da['Toff'] = Toff
    da.plot.pcolormesh(col='Ts', col_wrap=3)
    return da


def kappa(T, Tmul=0.72, T_offset=70.2, k2=22.1, k3=3.776e5):
    """T in celsious, anton says k2=22.1 is better"""
    # original k2=17.0 bevis 1992 etal.
    # [k2] = K / mbar, [k3] = K^2 / mbar
    # 100 Pa = 1 mbar
    Tm = (273.15 + T) * Tmul + T_offset  # K
    Rv = 461.52  # [Rv] = J / (kg * K) = (Pa * m^3) / (kg * K)
    # (1e-2 mbar * m^3) / (kg * K)
    k = 1e-6 * (k3 / Tm + k2) * Rv
    k = 1.0 / k  # [k] = 100 * kg / m^3 =  kg/ (m^2 * cm)
    # 1 kg/m^2 IPW = 1 mm PW
    return k


def minimize_kappa_tela_sound(sound_path=sound_path, gps=garner_path,
                              ims_path=ims_path, station='TELA', bounds=None,
                              x0=None, times=None, season=None):
    from skopt import gp_minimize
    import xarray as xr
    from sklearn.metrics import mean_squared_error
    import numpy as np
    from aux_gps import dim_intersection

    def func_to_min(x):
        Tmul = x[0]
        Toff = x[1]
        # k2 = x[2]
        # Ta = Tmul * (Ts + 273.15) + Toff
        Ts_k = Ts + 273.15
        Ta = Tmul * (Ts_k) + Toff
        added_loss = np.mean((np.where(Ta > Ts_k, 1.0, 0.0))) * 100.0
        k = kappa(Ts, Tmul=Tmul, T_offset=Toff)  # , k2=k2)
        res = sound - k * zwd_gps
        rmse = np.sqrt(mean_squared_error(sound, k * zwd_gps))
        loss = np.abs(np.mean(res)) + rmse
        print('loss:{}, added_loss:{}'.format(loss, added_loss))
        loss += added_loss
        return loss

    # load gerner zwd data:
    zwd_gps = xr.open_dataset(gps / 'garner_israeli_stations_filtered.nc')
    zwd_gps = zwd_gps[station].sel(zwd='value')
    zwd_gps.load()
    # load bet dagan sounding data:
    sound = xr.open_dataarray(sound_path / 'PW_bet_dagan_soundings.nc')
    sound = sound.where(sound > 0, drop=True)
    sound.load()
    # load surface temperature data in C:
    Tds = xr.open_dataset(ims_path / 'IMS_TD_israeli_for_gps.nc')
    Ts = Tds[station.lower()]
    Ts.load()
    # intersect the datetimes:
    new_time = dim_intersection([zwd_gps, sound, Ts], 'time')
    zwd_gps = zwd_gps.sel(time=new_time)
    sound = sound.sel(time=new_time)
    Ts = Ts.sel(time=new_time)
    if times is not None:
        zwd_gps = zwd_gps.sel(time=slice(times[0], times[1]))
        sound = sound.sel(time=slice(times[0], times[1]))
        Ts = Ts.sel(time=slice(times[0], times[1]))
    if season is not None:
        print('Minimizing for season : {}'.format(season))
        zwd_gps = zwd_gps.sel(time=zwd_gps['time.season'] == season)
        sound = sound.sel(time=sound['time.season'] == season)
        Ts = Ts.sel(time=Ts['time.season'] == season)

    zwd_gps = zwd_gps.values
    sound = sound.values
    Ts = Ts.values
    if bounds is None:
        # default boundries:
        bounds = {}
        bounds['Tmul'] = (0.1, 1.0)
        bounds['Toff'] = (0.0, 110.0)
        # bounds['k2'] = (1.0, 150.0)
    if x0 is None:
        # default x0
        x0 = {}
        x0['Tmul'] = 0.5
        x0['Toff'] = 90.0
        # x0['k2'] = 17.0
    if isinstance(x0, dict):
        x0_list = [x0.get('Tmul'), x0.get('Toff')]  # , x0.get('k2')]
        print('Running minimization with initial X:')
        for k, v in x0.items():
            print(k + ': ', v)
    if not x0:
        x0_list = None
        print('Running minimization with NO initial X...')
    print('Running minimization with the following bounds:')
    for k, v in bounds.items():
        print(k + ': ', v)
    bounds_list = [bounds.get('Tmul'), bounds.get('Toff')]  # , bounds.get('k2')]
    res = gp_minimize(func_to_min, dimensions=bounds_list,
                      x0=x0_list, n_jobs=-1, random_state=42,
                      verbose=False)
    return res


def check_anton_tela_station(anton_path, ims_path=ims_path):
    import pandas as pd
    from datetime import datetime, timedelta
    from pandas.errors import EmptyDataError
    import xarray as xr
    df_list = []
    for file in anton_path.glob('tela*.txt'):
        day = int(''.join([x for x in file.as_posix() if x.isdigit()]))
        year = 2015
        dt = pd.to_datetime(datetime(year, 1, 1) + timedelta(day - 1))
        try:
            df = pd.read_csv(file, index_col=0, delim_whitespace=True,
                             header=None)
            df.columns = ['zwd']
            df.index = dt + pd.to_timedelta(df.index * 60, unit='min')
            df_list.append(df)
        except EmptyDataError:
            print('found empty file...')
            continue
    df_all = pd.concat(df_list)
    df_all = df_all.sort_index()
    df_all.index.name = 'time'
    ds = df_all.to_xarray()
    ds = ds.rename({'zwd': 'TELA'})
    Tds = xr.open_dataset(ims_path / 'IMS_TD_israeli_for_gps.nc')
    k = kappa(Tds.tela, k2=22.1)
    ds = k * ds
    return ds


def from_opt_to_comparison(result=None, times=None, bounds=None, x0=None,
                           season=None, Tmul=None, T_offset=None):
    """ call optimization and comapring alltogather. can run optimization
    separetly and plugin the result to compare"""
    if result is None:
        print('minimizing the hell out of the function!...')
        result = minimize_kappa_tela_sound(times=times, bounds=bounds, x0=x0,
                                           season=season)
    geo_df = produce_geo_df()
    if result:
        Tmul = result.x[0]
        T_offset = result.x[1]
    if Tmul is not None and T_offset is not None:
        # k2 = result.x[2]
        ipw = produce_IPW_field(geo_df, Tmul=Tmul, T_offset=T_offset,
                                plot=False, hist=False, station='tela')
        pw = compare_to_sounding(gps=ipw, times=times, season=season)
        pw.attrs['result from fitted model'] = result.x
    return pw, result


def compare_to_sounding(sound_path=sound_path, gps=garner_path, station='TELA',
                        times=None, season=None, hour=None):
    import xarray as xr
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import mean_squared_error
    from pathlib import Path
    sns.set_style('darkgrid')
    if isinstance(gps, Path):
        pw_gps = xr.open_dataset(gps / 'IPW_israeli_from_gps.nc')
    else:
        pw_gps = gps
    if [x for x in pw_gps.coords if x == 'ipw']:
        pw_gps = pw_gps[station].sel(ipw='value')
    else:
        pw_gps = pw_gps[station]
    pw_gps.load()
    sound = xr.open_dataarray(sound_path / 'PW_bet_dagan_soundings.nc')
    # drop 0 pw - not physical
    sound = sound.where(sound > 0, drop=True)
    sound.load()
    new_time = list(set(pw_gps.dropna('time').time.values).intersection(
        set(sound.dropna('time').time.values)))
    new_dt = sorted(pd.to_datetime(new_time))
    # selecting requires time...
    print('selecting intersected datetime...')
    pw_gps = pw_gps.sel(time=new_dt)
    sound = sound.sel(time=new_dt)
    pw = pw_gps.to_dataset(name=station).reset_coords(drop=True)
    pw['sound'] = sound
    pw['resid'] = pw['sound'] - pw[station]
    pw.load()
    print('Done!')
    if times is not None:
        pw = pw.sel(time=slice(times[0], times[1]))
    if season is not None:
        pw = pw.sel(time=pw['time.season'] == season)
    if hour is not None:
        pw = pw.sel(time=pw['time.hour'] == hour)
    fig, ax = plt.subplots(1, 2, figsize=(20, 4),
                           gridspec_kw={'width_ratios': [3, 1]})
    pw[[station, 'sound']].to_dataframe().plot(ax=ax[0], style='.')
    sns.distplot(
        pw['resid'].values,
        bins=100,
        color='c',
        label='residuals',
        ax=ax[1])
    # pw['resid'].plot.hist(bins=100, color='c', edgecolor='k', alpha=0.65,
    #                      ax=ax[1])
    rmean = pw['resid'].mean().values
    rstd = pw['resid'].std().values
    rmedian = pw['resid'].median().values
    rmse = np.sqrt(mean_squared_error(pw['sound'], pw[station]))
    plt.axvline(rmean, color='r', linestyle='dashed', linewidth=1)
    # plt.axvline(rmedian, color='b', linestyle='dashed', linewidth=1)
    _, max_ = plt.ylim()
    plt.text(rmean + rmean / 10, max_ - max_ / 10,
             'Mean: {:.2f}, RMSE: {:.2f}'.format(rmean, rmse))
    fig.tight_layout()
    if season is None:
        pw['season'] = pw['time.season']
        pw['hour'] = pw['time.hour'].astype(str)
        pw['hour'] = pw.hour.where(pw.hour != '12', 'noon')
        pw['hour'] = pw.hour.where(pw.hour != '0', 'midnight')
        df = pw.to_dataframe()
    #    g = sns.relplot(
    #        data=df,
    #        x='sound',
    #        y='TELA',
    #        col='season',
    #        hue='hour',
    #        kind='scatter',
    #        style='season')
    #    if times is not None:
    #        plt.subplots_adjust(top=0.85)
    #        g.fig.suptitle('Time: ' + times[0] + ' to ' + times[1], y=0.98)
        h_order = ['noon', 'midnight']
        s_order = ['DJF', 'JJA', 'SON', 'MAM']
        g = sns.lmplot(
            data=df,
            x='sound',
            y='TELA',
            col='season',
            hue='season',
            row='hour',
            row_order=h_order,
            col_order=s_order)
        g.set(ylim=(0, 50), xlim=(0, 50))
        if times is not None:
            plt.subplots_adjust(top=0.9)
            g.fig.suptitle('Time: ' + times[0] + ' to ' + times[1], y=0.98)
        g = sns.FacetGrid(data=df, col='season', hue='season', row='hour',
                          row_order=h_order, col_order=s_order)
        g.fig.set_size_inches(15, 8)
        g = (g.map(sns.distplot, "resid"))
        rmeans = []
        rmses = []
        for hour in h_order:
            for season in s_order:
                sliced_pw = pw.sel(
                    time=pw['time.season'] == season).where(
                    pw.hour != hour).dropna('time')
                rmses.append(
                    np.sqrt(
                        mean_squared_error(
                            sliced_pw['sound'],
                            sliced_pw[station])))
                rmeans.append(sliced_pw['resid'].mean().values)
        for i, ax in enumerate(g.axes.flat):
            ax.axvline(rmeans[i], color='k', linestyle='dashed', linewidth=1)
            _, max_ = ax.get_ylim()
            ax.text(rmeans[i] + rmeans[i] / 10, max_ - max_ / 10,
                    'Mean: {:.2f}, RMSE: {:.2f}'.format(rmeans[i], rmses[i]))
        # g.set(xlim=(-5, 5))
        if times is not None:
            plt.subplots_adjust(top=0.9)
            g.fig.suptitle('Time: ' + times[0] + ' to ' + times[1], y=0.98)
    # maybe month ?
    # plt.text(rmedian + rmedian / 10, max_ - max_ / 10,
    #          'Mean: {:.2f}'.format(rmedian))
    return pw


def linear_T_from_sounding(sound_path=sound_path, categories=None):
    import xarray as xr
    ds = xr.open_dataset(sound_path / 'bet_dagan_sounding_pw_Ts_Tk_with_clouds.nc')
    ds = ds.reset_coords(drop=True)
    s_order = ['DJF', 'JJA', 'SON', 'MAM']
    h_order = ['noon', 'midnight']
    cld_order = [0, 1]
    if categories is None:
        results = formulate_plot(ds)
    if categories is not None:
        if not isinstance(categories, list):
            categories = [categories]
        if set(categories + ['season', 'hour', 'clouds']) != set(['season',
                                                                  'hour',
                                                                  'clouds']):
            raise ValueError('choices for categories are: season, hour, clouds')
        if len(categories) == 1:
            if 'season' in categories:
                dd = {'season': s_order}
            elif 'hour' in categories:
                dd = {'hour': h_order}
            elif 'clouds' in categories:
                dd = {'any_cld': cld_order}
        elif len(categories) == 2:
            if 'season' in categories and 'hour' in categories:
                dd = {'hour': h_order, 'season': s_order}
            elif 'season' in categories and 'clouds' in categories:
                dd = {'any_cld': cld_order, 'season': s_order}
            elif 'clouds' in categories and 'hour' in categories:
                dd = {'hour': h_order, 'any_cld': cld_order}
        elif len(categories) == 3:
            if 'season' in categories and 'hour' in categories and 'clouds' in categories:
                dd = {'hour': h_order, 'any_cld': cld_order, 'season': s_order}
        results = formulate_plot(ds, dd)
    return results


def formulate_plot(ds, dim_dict=None):
    import xarray as xr
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import mean_squared_error
    sns.set_style('darkgrid')
    if dim_dict is None:
        fig, axes = plt.subplots(1, 2, figsize=(10, 7))
        fig.suptitle(
                    'Water vapor weighted mean atmospheric temperature vs. bet dagan sounding station surface temperature')
        [a, b] = np.polyfit(ds.ts.values, ds.tm.values, 1)
        result = np.empty((2))
        result[0] = a
        result[1] = b
        # sns.regplot(ds.ts.values, ds.tm.values, ax=axes[0])
        df = ds.ts.dropna('time').to_dataframe()
        df['tm'] = ds.tm.dropna('time')
        df['clouds'] = ds.any_cld.dropna('time')
        g = sns.scatterplot(data=df, x='ts', y='tm', hue='clouds', marker='.', s=100,
                            ax=axes[0])
        g.legend(loc='best')
        # axes[0].scatter(x=ds.ts.values, y=ds.tm.values, marker='.', s=10)
        linex = np.array([ds.ts.min().item(), ds.ts.max().item()])
        liney = a * linex + b
        axes[0].plot(linex, liney, c='r')
        min_, max_ = axes[0].get_ylim()
        axes[0].text(0.01, 0.9, 'a: {:.2f}, b: {:.2f}'.format(a, b),
                     transform=axes[0].transAxes, color='black', fontsize=12)
        axes[0].text(0.1, 0.85, 'n={}'.format(len(ds.ts.values)),
                     verticalalignment='top', horizontalalignment='center',
                     transform=axes[0].transAxes, color='green', fontsize=12)
        axes[0].set_xlabel('Ts [K]')
        axes[0].set_ylabel('Tm [K]')
        resid = ds.tm.values - ds.ts.values * a - b
        sns.distplot(resid, bins=25, color='c', label='residuals', ax=axes[1])
        rmean = np.mean(resid)
        rmse = np.sqrt(mean_squared_error(ds.tm.values, ds.ts.values * a + b))
        _, max_ = axes[1].get_ylim()
        axes[1].text(rmean + rmean / 10, max_ - max_ / 10,
                     'Mean: {:.2f}, RMSE: {:.2f}'.format(rmean, rmse))
        axes[1].axvline(rmean, color='r', linestyle='dashed', linewidth=1)
        axes[1].set_xlabel('Residuals [K]')
        fig.tight_layout()
        results = xr.DataArray(result, dims=['parameter'])
        results['parameter'] = ['slope', 'intercept']
    elif dim_dict is not None:
        keys = [x for x in dim_dict.keys()]
        size = len(keys)
        if size == 1:
            key = keys[0]
            other_keys = [*set(['any_cld', 'hour', 'season']).difference([key])]
            vals = dim_dict[key]
            result = np.empty((len(vals), 2))
            residuals = []
            rmses = []
            fig, axes = plt.subplots(1, len(vals), sharey=True, sharex=True,
                                     figsize=(15, 8))
            for i, val in enumerate(vals):
                x = ds.ts.where(ds[key] == val).dropna('time')
                y = ds.tm.where(ds[key] == val).dropna('time')
                other_val0 = ds[other_keys[0]].where(ds[key] == val).dropna('time')
                other_val1 = ds[other_keys[1]].where(ds[key] == val).dropna('time')
                [tmul, toff] = np.polyfit(x.values, y.values, 1)
                result[i, 0] = tmul
                result[i, 1] = toff
                new_tm = tmul * x.values + toff
                resid = new_tm - y.values
                rmses.append(np.sqrt(mean_squared_error(y.values, new_tm)))
                residuals.append(resid)
                axes[i].text(0.15, 0.85, 'n={}'.format(len(x.values)),
                             verticalalignment='top',
                             horizontalalignment='center',
                             transform=axes[i].transAxes, color='green',
                             fontsize=12)
                df = x.to_dataframe()
                df['tm'] = y
                df[other_keys[0]] = other_val0
                df[other_keys[1]] = other_val1
                g = sns.scatterplot(data=df, x='ts', y='tm', marker='.', s=100,
                                    ax=axes[i], hue=other_keys[0],
                                    style=other_keys[1])
                g.legend(loc='upper right')
                # axes[i, j].scatter(x=x.values, y=y.values, marker='.', s=10)
                axes[i].set_title('{}:{}'.format(key, val))
                linex = np.array([x.min().item(), x.max().item()])
                liney = tmul * linex + toff
                axes[i].plot(linex, liney, c='r')
                axes[i].plot(x.values, x.values, c='k', alpha=0.2)
                min_, max_ = axes[i].get_ylim()
                axes[i].text(0.015, 0.9, 'a: {:.2f}, b: {:.2f}'.format(
                             tmul, toff), transform=axes[i].transAxes,
                             color='black', fontsize=12)
                axes[i].set_xlabel('Ts [K]')
                axes[i].set_ylabel('Tm [K]')
                fig.tight_layout()
            results = xr.DataArray(result, dims=[key, 'parameter'])
            results['parameter'] = ['slope', 'intercept']
            results[key] = vals
        elif size == 2:
            other_keys = [*set(['any_cld', 'hour', 'season']).difference(keys)]
            vals = [dim_dict[key] for key in dim_dict.keys()]
            result = np.empty((len(vals[0]), len(vals[1]), 2))
            residuals = []
            rmses = []
            fig, axes = plt.subplots(len(vals[0]), len(vals[1]), sharey=True,
                                     sharex=True, figsize=(15, 8))
            for i, val0 in enumerate(vals[0]):
                for j, val1 in enumerate(vals[1]):
                    x = ds.ts.where(ds[keys[0]] == val0).dropna(
                            'time').where(ds[keys[1]] == val1).dropna('time')
                    y = ds.tm.where(ds[keys[0]] == val0).dropna(
                            'time').where(ds[keys[1]] == val1).dropna('time')
                    other_val = ds[other_keys[0]].where(ds[keys[0]] == val0).dropna(
                            'time').where(ds[keys[1]] == val1).dropna('time')
                    [tmul, toff] = np.polyfit(x.values, y.values, 1)
                    result[i, j, 0] = tmul
                    result[i, j, 1] = toff
                    new_tm = tmul * x.values + toff
                    resid = new_tm - y.values
                    rmses.append(np.sqrt(mean_squared_error(y.values, new_tm)))
                    residuals.append(resid)
                    axes[i, j].text(0.15, 0.85, 'n={}'.format(len(x.values)),
                                    verticalalignment='top',
                                    horizontalalignment='center',
                                    transform=axes[i, j].transAxes,
                                    color='green', fontsize=12)
                    df = x.to_dataframe()
                    df['tm'] = y
                    df[other_keys[0]] = other_val
                    g = sns.scatterplot(data=df, x='ts', y='tm', marker='.',
                                        s=100, ax=axes[i, j],
                                        hue=other_keys[0])
                    g.legend(loc='upper right')
                    # axes[i, j].scatter(x=x.values, y=y.values, marker='.', s=10)
                    # axes[i, j].set_title('{}:{}'.format(key, val))
                    linex = np.array([x.min().item(), x.max().item()])
                    liney = tmul * linex + toff
                    axes[i, j].plot(linex, liney, c='r')
                    axes[i, j].plot(x.values, x.values, c='k', alpha=0.2)
                    min_, max_ = axes[i, j].get_ylim()
                    axes[i, j].text(0.015, 0.9, 'a: {:.2f}, b: {:.2f}'.format(
                                 tmul, toff), transform=axes[i, j].transAxes,
                                 color='black', fontsize=12)
                    axes[i, j].set_xlabel('Ts [K]')
                    axes[i, j].set_ylabel('Tm [K]')
                    axes[i, j].set_title('{}:{}, {}:{}'.format(keys[0], val0,
                                                               keys[1], val1))
                    fig.tight_layout()
            results = xr.DataArray(result, dims=keys + ['parameter'])
            results['parameter'] = ['slope', 'intercept']
            results[keys[0]] = vals[0]
            results[keys[1]] = vals[1]
    return results


def analyze_sounding_and_formulate(sound_path=sound_path):
    import xarray as xr
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import mean_squared_error
    sns.set_style('darkgrid')
    # ds = xr.open_dataset(sound_path / 'bet_dagan_sounding_pw_Ts_Tk1.nc')
    ds = xr.open_dataset(sound_path / 'bet_dagan_sounding_pw_Ts_Tk_with_clouds.nc')
    ds = ds.reset_coords(drop=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 7))
    fig.suptitle(
        'Water vapor weighted mean atmospheric temperature vs. bet dagan sounding station surface temperature')
    [a, b] = np.polyfit(ds.ts.values, ds.tm.values, 1)
    # sns.regplot(ds.ts.values, ds.tm.values, ax=axes[0])
    df = ds.ts.dropna('time').to_dataframe()
    df['tm'] = ds.tm.dropna('time')
    df['clouds'] = ds.any_cld.dropna('time')
    g = sns.scatterplot(data=df, x='ts', y='tm', hue='clouds', marker='.', s=100,
                        ax=axes[0])
    g.legend(loc='best')
    # axes[0].scatter(x=ds.ts.values, y=ds.tm.values, marker='.', s=10)
    linex = np.array([ds.ts.min().item(), ds.ts.max().item()])
    liney = a * linex + b
    axes[0].plot(linex, liney, c='r')
    min_, max_ = axes[0].get_ylim()
    axes[0].text(
        0.01,
        0.9,
        'a: {:.2f}, b: {:.2f}'.format(
            a,
            b),
        transform=axes[0].transAxes,
        color='black',
        fontsize=12)
    axes[0].text(0.1,
                 0.85,
                 'n={}'.format(len(ds.ts.values)),
                 verticalalignment='top',
                 horizontalalignment='center',
                 transform=axes[0].transAxes,
                 color='green',
                 fontsize=12)
    axes[0].set_xlabel('Ts [K]')
    axes[0].set_ylabel('Tm [K]')
    resid = ds.tm.values - ds.ts.values * a - b
    sns.distplot(resid, bins=25, color='c', label='residuals', ax=axes[1])
    rmean = np.mean(resid)
    rmse = np.sqrt(mean_squared_error(ds.tm.values, ds.ts.values * a + b))
    _, max_ = axes[1].get_ylim()
    axes[1].text(rmean + rmean / 10, max_ - max_ / 10,
                 'Mean: {:.2f}, RMSE: {:.2f}'.format(rmean, rmse))
    axes[1].axvline(rmean, color='r', linestyle='dashed', linewidth=1)
    axes[1].set_xlabel('Residuals [K]')
    fig.tight_layout()
    # plot of just hours:
    h_order = ['noon', 'midnight']
    result = np.empty((len(h_order), 2))
    residuals = []
    rmses = []
    fig, axes = plt.subplots(1, 2, sharey=True, sharex=True, figsize=(8, 6))
    for i, hour in enumerate(h_order):
        x = ds.ts.where(ds.hour == hour).dropna('time')
        y = ds.tm.where(ds.hour == hour).dropna('time')
        cld = ds.any_cld.where(ds.hour == hour).dropna('time')
        [tmul, toff] = np.polyfit(x.values, y.values, 1)
        result[i, 0] = tmul
        result[i, 1] = toff
        new_tm = tmul * x.values + toff
        resid = new_tm - y.values
        rmses.append(np.sqrt(mean_squared_error(y.values, new_tm)))
        residuals.append(resid)
        axes[i].text(0.15, 0.85, 'n={}'.format(len(x.values)),
                     verticalalignment='top', horizontalalignment='center',
                     transform=axes[i].transAxes, color='green', fontsize=12)
        df = x.to_dataframe()
        df['tm'] = y
        df['clouds'] = cld
        g = sns.scatterplot(data=df, x='ts', y='tm', hue='clouds',
                            marker='.', s=100, ax=axes[i])
        g.legend(loc='upper right')
        # axes[i, j].scatter(x=x.values, y=y.values, marker='.', s=10)
        axes[i].set_title('hour:{}'.format(hour))
        linex = np.array([x.min().item(), x.max().item()])
        liney = tmul * linex + toff
        axes[i].plot(linex, liney, c='r')
        axes[i].plot(x.values, x.values, c='k', alpha=0.2)
        min_, max_ = axes[i].get_ylim()
        axes[i].text(0.015, 0.9, 'a: {:.2f}, b: {:.2f}'.format(
                     tmul, toff), transform=axes[i].transAxes, color='black',
                     fontsize=12)
        axes[i].set_xlabel('Ts [K]')
        axes[i].set_ylabel('Tm [K]')
    s_order = ['DJF', 'JJA', 'SON', 'MAM']
    # plot of hours and seasons:
#    Tmul = []
#    Toff = []
    residuals = []
    rmses = []
    result = np.empty((len(h_order), len(s_order), 2))
    fig, axes = plt.subplots(2, 4, sharey=True, sharex=True, figsize=(20, 15))
    for i, hour in enumerate(h_order):
        for j, season in enumerate(s_order):
            x = ds.ts.sel(time=ds['time.season'] == season).where(
                ds.hour == hour).dropna('time')
            y = ds.tm.sel(time=ds['time.season'] == season).where(
                ds.hour == hour).dropna('time')
            cld = ds.any_cld.sel(time=ds['time.season'] == season).where(
                ds.hour == hour).dropna('time')
            [tmul, toff] = np.polyfit(x.values, y.values, 1)
            result[i, j, 0] = tmul
            result[i, j, 1] = toff
            new_tm = tmul * x.values + toff
            resid = new_tm - y.values
            rmses.append(np.sqrt(mean_squared_error(y.values, new_tm)))
            residuals.append(resid)
            axes[i, j].text(0.15, 0.85, 'n={}'.format(len(x.values)),
                            verticalalignment='top', horizontalalignment='center',
                            transform=axes[i, j].transAxes, color='green',
                            fontsize=12)
            df = x.to_dataframe()
            df['tm'] = y
            df['clouds'] = cld
            g = sns.scatterplot(data=df, x='ts', y='tm', hue='clouds',
                                marker='.', s=100, ax=axes[i, j])
            g.legend(loc='upper right')
            # axes[i, j].scatter(x=x.values, y=y.values, marker='.', s=10)
            axes[i, j].set_title('season:{} ,hour:{}'.format(season, hour))
            linex = np.array([x.min().item(), x.max().item()])
            liney = tmul * linex + toff
            axes[i, j].plot(linex, liney, c='r')
            axes[i, j].plot(x.values, x.values, c='k', alpha=0.2)
            min_, max_ = axes[i, j].get_ylim()
            axes[i, j].text(0.015, 0.9, 'a: {:.2f}, b: {:.2f}'.format(
                tmul, toff), transform=axes[i, j].transAxes, color='black', fontsize=12)
            axes[i, j].set_xlabel('Ts [K]')
            axes[i, j].set_ylabel('Tm [K]')
#            Tmul.append(tmul)
#            Toff.append(toff)
    cnt = 0
    fig, axes = plt.subplots(2, 4, sharey=True, sharex=True, figsize=(20, 15))
    for i, hour in enumerate(h_order):
        for j, season in enumerate(s_order):
            sns.distplot(residuals[cnt], bins=25, color='c',
                         label='residuals', ax=axes[i, j])
            rmean = np.mean(residuals[cnt])
            _, max_ = axes[i, j].get_ylim()
            axes[i, j].text(rmean + rmean / 10, max_ - max_ / 10,
                            'Mean: {:.2f}, RMSE: {:.2f}'.format(rmean,
                                                                rmses[cnt]))
            axes[i, j].axvline(rmean, color='r', linestyle='dashed',
                               linewidth=1)
            axes[i, j].set_xlabel('Residuals [K]')
            axes[i, j].set_title('season:{} ,hour:{}'.format(season, hour))
            cnt += 1
    fig.tight_layout()
    results = xr.DataArray(result, dims=['hour', 'season', 'parameter'])
    results['hour'] = h_order
    results['season'] = s_order
    results['parameter'] = ['slope', 'intercept']
    results.attrs['all_data_slope'] = a
    results.attrs['all_data_intercept'] = b
    return results
