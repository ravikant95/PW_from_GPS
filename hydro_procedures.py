#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 21 14:08:43 2019

@author: ziskin
"""

from PW_paths import work_yuval
hydro_path = work_yuval / 'hydro'
gis_path = work_yuval / 'gis'

# TODO: slice hydro data for 1996-2019
# TODO: slice 4-5 stations around a 5-km radius from the GNSS stations
# TODO: hope for 1 continous hydro time series and work with it
# TODO: get each tide event (with threshold) and take a few days before(parameter)
# and mean this time-span of the PW time-series (or anomalies) and present it with graphs


def get_n_days_pw_hydro_event(pw_da, hs_id, ndays=5):
    # dims = (time, tide_start)
    return ds

def get_hydro_near_GNSS(radius=5.0, n=5, hydro_path=hydro_path,
                        gis_path=gis_path, plot=True):
    import pandas as pd
    import geopandas as gpd
    from pathlib import Path
    df = pd.read_csv(Path().cwd() / 'israeli_gnss_coords.txt',
                     delim_whitespace=True)
    df = df[['lon', 'lat']]
    gnss = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat),
                            crs={'init': 'epsg:4326'})
    gnss = gnss.to_crs({'init': 'epsg:2039'})
    hydro_meta = read_hydro_metadata(hydro_path, gis_path, plot=False)
    hydro_meta = hydro_meta.to_crs({'init': 'epsg:2039'})
    hydro_list = []
    for index, row in gnss.iterrows():
        hydro_meta[index] = hydro_meta.geometry.distance(row['geometry'])
        hydro_list.append(hydro_meta[hydro_meta[index] <= radius * 1000])
    sel_hydro = pd.concat(hydro_list)
    if plot:
        isr = gpd.read_file(gis_path / 'Israel_and_Yosh.shp')
        isr.crs = {'init': 'epsg:4326'}
        gnss = gnss.to_crs({'init': 'epsg:4326'})
        sel_hydro = sel_hydro.to_crs({'init': 'epsg:4326'})
        ax = isr.plot()
        gnss.plot(ax=ax, color='green', edgecolor='black')
        for x, y, label in zip(gnss.lon, gnss.lat, gnss.index):
            ax.annotate(label, xy=(x, y), xytext=(3, 3),
                        textcoords="offset points")
        sel_hydro.plot(ax=ax, color='red', edgecolor='black')
        for x, y, label in zip(sel_hydro.lon, sel_hydro.lat,
                               sel_hydro.id):
            ax.annotate(label, xy=(x, y), xytext=(3, 3),
                        textcoords="offset points")
    return sel_hydro


def read_hydro_metadata(path=hydro_path, gis_path=gis_path, plot=True):
    import pandas as pd
    import geopandas as gpd
    import xarray as xr
    df = pd.read_excel(hydro_path / 'hydro_stations_metadata.xlsx',
                       header=4)
    # drop last row:
    df.drop(df.tail(1).index, inplace=True)  # drop last n rows
    df.columns = [
        'id',
        'name',
        'active',
        'agency',
        'type',
        'X',
        'Y',
        'area']
    df.loc[:, 'active'][df['active'] == 'פעילה'] = 1
    df.loc[:, 'active'][df['active'] == 'לא פעילה'] = 0
    df.loc[:, 'active'][df['active'] == 'לא פעילה זמנית'] = 0
    df['active'] = df['active'].astype(float)
    df = df[~df.X.isnull()]
    df = df[~df.Y.isnull()]
    # now, geopandas part:
    geo_df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.X, df.Y),
                              crs={'init': 'epsg:2039'})
    # geo_df.crs = {'init': 'epsg:2039'}
    geo_df = geo_df.to_crs({'init': 'epsg:4326'})
    isr_dem = xr.open_rasterio(gis_path / 'israel_dem.tif')
    alt_list = []
    for index, row in geo_df.iterrows():
        lat = row.geometry.y
        lon = row.geometry.x
        alt = isr_dem.sel(band=1, x=lon, y=lat, method='nearest').values.item()
        alt_list.append(float(alt))
    geo_df['alt'] = alt_list
    geo_df['lat'] = geo_df.geometry.y
    geo_df['lon'] = geo_df.geometry.x
    isr = gpd.read_file(gis_path / 'Israel_and_Yosh.shp')
    isr.crs = {'init': 'epsg:4326'}
    geo_df = gpd.sjoin(geo_df, isr, op='within')
    if plot:
        ax = isr.plot()
        geo_df.plot(ax=ax, edgecolor='black', legend=True)
    return geo_df


def read_tides(path=hydro_path):
    from aux_gps import path_glob
    import pandas as pd
    import xarray as xr
    from aux_gps import get_unique_index
    files = path_glob(path, 'tide_report*.xlsx')
    df_list = []
    for file in files:
        df = pd.read_excel(file, header=4)
        df.drop(df.columns[len(df.columns) - 1], axis=1, inplace=True)
        df.columns = [
            'id',
            'name',
            'hydro_year',
            'tide_start_hour',
            'tide_start_date',
            'tide_end_hour',
            'tide_end_date',
            'tide_duration',
            'tide_max_hour',
            'tide_max_date',
            'max_height',
            'max_flow[m^3/sec]',
            'tide_vol[MCM]']
        df = df[~df.hydro_year.isnull()]
        df['id'] = df['id'].astype(int)
        df['tide_start'] = pd.to_datetime(
            df['tide_start_date'], dayfirst=True) + pd.to_timedelta(
            df['tide_start_hour'].add(':00'), unit='m', errors='coerce')
        df['tide_end'] = pd.to_datetime(
            df['tide_end_date'], dayfirst=True) + pd.to_timedelta(
            df['tide_end_hour'].add(':00'),
            unit='m',
            errors='coerce')
        df['tide_max'] = pd.to_datetime(
            df['tide_max_date'], dayfirst=True) + pd.to_timedelta(
            df['tide_max_hour'].add(':00'),
            unit='m',
            errors='coerce')
        df['tide_duration'] = pd.to_timedelta(
            df['tide_duration'] + ':00', unit='m', errors='coerce')
        df.loc[:,
               'max_flow[m^3/sec]'][df['max_flow[m^3/sec]'].str.contains('<',
                                                                         na=False)] = 0
        df.loc[:, 'tide_vol[MCM]'][df['tide_vol[MCM]'].str.contains(
            '<', na=False)] = 0
        df['max_flow[m^3/sec]'] = df['max_flow[m^3/sec]'].astype(float)
        df['tide_vol[MCM]'] = df['tide_vol[MCM]'].astype(float)
        to_drop = ['tide_start_hour', 'tide_start_date', 'tide_end_hour',
                   'tide_end_date', 'tide_max_hour', 'tide_max_date']
        df = df.drop(to_drop, axis=1)
        df_list.append(df)
    df = pd.concat(df_list)
    dfs = [x for _, x in df.groupby('id')]
    ds_list = []
    meta_df = read_hydro_metadata(path, gis_path, False)
    for df in dfs:
        st_id = df['id'].iloc[0]
        st_name = df['name'].iloc[0]
        print('proccessing station number: {}, {}'.format(st_id, st_name))
        meta = meta_df[meta_df['id'] == st_id]
        ds = xr.Dataset()
        df.set_index('tide_start', inplace=True)
        attrs = {}
        attrs['station_name'] = st_name
        if not meta.empty:
            attrs['lon'] = meta.lon.values.item()
            attrs['lat'] = meta.lat.values.item()
            attrs['alt'] = meta.alt.values.item()
            attrs['drainage_basin_area'] = meta.area.values.item()
            attrs['active'] = meta.active.values.item()
        attrs['units'] = 'm'
        max_height = df['max_height'].to_xarray()
        max_height.name = 'TS_{}_max_height'.format(st_id)
        max_height.attrs = attrs
        max_flow = df['max_flow[m^3/sec]'].to_xarray()
        max_flow.name = 'TS_{}_max_flow'.format(st_id)
        attrs['units'] = 'm^3/sec'
        max_flow.attrs = attrs
        attrs['units'] = 'MCM'
        tide_vol = df['tide_vol[MCM]'].to_xarray()
        tide_vol.name = 'TS_{}_tide_vol'.format(st_id)
        tide_vol.attrs = attrs
        attrs.pop('units')
#        tide_start = df['tide_start'].to_xarray()
#        tide_start.name = 'TS_{}_tide_start'.format(st_id)
#        tide_start.attrs = attrs
        tide_end = df['tide_end'].to_xarray()
        tide_end.name = 'TS_{}_tide_end'.format(st_id)
        tide_end.attrs = attrs
        tide_max = df['tide_max'].to_xarray()
        tide_max.name = 'TS_{}_tide_max'.format(st_id)
        tide_max.attrs = attrs
        ds['{}'.format(max_height.name)] = max_height
        ds['{}'.format(max_flow.name)] = max_flow
        ds['{}'.format(tide_vol.name)] = tide_vol
#         ds['{}'.format(tide_start.name)] = tide_start
        ds['{}'.format(tide_end.name)] = tide_end
        ds['{}'.format(tide_max.name)] = tide_max
        ds_list.append(ds)
    dsu = [get_unique_index(x, dim='tide_start') for x in ds_list]
    print('merging...')
    ds = xr.merge(dsu)
    filename = 'hydro_tides.nc'
    print('saving {} to {}'.format(filename, path))
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in ds.data_vars}
    ds.to_netcdf(path / filename, 'w', encoding=encoding)
    print('Done!')
    return ds


def text_process_hydrographs(path=hydro_path, gis_path=gis_path):
    from aux_gps import path_glob
    files = path_glob(path, 'hydro_flow*.txt')
    for i, file in enumerate(files):
        print(file)
        with open(file, 'r') as f:
            big_list = f.read().splitlines()
        # for small_list in big_list:
        #     flat_list = [item for sublist in l7 for item in sublist]
        big = [x.replace(',', ' ') for x in big_list]
        big = big[6:]
        big = [x.replace('\t', ',') for x in big]
        filename = 'hydro_graph_{}.txt'.format(i)
        with open(path / filename, 'w') as fs:
            for item in big:
                fs.write('{}\n'.format(item))
        print('{} saved to {}'.format(filename, path))
    return


def read_hydrographs(path=hydro_path):
    from aux_gps import path_glob
    import pandas as pd
    import xarray as xr
    from aux_gps import get_unique_index
    files = path_glob(path, 'hydro_graph*.txt')
    df_list = []
    for file in files:
        print(file)
        df = pd.read_csv(file, header=0, sep=',')
        df.columns = [
            'id',
            'name',
            'time',
            'tide_height[m]',
            'flow[m^3/sec]',
            'data_type',
            'flow_type',
            'record_type',
            'record_code']
        df['time'] = pd.to_datetime(df['time'], dayfirst=True)
        df['tide_height[m]'] = df['tide_height[m]'].astype(float)
        df['flow[m^3/sec]'] = df['flow[m^3/sec]'].astype(float)
        df.loc[:, 'data_type'][df['data_type'].str.contains(
            'מדודים', na=False)] = 'measured'
        df.loc[:, 'data_type'][df['data_type'].str.contains(
            'משוחזרים', na=False)] = 'reconstructed'
        df.loc[:, 'flow_type'][df['flow_type'].str.contains(
            'תקין', na=False)] = 'normal'
        df.loc[:, 'flow_type'][df['flow_type'].str.contains(
            'גאות', na=False)] = 'tide'
        df.loc[:, 'record_type'][df['record_type'].str.contains(
            'נקודה פנימית', na=False)] = 'inner_point'
        df.loc[:, 'record_type'][df['record_type'].str.contains(
            'נקודה פנימית', na=False)] = 'inner_point'
        df.loc[:, 'record_type'][df['record_type'].str.contains(
            'התחלת קטע', na=False)] = 'section_begining'
        df.loc[:, 'record_type'][df['record_type'].str.contains(
            'סיום קטע', na=False)] = 'section_ending'
        df_list.append(df)
    df = pd.concat(df_list)
    dfs = [x for _, x in df.groupby('id')]
    ds_list = []
    meta_df = read_hydro_metadata(path, gis_path, False)
    for df in dfs:
        st_id = df['id'].iloc[0]
        st_name = df['name'].iloc[0]
        print('proccessing station number: {}, {}'.format(st_id, st_name))
        meta = meta_df[meta_df['id'] == st_id]
        ds = xr.Dataset()
        df.set_index('time', inplace=True)
        attrs = {}
        attrs['station_name'] = st_name
        if not meta.empty:
            attrs['lon'] = meta.lon.values.item()
            attrs['lat'] = meta.lat.values.item()
            attrs['alt'] = meta.alt.values.item()
            attrs['drainage_basin_area'] = meta.area.values.item()
            attrs['active'] = meta.active.values.item()
        attrs['units'] = 'm'
        tide_height = df['tide_height[m]'].to_xarray()
        tide_height.name = 'HS_{}_tide_height'.format(st_id)
        tide_height.attrs = attrs
        flow = df['flow[m^3/sec]'].to_xarray()
        flow.name = 'HS_{}_flow'.format(st_id)
        attrs['units'] = 'm^3/sec'
        flow.attrs = attrs
        ds['{}'.format(tide_height.name)] = tide_height
        ds['{}'.format(flow.name)] = flow
        ds_list.append(ds)
    dsu = [get_unique_index(x) for x in ds_list]
    print('merging...')
    ds = xr.merge(dsu)
    filename = 'hydro_graphs.nc'
    print('saving {} to {}'.format(filename, path))
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in ds.data_vars}
    ds.to_netcdf(path / filename, 'w', encoding=encoding)
    print('Done!')
    return ds