#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 16 14:24:40 2019

@author: ziskin
"""
# from pathlib import Path
from PW_paths import work_yuval
sound_path = work_yuval / 'sounding'
era5_path = work_yuval / 'ERA5'
edt_path = sound_path / 'edt'


def process_physical_radiosonde_data(path=sound_path, savepath=None):
    import xarray as xr
    from aux_gps import path_glob
    file = path_glob(path, 'bet_dagan_phys_sounding_*.nc')
    phys = xr.load_dataset(file[0])
        
    return ds

def process_new_field_from_physical_data(phys_ds, dim='sound_time',
                                         field_name='pw', bottom=None,
                                         top=None, verbose=False):
    import xarray as xr
    from aux_gps import keep_iqr
    field_list = []
    for i in range(phys_ds[dim].size):
        record = phys_ds[dim].isel({dim: i})
        if 'time' in dim:
            record = record.dt.strftime('%Y-%m-%d %H:%M').values.item()
        if verbose:
            print('processing {}'.format(record))
        if field_name == 'pw':
            Dewpt = phys_ds['Dewpt'].isel({dim: i})
            P = phys_ds['P'].isel({dim: i})
            field, unit = wrap_xr_metpy_pw(Dewpt, P, bottom=bottom, top=top)
        if field_name == 'tm':
            MR = phys_ds['MR'].isel({dim: i})
            field, unit = calculate_tm_using_mixing_ratio_trapz(MR, T, bottom=bottom, top=top)
        field_list.append(field)
    da = xr.DataArray(field_list, dims=[dim])
    da[dim] = phys_ds[dim]
    da.attrs['units'] = unit
    if top is not None:
        da.attrs['top'] = top.magnitude
    if bottom is not None:
        da.attrs['bottom'] = top.magnitude
    da = keep_iqr(da, dim=dim, k=1.5)
    if verbose:
        print('Done!')
    return da


def wrap_xr_metpy_vapor_pressure(P, MR, verbose=False):
    from metpy.calc import vapor_pressure
    from metpy.units import units
    try:
        P_unit = P.attrs['units']
        assert P_unit == 'hPa'
    except KeyError:
        P_unit = 'hPa'
        if verbose:
            print('assuming pressure units are hPa...')
    try:
        MR_unit = MR.attrs['units']
        assert MR_unit == 'g/kg'
    except KeyError:
        MR_unit = 'g/kg'
        if verbose:
            print('assuming mixing ratio units are g/kg...')  
    P_values = P.values * units(P_unit)
    MR_values = MR.values * units(MR_unit)
    VP = vapor_pressure(P_values, MR_values)
    da = P.copy(data=VP.magnitude)
    da.attrs['units'] = P_unit
    return da


def wrap_xr_metpy_mixing_ratio(P, T, RH, verbose=False):
    from metpy.calc import mixing_ratio_from_relative_humidity
    import numpy as np
    from metpy.units import units
    if np.max(RH) > 1.2:
        RH_values = RH.values / 100.0
    else:
        RH_values = RH.values
    try:
        T_unit = T.attrs['units']
        assert T_unit == 'degC'
    except KeyError:
        T_unit = 'degC'
        if verbose:
            print('assuming temperature units are degC...')
        T.attrs['units'] = T_unit
    try:
        P_unit = P.attrs['units']
        assert P_unit == 'hPa'
    except KeyError:
        P_unit = 'hPa'
        if verbose:
            print('assuming pressure units are hPa...')
    T_values = T.values * units(T_unit)
    P_values = P.values * units(P_unit)
    mixing_ratio = mixing_ratio_from_relative_humidity(
        RH_values, T_values, P_values)
    da = T.copy(data=mixing_ratio.magnitude)
    da.attrs['units'] = 'g/kg'
    return da


def wrap_xr_metpy_dewpoint(T, RH, verbose=False):
    import numpy as np
    from metpy.calc import dewpoint_from_relative_humidity
    from metpy.units import units
    if np.max(RH) > 1.2:
        RH_values = RH.values / 100.0
    else:
        RH_values = RH.values
    try:
        T_unit = T.attrs['units']
        assert T_unit == 'degC'
    except KeyError:
        T_unit = 'degC'
        if verbose:
            print('assuming temperature units are degC...')
        T.attrs['units'] = T_unit
    T_values = T.values * units(T_unit)
    dewpoint = dewpoint_from_relative_humidity(T_values, RH_values)
    da = T.copy(data=dewpoint.magnitude)
    da.attrs['units'] = T_unit
    return da


def wrap_xr_metpy_pw(dewpt, pressure, bottom=None, top=None, verbose=False):
    from metpy.calc import precipitable_water
    from metpy.units import units
    try:
        T_unit = dewpt.attrs['units']
        assert T_unit == 'degC'
    except KeyError:
        T_unit = 'degC'
        if verbose:
            print('assuming dewpoint units are degC...')
    dew_values = dewpt.values * units(T_unit)
    try:
        P_unit = pressure.attrs['units']
        assert P_unit == 'hPa'
    except KeyError:
        P_unit = 'hPa'
        if verbose:
            print('assuming pressure units are hPa...')
    if top is not None:
        top = top * units(P_unit)
    if bottom is not None:
        bottom = bottom * units(P_unit)
    pressure_values = pressure.values * units(P_unit)
    pw = precipitable_water(dew_values, pressure_values, bottom=bottom, top=top)
    pw_units = pw.units.format_babel('~P')
    return pw.magnitude, pw_units


class Constants:
    def __init__(self):
        import astropy.units as u
        # Specific gas const for water vapour, J kg^{-1} K^{-1}:
        self.Rs_v = 461.52 * u.joule / (u.kilogram * u.Kelvin)
        # Specific gas const for dry air, J kg^{-1} K^{-1}:
        self.Rs_da = 287.05 * u.joule / (u.kilogram * u.Kelvin)
        self.MW_dry_air = 28.9647  * u.gram / u.mol  # gr/mol
        self.MW_water = 18.015 * u.gram / u.mol  # gr/mol
        self.Water_Density = 1000.0 * u.kilogram / u.m**3
        self.Epsilon = self.MW_water / self.MW_dry_air  # Epsilon=Rs_da/Rs_v;

    def show(self):
        from termcolor import colored
        for attr, value in vars(self).items():
            print(colored('{} : '.format(attr), color='blue', attrs=['bold']), end='')
            print(colored('{:.2f}'.format(value), color='white', attrs=['bold']))


class WaterVaporVar:
    def __init__(self, name, value, unit):
        try:
            setattr(self, name, value.values)
        except AttributeError:
            setattr(self, name, value)
        if value is not None:
            value = getattr(self, name)
            setattr(self, name, value * unit)

class WaterVapor:
    def __init__(self,
                 Z=None,
                 P=None,
                 T=None,
                 DWPT=None,
                 MR=None,
                 Q=None,
                 RH=None,
                 PPMV=None,
                 MD=None,
                 KMOL=None,
                 ND=None,
                 PP=None,
                 verbose=True):
        import astropy.units as u
        self.verbose = verbose
        self.Z = WaterVaporVar('Z', Z, u.meter).Z  # height in meters
        self.P = WaterVaporVar('P', P, u.hPa).P  # pressure in hPa
        self.T = WaterVaporVar('T', T, u.deg_C).T  # temperature in deg_C
        self.DWPT = WaterVaporVar('DWPT', DWPT, u.deg_C).DWPT  # dew_point in deg_C
        self.MR = WaterVaporVar('MR', MR, u.gram / u.kilogram).MR  # mass_mixing_ratio in gr/kg
        self.Q = WaterVaporVar('Q', Q, u.gram / u.kilogram).Q  # specific humidity in gr/kg
        self.RH = WaterVaporVar('RH', RH, u.percent).RH  # relative humidity in %
        self.PPMV = WaterVaporVar('PPMV', PPMV, u.cds.ppm).PPMV  # volume_mixing_ratio in ppm
        self.MD = WaterVaporVar('MD', MD, u.gram / u.meter**3).MD  # water vapor density in gr/m^3
        self.KMOL = WaterVaporVar('KMOL', KMOL, u.kilomole / u.cm**2).KMOL  # water vapor column density in kmol/cm^2
        self.ND = WaterVaporVar('ND', ND, u.dimensionless_unscaled / u.m**3).ND  # number density in molecules / m^3
        self.PP = WaterVaporVar('PP', PP, u.hPa).PP  # water vapor partial pressure in hPa
    # update attrs from dict containing keys as attrs and vals as attrs vals
    # to be updated

    def from_dict(self, d):
        self.__dict__.update(d)
        return self

    def show(self, name='all'):
        from termcolor import colored
        if name == 'all':
            for attr, value in vars(self).items():
                print(colored('{} : '.format(attr), color='blue', attrs=['bold']), end='')
                print(colored(value, color='white', attrs=['bold']))
        elif hasattr(self, name):
            print(colored('{} : '.format(name), color='blue', attrs=['bold']), end='')
            print(colored(self.name, color='white', attrs=['bold']))

    def convert(self, from_to='PP_to_MR'):
        import astropy.units as u
        C = Constants()
        from_name = from_to.split('_')[0]
        to_name = from_to.split('_')[-1]
        from_ = getattr(self, from_name)
        to_ = getattr(self, to_name)
        print('converting {} to {}:'.format(from_name, to_name))
        if to_ is not None:
            if self.verbose:
                print('{} already exists, overwriting...'.format(to_name))
        if from_ is not None:
            if from_name == 'PP' and to_name == 'MR':
                # convert wv partial pressure to mass mixing ratio:
                if self.P is None:
                    raise Exception('total pressure is needed for this conversion')
                self.MR = C.Epsilon * self.PP / (self.P - self.PP) / self.MR.unit.decompose()
                return self.MR
            elif from_name == 'MR' and to_name == 'PP':
                # convert mass mixing ratio to wv partial pressure:
                if self.P is None:
                    raise Exception('total pressure is needed for this conversion')
                e_tag = self.MR * self.MR.unit.decompose() / (C.Epsilon)
                self.PP = self.P * e_tag / (1. * e_tag.unit + e_tag)
                return self.PP
        else:
            raise Exception('{} is needed to perform conversion'.format(from_))
        return self

def check_sound_time(df):
    import pandas as pd
    # check for validity of radiosonde air time, needs to be
    # in noon or midnight:
    if not df.between_time('22:00', '02:00').empty:
        sound_time = pd.to_datetime(
            df.index[0].strftime('%Y-%m-%d')).replace(hour=0, minute=0)
    elif not df.between_time('10:00', '14:00').empty:
        sound_time = pd.to_datetime(
            df.index[0].strftime('%Y-%m-%d')).replace(hour=12, minute=0)
    elif (df.between_time('22:00', '02:00').empty and
          df.between_time('10:00', '14:00').empty):
        raise ValueError(
            '{} time is not midnight nor noon'.format(
                df.index[0]))
    return sound_time


def calculate_tm_edt(wvpress, tempc, height, mixratio,
                     press, method='mr_trapz'):
    def calculate_tm_with_method(method='mr_trapz'):
        import numpy as np
        import pandas as pd
        nonlocal wvpress, tempc, height, mixratio, press
        # conver Mixing ratio to WV-PP(e):
        MW_dry_air = 28.9647  # gr/mol
        MW_water = 18.015  # gr/mol
        Epsilon = MW_water / MW_dry_air  # Epsilon=Rs_da/Rs_v;
        mr = pd.Series(mixratio)
        p = pd.Series(press)
        eps_tag = mr / (1000.0 * Epsilon)
        e = p * eps_tag / (1.0 + eps_tag)
        try:
            # directly use WV-PP with trapz:
            if method == 'wv_trapz':
                numerator = np.trapz(
                    wvpress /
                    (tempc +
                     273.15),
                    height)
                denominator = np.trapz(
                    wvpress / (tempc + 273.15)**2.0, height)
                tm = numerator / denominator
            # use WV-PP from mixing ratio with trapz:
            elif method == 'mr_trapz':
                numerator = np.trapz(
                    e /
                    (tempc +
                     273.15),
                    height)
                denominator = np.trapz(
                    e / (tempc + 273.15)**2.0, height)
                tm = numerator / denominator
            # use WV-PP from mixing ratio with sum:
            elif method == 'mr_sum':
                e_ser = pd.Series(e)
                height = pd.Series(height)
                e_sum = (e_ser.shift(-1) + e_ser).dropna()
                h = height.diff(-1).abs()
                numerator = 0.5 * (e_sum * h / (pd.Series(tempc) + 273.15)).sum()
                denominator = 0.5 * \
                    (e_sum * h / (pd.Series(tempc) + 273.15)**2.0).sum()
                tm = numerator / denominator
        except ValueError:
            return np.nan
        return tm
    if method is None:
        tm_wv_trapz = calculate_tm_with_method('wv_trapz')
        tm_mr_trapz = calculate_tm_with_method('mr_trapz')
        tm_sum = calculate_tm_with_method('sum')
    else:
        tm = calculate_tm_with_method(method)
        chosen_method = method
    return tm, chosen_method


def calculate_tpw_edt(mixratio, rho, rho_wv, height, press, g, method='trapz'):
    def calculate_tpw_with_method(method='trapz'):
        nonlocal mixratio, rho, rho_wv, height, press, g
        import numpy as np
        import pandas as pd
        # calculate specific humidity q:
        q = (mixratio / 1000.0) / \
            (1 + 0.001 * mixratio / 1000.0)
        try:
            if method == 'trapz':
                tpw = np.trapz(q * rho,
                               height)
            elif method == 'sum':
                rho_wv = pd.Series(rho_wv)
                height = pd.Series(height)
                rho_sum = (rho_wv.shift(-1) + rho_wv).dropna()
                h = height.diff(-1).abs()
                tpw = 0.5 * (rho_sum * h).sum()
            elif method == 'psum':
                q = pd.Series(q)
                q_sum = q.shift(-1) + q
                p = pd.Series(press) * 100.0  # to Pa
                dp = p.diff(-1).abs()
                tpw = (q_sum * dp / (2.0 * 1000 * g)).sum() * 1000.0
        except ValueError:
            return np.nan
        return tpw
    if method is None:
        # calculate all the methods and choose trapz if all agree:
        tpw_trapz = calculate_tpw_with_method(method='trapz')
        tpw_sum = calculate_tpw_with_method(method='sum')
        tpw_psum = calculate_tpw_with_method(method='psum')
    else:
        tpw = calculate_tpw_with_method(method=method)
        chosen_method = method
    return tpw, chosen_method


def read_one_EDT_record(filepath):
    import pandas as pd
    import numpy as np
    import xarray as xr
    from aux_gps import get_unique_index
    from aux_gps import calculate_g
    from aux_gps import remove_duplicate_spaces_in_string
    from metpy.calc import precipitable_water
    from metpy.units import units
    with open(filepath) as f:
        content = f.readlines()
    content = [x.strip() for x in content]
    meta = {}
    for i, line in enumerate(content):
        if line.startswith('Station:'):
            line = remove_duplicate_spaces_in_string(line)
            meta['station'] = line.split(' ')[1]
        if line.startswith('Launch time:'):
            line = remove_duplicate_spaces_in_string(line)
            dt = 'T'.join(line.split(' ')[2:4])
            meta['launch_time'] = pd.to_datetime(dt)
        if line.startswith('RS type:'):
            line = remove_duplicate_spaces_in_string(line)
            rs_type = line.split(' ' )[-1]
            meta['RS_type'] = rs_type
        if line.startswith('RS number:'):
            line = remove_duplicate_spaces_in_string(line)
            rs_num = line.split(' ' )[-1]
            meta['RS_number'] = rs_num
        if line.startswith('Reason for termination:'):
            line = remove_duplicate_spaces_in_string(line)
            termination = line.split(' ' )[-1]
            meta['termination_reason'] = termination
        if line.startswith('Record name:'):
            meta_header = remove_duplicate_spaces_in_string(line)
            meta_header = meta_header.split(': ')
            meta_header[-1] = meta_header[-1].split(':')[0]
        if i >42:
            break
    # read units table:        global mixratio, rho, rho_wv, height, press, g

    table = pd.read_fwf(
        filepath,
        skiprows=22,
        nrows=19,
        header=None,
        widths=[16, 16, 23, 9, 9])
    table.columns = meta_header
    # drop 3 last rows:
    table = table.iloc[:-3, :]
    # units dict:
    units = dict(zip(table['Record name'], table['Unit']))
    units.pop('Pscl')
    # read all data:
    data = pd.read_csv(
        filepath,
        delim_whitespace=True,
        skiprows=44,
        na_values=-32768)
    # drop 3 last cols:
    data = data.iloc[:, :-3]
    data = data.drop('Pscl', axis=1)
    # datetime index:
    Time = data['time']
    data['time'] = pd.to_timedelta(data['time'], errors='coerce', unit='sec')
    data['time'] += meta['launch_time']
    data.set_index('time', inplace=True)
    sound_time = check_sound_time(data)
    # now index as height:
    data.set_index('Height', inplace=True)
    data['time'] = Time
    data = data.astype('float')
    data.index = data.index.astype('float')
    # to xarray:
    ds = data.to_xarray()
    ds = ds.sortby('Height')
    ds = get_unique_index(ds, 'Height')
    # interpolate:
    h = np.linspace(31, 25000, 5000)
    ds_list = []
    for da in ds.data_vars.values():
        # dropna in all vars:
        dropped = da.dropna('Height')
        # if some data remain, interpolate:
        if dropped.size > 0:
            ds_list.append(dropped.interp({'Height': h}, method='cubic'))
        # if nothing left, create new ones with nans:
        else:
            nan_da = np.nan * ds['Height']
            nan_da.name = dropped.name
            ds_list.append(dropped)
    ds = xr.merge(ds_list)
    # copy general attrs:
    for key, val in meta.items():
        ds.attrs[key] = val
    ds.attrs['sound_time'] = sound_time
    ds['Height'].attrs['unit'] = 'm'
    # copy unit attrs:
    for key, val in units.items():
        try:
            ds[key].attrs['unit'] = val
        except KeyError:
            pass
    ds = ds.rename({'Lat': 'lat', 'Lon': 'lon', 'Range': 'range'})
    # add more variables: Tm, Tpw, etc...
    ds['g'] = calculate_g(ds['lat'][0])
    ds['g'].attrs.update({'long_name': 'gravitational accelaration',
      'unit': 'm*sec^-2'})
    ds['T'] -= 273.15
    ds['T'].attrs['unit'] = 'degC'
    ds['WVpress'] = VaporPressure(ds['TD'] - 273.15, phase="liquid", units='hPa',
                              method='Buck')
    ds['WVpress'].attrs['unit'] = 'hPa'
    ds['Rho'] = DensHumid(ds['T'], ds['P'], ds['WVpress'],
                    out='both')
    ds['Rho'].attrs['unit'] = 'kg/m^3'
    ds['Rho_wv'] = DensHumid(ds['T'], ds['P'], ds['WVpress'],
                       out='wv_density')
    ds['Rho_wv'].attrs['unit'] = 'kg/m^3'
    # calculate Tpw with default method:
    ds['Tpw'], chosen_method = calculate_tpw_edt(
        ds['MR'],
        ds['Rho'],
        ds['Rho_wv'],
        ds['Height'], ds['P'], ds['g'].values.item(),
        method='trapz')
    ds['Tpw'].attrs.update({'long_name': 'Total precipitable water',
                            'unit': 'kg*m^-2',
                            'integration_method': chosen_method})
    ds['Ts'] = ds['T'][0] + 273.15
    ds['Ts'].attrs.update({'long_name': 'Surface temperature', 'unit': 'K'})
    ds['Tm'], chosen_method = calculate_tm_edt(ds['WVpress'], ds['T'], ds['Height'],
                                    ds['MR'], ds['P'], method='mr_trapz')
    ds['Tm'].attrs.update({'long_name': 'Water vapor mean atmospheric temperature',
                              'unit': 'K', 'integration_method': chosen_method})
    ds.attrs['launch_time'] = ds.attrs['launch_time'].strftime('%Y-%m-%d %H:%M:%S')
    ds.attrs['sound_time'] = ds.attrs['sound_time'].strftime('%Y-%m-%d %H:%M:%S')
    return ds


def transform_model_levels_to_pressure(path, field_da, plevel=85.0, mm=True):
    """takes a field_da (like t, u) that uses era5 L137 model levels and
    interpolates it using pf(only monthly means) to desired plevel"""
    # TODO: do scipy.interpolate instead of np.interp (linear)
    # TODO: add multiple plevel support
    import xarray as xr
    from aux_functions_strat import dim_intersection
    import numpy as np
    if mm:
        pf = xr.open_dataset(path / 'era5_full_pressure_mm_1979-2018.nc')
    pf = pf.pf
    levels = dim_intersection([pf, field_da], dropna=False, dim='level')
    pf = pf.sel(level=levels)
    field_da = field_da.sel(level=levels)
    field_da = field_da.transpose('time', 'latitude', 'longitude', 'level')
    field = field_da.values
    da = np.zeros((pf.time.size, pf.latitude.size, pf.longitude.size, 1),
                  'float32')
    pf = pf.values
    for t in range(pf.shape[0]):
        print(t)
        for lat in range(pf.shape[1]):
            for lon in range(pf.shape[2]):
                pressures = pf[t, lat, lon, :]
                vals = field[t, lat, lon, :]
                da[t, lat, lon, 0] = np.interp(plevel, pressures, vals)
    da = xr.DataArray(da, dims=['time', 'lat', 'lon', 'level'])
    da['level'] = [plevel]
    da['time'] = field_da['time']
    da['level'].attrs['long_name'] = 'pressure_level'
    da['level'].attrs['units'] = 'hPa'
    da['lat'] = field_da['latitude'].values
    da['lat'].attrs = field_da['latitude'].attrs
    da['lon'] = field_da['longitude'].values
    da['lon'].attrs = field_da['longitude'].attrs
    da.name = field_da.name
    da.attrs = field_da.attrs
    da = da.sortby('lat')
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in da.to_dataset(name=da.name).data_vars}
    filename = 'era5_' + da.name + '_' + str(int(plevel)) + 'hPa.nc'
    da.to_netcdf(path / filename, encoding=encoding)
    return da


def create_model_levels_map_from_surface_pressure(work_path):
    import numpy as np
    import xarray as xr
    """takes ~24 mins for monthly mean with 1.25x1.25 degree for full 137
    levels,~=2.9GB file. Don't try with higher sample rate"""
    ds = read_L137_to_ds(work_path)
    a = ds.a.values
    b = ds.b.values
    n = ds.n.values
    sp = xr.open_dataset(work_path / 'era5_SP_mm_1979-2018.nc')
    sp = sp.sp / 100.0
    pf = np.zeros((sp.time.size, sp.latitude.size, sp.longitude.size, len(a)),
                  'float32')
    sp_np = sp.values
    for t in range(sp.time.size):
        print(t)
        for lat in range(sp.latitude.size):
            for lon in range(sp.longitude.size):
                ps = sp_np[t, lat, lon]
                pf[t, lat, lon, :] = pressure_from_ab(ps, a, b, n)
    pf_da = xr.DataArray(pf, dims=['time', 'latitude', 'longitude', 'level'])
    pf_da.attrs['units'] = 'hPa'
    pf_da.attrs['long_name'] = 'full_pressure_level'
    pf_ds = pf_da.to_dataset(name='pf')
    pf_ds['level'] = n
    pf_ds['level'].attrs['long_name'] = 'model_level_number'
    pf_ds['latitude'] = sp.latitude
    pf_ds['latitude'].attrs = sp.latitude.attrs
    pf_ds['longitude'] = sp.longitude
    pf_ds['longitude'].attrs = sp.longitude.attrs
    pf_ds['time'] = sp.time
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in pf_ds.data_vars}
    pf_ds.to_netcdf(work_path / 'era5_full_pressure_mm_1979-2018.nc',
                    encoding=encoding)
    return pf_ds


def calculate_era5_tm(q_ml, t_ml, pf_ml, g=9.79):
    """given pressure in model levels(ps_ml) and specific humidity(q_ml)
    in era5 model levels and temperature, compute the tm for each lat/lon grid point."""
    assert t_ml.attrs['units'] == 'K'
    assert q_ml.attrs['units'] == 'kg kg**-1'
    assert pf_ml.attrs['units'] == 'Pa'
    factor = g * 2   # g in mks
    WVpress = VaporPressure(t_ml - 273.15, method='Buck', units='Pa')
    wvpress = WVpress + WVpress.shift(level=1)
    t = t_ml + t_ml.shift(level=1)
    t2 = t_ml**2.0 + t_ml.shift(level=1)**2.0
    Rho = DensHumid(t_ml - 273.15, pf_ml / 100.0, WVpress / 100.0, out='both')
    rho = Rho + Rho.shift(level=1)
    nume = ((wvpress * pf_ml.diff('level')) / (t * rho * factor)).sum('level')
    denom = ((wvpress * pf_ml.diff('level')) / (t2 * rho * factor)).sum('level')
    tm = nume / denom
    tm.name = 'Tm'
    tm.attrs['units'] = 'K'
    return tm


def calculate_era5_pw(q_ml, pf_ml, g=9.79):
    """given pressure in model levels(ps_ml) and specific humidity(q_ml)
    in era5 model levels, compute the IWV for each lat/lon grid point."""
    assert q_ml.attrs['units'] == 'kg kg**-1'
    assert pf_ml.attrs['units'] == 'Pa'
    factor = g * 2 * 1000  # density of water in mks, g in mks
    pw = (((q_ml + q_ml.shift(level=1)) * pf_ml.diff('level')) / factor).sum('level')
    pw = pw * 1000.0
    pw.name = 'PW'
    pw.attrs['units'] = 'mm'
    return pw


def pressure_from_ab(ps_da, ds_l137):
    """takes the surface pressure(hPa) and  a, b coeffs from L137(n) era5
    table and produces the pressure level point in hPa"""
    try:
        unit = ps_da.attrs['units']
    except AttributeError:
        # assume Pascals in ps
        unit = 'Pa'
    a = ds_l137.a
    b = ds_l137.b
    if unit == 'Pa':
        ph = a + b * ps_da
    pf_da = 0.5 * (ph + ph.shift(n=1))
    pf_da.name = 'pressure'
    pf_da.attrs['units'] = unit
    pf_da = pf_da.dropna('n')
    pf_da = pf_da.rename({'n': 'level'})
    return pf_da


def read_L137_to_ds(path):
    import pandas as pd
    l137_df = pd.read_csv(path / 'L137_model_levels_1976_climate.txt',
                          header=None, delim_whitespace=True, na_values='-')
    l137_df.columns = ['n', 'a', 'b', 'ph', 'pf', 'Geopotential Altitude',
                       'Geometric Altitude', 'Temperature', 'Density']
    l137_df.set_index('n')
    l137_df.drop('n', axis=1, inplace=True)
    l137_df.index.name = 'n'
    ds = l137_df.to_xarray()
    ds.attrs['long_name'] = 'L137 model levels and 1976 ICAO standard atmosphere 1976'
    ds.attrs['surface_pressure'] = 1013.250
    ds.attrs['pressure_units'] = 'hPa'
    ds.attrs['half_pressure_formula'] = 'ph(k+1/2) = a(k+1/2) + ps*b(k+1/2)'
    ds.attrs['full_pressure_formula'] = 'pf(k) = 1/2*(ph(k-1/2) + ph(k+1/2))'
    ds['n'].attrs['long_name'] = 'model_level_number'
    ds['a'].attrs['long_name'] = 'a_coefficient'
    ds['a'].attrs['units'] = 'Pa'
    ds['b'].attrs['long_name'] = 'b_coefficient'
    ds['ph'].attrs['long_name'] = 'half_pressure_level'
    ds['ph'].attrs['units'] = 'hPa'
    ds['pf'].attrs['long_name'] = 'full_pressure_level'
    ds['pf'].attrs['units'] = 'hPa'
    ds['Geopotential Altitude'].attrs['units'] = 'm'
    ds['Geometric Altitude'].attrs['units'] = 'm'
    ds['Temperature'].attrs['units'] = 'K'
    ds['Density'].attrs['units'] = 'kg/m^3'
    return ds


def merge_era5_fields_and_save(path=era5_path, field='SP'):
    from aux_gps import path_glob
    import xarray as xr
    files = path_glob(path, 'era5_{}*.nc'.format(field))
    ds = xr.open_mfdataset(files)
    ds = concat_era5T(ds)
    ds = ds.rename({'latitude': 'lat', 'longitude': 'lon'})
    ds = ds.sortby('lat')
    yr_min = ds.time.min().dt.year.item()
    yr_max = ds.time.max().dt.year.item()
    filename = 'era5_{}_israel_{}-{}.nc'.format(field, yr_min, yr_max)
    print('saving {} to {}'.format(filename, path))
    ds.to_netcdf(path / filename, 'w')
    print('Done!')
    return ds


def concat_era5T(ds):
    import xarray as xr
    field_0001 = [x for x in ds.data_vars if '0001' in x]
    field_0005 = [x for x in ds.data_vars if '0005' in x]
    field = [x for x in ds.data_vars if '0001' not in x and '0005' not in x]
    if field_0001 and field_0005:
        da = xr.concat([ds[field_0001[0]].dropna('time'),
                        ds[field_0005[0]].dropna('time')], 'time')
        da.name = field_0001[0].split('_')[0]
    elif not field_0001 and not field_0005:
        return ds
    if field:
        da = xr.concat([ds[field[0]].dropna('time'), da], 'time')
    dss = da.to_dataset(name=field[0])
    return dss


def merge_concat_era5_field(path=era5_path, field='Q', savepath=None):
    import xarray as xr
    from aux_gps import path_glob
    strato_files = path_glob(path, 'era5_{}_*_pl_1_to_150.nc'.format(field))
    strato_list = [xr.open_dataset(x) for x in strato_files]
    strato = xr.concat(strato_list, 'time')
    tropo_files = path_glob(path, 'era5_{}_*_pl_175_to_1000.nc'.format(field))
    tropo_list = [xr.open_dataset(x) for x in tropo_files]
    tropo = xr.concat(tropo_list, 'time')
    ds = xr.concat([tropo, strato], 'level')
    ds = ds.sortby('level', ascending=False)
    ds = ds.sortby('time')
    ds = ds.rename({'latitude': 'lat', 'longitude': 'lon'})
    if savepath is not None:
        yr_min = ds.time.min().dt.year.item()
        yr_max = ds.time.max().dt.year.item()
        filename = 'era5_{}_israel_{}-{}.nc'.format(field, yr_min, yr_max)
        print('saving {} to {}'.format(filename, savepath))
        comp = dict(zlib=True, complevel=9)  # best compression
        encoding = {var: comp for var in ds}
        ds.to_netcdf(savepath / filename, 'w', encoding=encoding)
    print('Done!')
    return ds


def calculate_PW_from_era5(path=era5_path, glob_str='era5_Q_israel*.nc',
                           water_density=1000.0, savepath=None):
    import xarray as xr
    from aux_gps import path_glob
    from aux_gps import calculate_g
    import numpy as np
    file = path_glob(path, glob_str)[0]
    Q = xr.open_dataset(file)['q']
    g = calculate_g(Q.lat)
    g.name = 'g'
    g = g.mean('lat')
    plevel_in_pa = Q.level * 100.0
    # P_{i+1} - P_i:
    plevel_diff = np.abs(plevel_in_pa.diff('level'))
    # Q_i + Q_{i+1}:
    Q_sum = Q.shift(level=-1) + Q
    pw_in_mm = ((Q_sum * plevel_diff) /
                (2.0 * water_density * g)).sum('level') * 1000.0
    pw_in_mm.name = 'pw'
    pw_in_mm.attrs['units'] = 'mm'
    if savepath is not None:
        yr_min = pw_in_mm.time.min().dt.year.item()
        yr_max = pw_in_mm.time.max().dt.year.item()
        filename = 'era5_PW_israel_{}-{}.nc'.format(yr_min, yr_max)
        print('saving {} to {}'.format(filename, savepath))
        comp = dict(zlib=True, complevel=9)  # best compression
        encoding = {var: comp for var in pw_in_mm.to_dataset(name='pw')}
        pw_in_mm.to_netcdf(savepath / filename, 'w', encoding=encoding)
    print('Done!')
    return pw_in_mm


def calculate_Tm_from_era5(path=era5_path, Tfile='era5_T_israel*.nc',
                           RHfile='era5_RH_israel*.nc', savepath=None):
    import xarray as xr
    from aux_gps import path_glob
    tfile = path_glob(path, Tfile)
    rhfile = path_glob(path, RHfile)
    T = xr.open_dataarray(tfile)
    RH = xr.open_dataarray(rhfile)
    Dewpt = dewpoint_rh(T, RH)
    WVpress = VaporPressure(Dewpt, units='hPa', method='Buck')
    nom = WVpress / T
    nom = nom.integrate('level')
    denom = WVpress / T ** 2.0
    denom = denom.integrate('level')
    Tm = nom / denom
    Tm.name = 'Tm'
    Tm.attrs['units'] = 'K'
    if savepath is not None:
        yr_min = Tm.time.min().dt.year.item()
        yr_max = Tm.time.max().dt.year.item()
        filename = 'era5_Tm_israel_{}-{}.nc'.format(yr_min, yr_max)
        print('saving {} to {}'.format(filename, savepath))
        comp = dict(zlib=True, complevel=9)  # best compression
        encoding = {var: comp for var in Tm.to_dataset(name='Tm')}
        Tm.to_netcdf(savepath / filename, 'w', encoding=encoding)
    print('Done!')
    return Tm


def calculate_pw_from_physical_with_params(temp, rh, press, height, **params):
    """calculate the pw from radiosonde temp, rh, press, height, params are
    kwargs that hold the parameters for scaling the temp, rh, press, etc.."""
    import numpy as np
    dewpt = dewpoint_rh(temp, rh)
    wvpress = VaporPressure(dewpt, units='hPa', method='Buck')
    mixratio = MixRatio(wvpress, press)  # both in hPa
    # Calculate density of air (accounting for moisture)
    rho = DensHumid(temp, press, wvpress, out='both')
    specific_humidity = (mixratio / 1000.0) / (1 + 0.001 * mixratio / 1000.0)
    pw = np.trapz(specific_humidity * rho, height)
    return pw


def evaluate_sin_to_tmsearies(
        da,
        time_dim='time',
        plot=True,
        params_up={
                'amp': 6.0,
                'period': 365.0,
                'phase': 30.0,
                'offset': 253.0,
                'a': 0.0,
                'b': 0.0},
        func='sine',
        bounds=None,
        just_eval=False):
    import pandas as pd
    import xarray as xr
    import numpy as np
    from aux_gps import dim_intersection
    from scipy.optimize import curve_fit
    from sklearn.metrics import mean_squared_error

    def sine(time, amp, period, phase, offset):
        f = amp * np.sin(2 * np.pi * (time / period + 1.0 / phase)) + offset
        return f

    def sine_on_linear(time, amp, period, phase, offset, a):
        f = a * time / 365.25 + amp * \
            np.sin(2 * np.pi * (time / period + 1.0 / phase)) + offset
        return f

    def sine_on_quad(time, amp, period, phase, offset, a, b):
        f = a * (time / 365.25) ** 2.0 + b * time / 365.25 + amp * \
            np.sin(2 * np.pi * (time / period + 1.0 / phase)) + offset
        return f
    params={'amp': 6.0,
            'period': 365.0,
            'phase': 30.0,
            'offset': 253.0,
            'a': 0.0,
            'b': 0.0}
    params.update(params_up)
    print(params)
    lower = {}
    upper = {}
    if bounds is not None:
        # lower = [(x - y) for x, y in zip(params, perc2)]
        for key in params.keys():
            lower[key] = -np.inf
            upper[key] = np.inf
        lower['phase'] = 0.01
        upper['phase'] = 0.05
        lower['offset'] = 46.2
        upper['offset'] = 46.3
        lower['a'] = 0.0001
        upper['a'] = 0.002
        upper['amp'] = 0.04
        lower['amp'] = 0.02
    else:
        for key in params.keys():
            lower[key] = -np.inf
            upper[key] = np.inf
    lower = [x for x in lower.values()]
    upper = [x for x in upper.values()]
    params = [x for x in params.values()]
    da_no_nans = da.dropna(time_dim)
    time = da_no_nans[time_dim].values
    time = pd.to_datetime(time)
    jul = time.to_julian_date()
    jul -= jul[0]
    jul_with_nans = pd.to_datetime(da[time_dim].values).to_julian_date()
    jul_with_nans -= jul[0]
    ydata = da_no_nans.values
    if func == 'sine':
        print('Model chosen: y = amp * sin (2*pi*(x/T + 1/phi)) + offset')
        if not just_eval:
            popt, pcov = curve_fit(sine, jul, ydata, p0=params[:-2],
                                   bounds=(lower[:-2], upper[:-2]), ftol=1e-9,
                                   xtol=1e-9)
            amp = popt[0]
            period = popt[1]
            phase = popt[2]
            offset = popt[3]
            perr = np.sqrt(np.diag(pcov))
            print('amp: {:.4f} +- {:.2f}'.format(amp, perr[0]))
            print('period: {:.2f} +- {:.2f}'.format(period, perr[1]))
            print('phase: {:.2f} +- {:.2f}'.format(phase, perr[2]))
            print('offset: {:.2f} +- {:.2f}'.format(offset, perr[3]))
        new = sine(jul_with_nans, amp, period, phase, offset)
    elif func == 'sine_on_linear':
        print('Model chosen: y = a * x + amp * sin (2*pi*(x/T + 1/phi)) + offset')
        if not just_eval:
            popt, pcov = curve_fit(sine_on_linear, jul, ydata, p0=params[:-1],
                                   bounds=(lower[:-1], upper[:-1]), xtol=1e-11,
                                   ftol=1e-11)
            amp = popt[0]
            period = popt[1]
            phase = popt[2]
            offset = popt[3]
            a = popt[4]
            perr = np.sqrt(np.diag(pcov))
            print('amp: {:.4f} +- {:.2f}'.format(amp, perr[0]))
            print('period: {:.2f} +- {:.2f}'.format(period, perr[1]))
            print('phase: {:.2f} +- {:.2f}'.format(phase, perr[2]))
            print('offset: {:.2f} +- {:.2f}'.format(offset, perr[3]))
            print('a: {:.7f} +- {:.2f}'.format(a, perr[4]))
        new = sine_on_linear(jul_with_nans, amp, period, phase, offset, a)
    elif func == 'sine_on_quad':
        print('Model chosen: y = a * x^2 + b * x + amp * sin (2*pi*(x/T + 1/phi)) + offset')
        if not just_eval:
            popt, pcov = curve_fit(sine_on_quad, jul, ydata, p0=params,
                                   bounds=(lower, upper))
            amp = popt[0]
            period = popt[1]
            phase = popt[2]
            offset = popt[3]
            a = popt[4]
            b = popt[5]
            perr = np.sqrt(np.diag(pcov))
            print('amp: {:.4f} +- {:.2f}'.format(amp, perr[0]))
            print('period: {:.2f} +- {:.2f}'.format(period, perr[1]))
            print('phase: {:.2f} +- {:.2f}'.format(phase, perr[2]))
            print('offset: {:.2f} +- {:.2f}'.format(offset, perr[3]))
            print('a: {:.7f} +- {:.2f}'.format(a, perr[4]))
            print('b: {:.7f} +- {:.2f}'.format(a, perr[5]))
        new = sine_on_quad(jul_with_nans, amp, period, phase, offset, a, b)
    new_da = xr.DataArray(new, dims=[time_dim])
    new_da[time_dim] = da[time_dim]
    resid = new_da - da
    rmean = np.mean(resid)
    new_time = dim_intersection([da, new_da], time_dim)
    rmse = np.sqrt(mean_squared_error(da.sel({time_dim: new_time}).values,
                                      new_da.sel({time_dim: new_time}).values))
    print('MEAN : {}'.format(rmean))
    print('RMSE : {}'.format(rmse))
    if plot:
        da.plot.line(marker='.', linewidth=0., figsize=(20, 5))
        new_da.plot.line(marker='.', linewidth=0.)
    return new_da


def move_bet_dagan_physical_to_main_path(bet_dagan_path):
    """rename bet_dagan physical radiosonde filenames and move them to main
    path i.e., bet_dagan_path! warning-DO ONCE """
    from aux_gps import path_glob
    import shutil
    year_dirs = sorted([x for x in path_glob(bet_dagan_path, '*/') if x.is_dir()])
    for year_dir in year_dirs:
        month_dirs = sorted([x for x in path_glob(year_dir, '*/') if x.is_dir()])
        for month_dir in month_dirs:
            day_dirs = sorted([x for x in path_glob(month_dir, '*/') if x.is_dir()])
            for day_dir in day_dirs:
                hour_dirs = sorted([x for x in path_glob(day_dir, '*/') if x.is_dir()])
                for hour_dir in hour_dirs:
                    file = [x for x in path_glob(hour_dir, '*/') if x.is_file()]
                    splitted = file[0].as_posix().split('/')
                    name = splitted[-1]
                    hour = splitted[-2]
                    day = splitted[-3]
                    month = splitted[-4]
                    year = splitted[-5]
                    filename = '{}_{}{}{}{}'.format(name, year, month, day, hour)
                    orig = file[0]
                    dest = bet_dagan_path / filename
                    shutil.move(orig.resolve(), dest.resolve())
                    print('moving {} to {}'.format(filename, bet_dagan_path))
    return year_dirs


def read_all_physical_radiosonde(path, savepath=None, concat_epoch_num=300,
                                 verbose=True):
    from aux_gps import path_glob
    from aux_gps import get_unique_index
    from aux_gps import keep_iqr
    import xarray as xr
    from aux_gps import save_ncfile
    import gc
    ds_list = []
    # ds_extra_list = []
    cnt = 0
    cnt_save = 0
    for path_file in sorted(path_glob(path, '*/')):
        cnt += 1
        if path_file.is_file():
            ds = read_one_physical_radiosonde_report(path_file)
            if ds is None:
                print('{} is corrupted...'.format(
                    path_file.as_posix().split('/')[-1]))
                continue
            date = ds['sound_time'].dt.strftime('%Y-%m-%d %H:%M').values.item()
            if verbose:
                print('reading {} physical radiosonde report'.format(date))
            # ds_with_time_dim = [x for x in ds.data_vars if 'time' in ds[x].dims]
            # ds_list.append(ds[ds_with_time_dim])
            ds_list.append(ds)
            # ds_extra = [x for x in ds.data_vars if 'time' not in ds[x].dims]
            # ds_extra_list.append(ds[ds_extra])
            # every 600 iters, concat:
            if cnt % concat_epoch_num == 0:
                cnt_save += 1
                print('concatating and saving every {} points'.format(concat_epoch_num))
                temp = xr.concat(ds_list, 'sound_time')
                save_ncfile(temp, savepath, filename='bet_dagan_temp_{}.nc'.format(cnt_save))
                del temp
                ds_list = []
                print("Collecting...")
                n = gc.collect()
                print("Number of unreachable objects collected by GC:", n)
                print("Uncollectable garbage:", gc.garbage)
            if cnt == len(path_glob(path, '*/')):
                temp = xr.concat(ds_list, 'sound_time')
                save_ncfile(temp, savepath, filename='bet_dagan_temp_{}.nc'.format(cnt_save))
                ds_list = []
    # dss = xr.concat(ds_list, 'time')
    print('loading temp files and concatenating...')
    tempfiles = path_glob(savepath, 'bet_dagan_temp*.nc')
    temp_list = [xr.open_dataset(x) for x in tempfiles]
    dss = xr.concat(temp_list, 'sound_time')
    dss = dss.sortby('sound_time')
    dss = get_unique_index(dss, 'sound_time')
    # filter iqr:
    da_list = []
    for da in dss.data_vars.values():
        if len(da.dims) == 1:
            if da.dims[0] == 'sound_time' and da.dtype == 'float64':
                da_list.append(keep_iqr(da, dim='sound_time'))
    new_ds = xr.merge(da_list)
    # replace with filtered vars:
    for da in new_ds.data_vars:
        dss[da] = new_ds[da]
    if savepath is not None:
        yr_min = dss.sound_time.min().dt.year.item()
        yr_max = dss.sound_time.max().dt.year.item()
        filename = 'bet_dagan_phys_sounding_{}-{}.nc'.format(yr_min, yr_max)
        print('saving {} to {}'.format(filename, savepath))
        comp = dict(zlib=True, complevel=9)  # best compression
        encoding = {var: comp for var in dss}
        dss.to_netcdf(savepath / filename, 'w', encoding=encoding)
        print('clearing temp files...')
        [x.unlink() for x in tempfiles]
    print('Done!')
    return dss


def read_one_physical_radiosonde_report(path_file, verbose=False):
    """read one(12 or 00) physical bet dagan radiosonde reports and return a df
    containing time series, PW for the whole sounding and time span of the
    sounding"""
    import numpy as np
    from aux_gps import get_unique_index
    import pandas as pd
    import xarray as xr

    def df_to_ds_and_interpolate(df, h='Height'):
        import numpy as np
        # set index the height, and transform to xarray:
        df = df.set_index(h).squeeze()
        ds = df.to_xarray()
        ds = ds.sortby(h)
        ds = get_unique_index(ds, dim=h)
        # do cubic interpolation:
        height = np.linspace(35, 25000, 500)
        ds_list = []
        for da in ds.data_vars.values():
            # dropna in all vars:
            dropped = da.dropna(h)
            # if some data remain, interpolate:
            if dropped.size > 0:
                ds_list.append(dropped.interp({h: height}, method='cubic'))
            # if nothing left, create new ones with nans:
            else:
                nan_da = np.nan * ds[h]
                nan_da.name = dropped.name
                ds_list.append(dropped)
        ds = xr.merge(ds_list)
        ds.attrs['operation'] = 'all physical fields were cubic interpolated to {}'.format(h)
        return ds

    # TODO: recheck units, add to df and to units_dict
    df = pd.read_csv(
         path_file,
         header=None,
         encoding="windows-1252",
         delim_whitespace=True,
         skip_blank_lines=True,
         na_values=['/////'])
    time_str = path_file.as_posix().split('/')[-1].split('_')[-1]
    dt = pd.to_datetime(time_str, format='%Y%m%d%H')
    if not df[df.iloc[:, 0].str.contains('PILOT')].empty:
        return None
    # drop last two cols:
    df.drop(df.iloc[:, -2:len(df)], inplace=True, axis=1)
    # extract datetime:
    date = df[df.loc[:, 0].str.contains("PHYSICAL")].loc[0, 3]
    time = df[df.loc[:, 0].str.contains("PHYSICAL")].loc[0, 4]
    dt = pd.to_datetime(date + 'T' + time, dayfirst=True)
    # extract station number:
    station_num = int(df[df.loc[:, 0].str.contains("STATION")].iloc[0, 3])
    # extract cloud code:
    cloud_code = df[df.loc[:, 0].str.contains("CLOUD")].iloc[0, 3]
    # extract sonde_type:
    sonde_type = df[df.loc[:, 5].fillna('NaN').str.contains("TYPE")].iloc[0, 7:9]
    sonde_type = sonde_type.dropna()
    sonde_type = '_'.join(sonde_type.to_list())
    # change col names to:
    df.columns = ['Time', 'T', 'RH', 'P', 'H-Sur', 'Height', 'EL',
                  'AZ', 'WD', 'WS']
    radio_units = dict(zip(df.columns.to_list(),
                           ['sec', 'degC', '%', 'hPa', 'm', 'm', 'deg', 'deg', 'deg',
                            'knots']))
    # iterate over the cols and change all to numeric(or timedelta) values:
    for col in df.columns:
        if col == 'Time':
            df[col] = pd.to_timedelta(df[col], errors='coerce')
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # filter all entries that the first col is not null:
    df = df[~df.loc[:, 'Time'].isnull()]
    # get the minimum and maximum times:
    min_time = dt
    max_time = dt + df['Time'].iloc[-1]
    # reindex with datetime:
    df['datetime_index'] = df['Time'] + dt
    df = df.set_index('datetime_index')
    sound_time = check_sound_time(df)
    # now, convert Time to decimal seconds:
    df['Time'] = df['Time'] / np.timedelta64(1, 's')
#    # finally, add time delta to inital date and index:
#    df.Time = dt + df.Time
#    df = df.set_index('Time')
#    df.index.name = 'time'
    # calculate total precipitaple water(tpw):
#    ds_h['sound_time'] = check_sound_time(df)
    ds = df_to_ds_and_interpolate(df)
    # add meta data:
    for name in ds.data_vars:
        ds[name].attrs['units'] = radio_units[name]
    # add more fields:
    ds['Dewpt'] = wrap_xr_metpy_dewpoint(ds['T'], ds['RH'])
    ds['Dewpt'].attrs['long_name'] = 'Dew point'
    ds['MR'] = wrap_xr_metpy_mixing_ratio(ds['P'], ds['T'], ds['RH'])
    ds['MR'].attrs['long_name'] = 'Water vapor mass mixing ratio'
    ds['VP'] = wrap_xr_metpy_vapor_pressure(ds['P'], ds['MR'])
    ds['VP'].attrs['long_name'] = 'Water vapor partial pressure'
#        df_extra['sound_time'] = sound_time
    ds['sound_time'] = sound_time
    ds['min_time'] = min_time
    ds['max_time'] = max_time
    ds['cloud_code'] = cloud_code
    ds['sonde_type'] = sonde_type
#        df_extra = df_extra.set_index('sound_time')
#        ds_extra = df_extra.to_xarray()
#        # add meta date to new fields:
#        for name in ds_extra.data_vars:
#            if 'time' not in name:
#                ds_extra[name].attrs['units'] = meta['units_extra'][name]
    # finally, merge all ds:
#        ds = xr.merge([ds, ds_extra])
    ds.attrs['station_number'] = station_num
    ds.attrs['lat'] = 32.01
    ds.attrs['lat'] = 34.81
    ds.attrs['alt'] = 31.0
    ds['Height'].attrs['units'] = 'm'
    return ds


def classify_clouds_from_sounding(sound_path=sound_path):
    import xarray as xr
    import numpy as np
    da = xr.open_dataarray(sound_path / 'ALL_bet_dagan_soundings.nc')
    ds = da.to_dataset(dim='var')
    cld_list = []
    for date in ds.time:
        h = ds['HGHT'].sel(time=date).dropna('mpoint').values
        T = ds['TEMP'].sel(time=date).dropna('mpoint').values
        dwT = ds['DWPT'].sel(time=date).dropna('mpoint').values
        h = h[0: len(dwT)]
        cld = np.empty(da.mpoint.size, dtype='float')
        cld[:] = np.nan
        T = T[0: len(dwT)]
        try:
            dT = np.abs(T - dwT)
        except ValueError:
            print('valueerror')
            cld_list.append(cld)
            continue
        found = h[dT < 0.5]
        found_pos = np.where(dT < 0.5)[0]
        if found.any():
            for i in range(len(found)):
                if found[i] < 2000:
                    cld[found_pos[i]] = 1.0  # 'LOW' clouds
                elif found[i] < 7000 and found[i] > 2000:
                    cld[found_pos[i]] = 2.0  # 'MIDDLE' clouds
                elif found[i] < 13000 and found[i] > 7000:
                    cld[found_pos[i]] = 3.0  # 'HIGH' clouds
        cld_list.append(cld)
    ds['CLD'] = ds['HGHT'].copy(deep=False, data=cld_list)
    ds.to_netcdf(sound_path / 'ALL_bet_dagan_soundings_with_clouds.nc', 'w')
    print('ALL_bet_dagan_soundings_with_clouds.nc saved to {}'.format(sound_path))
    return ds


def compare_interpolated_to_real(Tint, date='2014-03-02T12:00',
                                 sound_path=sound_path):
    from metpy.plots import SkewT
    from metpy.units import units
    import pandas as pd
    import xarray as xr
    import matplotlib.pyplot as plt
    da = xr.open_dataarray(sound_path / 'ALL_bet_dagan_soundings.nc')
    p = da.sel(time=date, var='PRES').values * units.hPa
    dt = pd.to_datetime(da.sel(time=date).time.values)
    T = da.sel(time=dt, var='TEMP').values * units.degC
    Tm = Tint.sel(time=dt).values * units.degC
    pm = Tint['pressure'].values * units.hPa
    fig = plt.figure(figsize=(9, 9))
    title = da.attrs['description'] + ' ' + dt.strftime('%Y-%m-%d')
    skew = SkewT(fig)
    skew.plot(p, T, 'r', linewidth=2)
    skew.plot(pm, Tm, 'g', linewidth=2)
    skew.ax.set_title(title)
    skew.ax.legend(['Original', 'Interpolated'])
    return


def average_meteogram(sound_path=sound_path, savepath=None):
    import xarray as xr
    import numpy as np
    from scipy.interpolate import interp1d
    da = xr.open_dataarray(sound_path / 'ALL_bet_dagan_soundings.nc')
    # pressure = np.linspace(1010, 20, 80)
    height = da.sel(var='HGHT').isel(time=0).dropna('mpoint').values
    T_list = []
    for i in range(da.time.size):
        x = da.isel(time=i).sel(var='HGHT').dropna('mpoint').values
        y = da.isel(time=i).sel(var='TEMP').dropna('mpoint').values
        x = x[0: len(y)]
        f = interp1d(x, y, kind='linear', fill_value='extrapolate')
        T_list.append(f(height))
    T = xr.DataArray(T_list, dims=['time', 'height'])
    ds = T.to_dataset(name='temperature')
    ds['height'] = height
    ds['time'] = da.time
    ds['temperature'].attrs['units'] = 'degC'
    ds['temperature'] = ds['temperature'].where(ds['temperature'].isel(height=0)>-13,drop=True)
    ds['height'].attrs['units'] = 'm'
    ts_list = [ds['temperature'].isel(height=0).sel(time=x) + 273.15 for x in
               ds.time]
    tm_list = [Tm(ds['temperature'].sel(time=x), from_raw_sounding=False)
               for x in ds.time]
    tm = xr.DataArray(tm_list, dims='time')
    tm.attrs['description'] = 'mean atmospheric temperature calculated by water vapor pressure weights'
    tm.attrs['units'] = 'K'
    ts = xr.concat(ts_list, 'time')
    ts.attrs['description'] = 'Surface temperature from BET DAGAN soundings'
    ts.attrs['units'] = 'K'
    hours = [12, 0]
    hr_dict = {12: 'noon', 0: 'midnight'}
    seasons = ['DJF', 'SON', 'MAM', 'JJA']
    for season in seasons:
        for hour in hours:
            da = ds['temperature'].sel(time=ds['time.season'] == season).where(
                ds['time.hour'] == hour).dropna('time').mean('time')
            name = ['T', season, hr_dict[hour]]
            ds['_'.join(name)] = da
    ds['season'] = ds['time.season']
    ds['hour'] = ds['time.hour'].astype(str)
    ds['hour'] = ds.hour.where(ds.hour != '12', 'noon')
    ds['hour'] = ds.hour.where(ds.hour != '0', 'midnight')
    ds['ts'] = ts
    ds['tm'] = tm
    ds = ds.dropna('time')
    if savepath is not None:
        filename = 'bet_dagan_sounding_pw_Ts_Tk1.nc'
        print('saving {} to {}'.format(filename, savepath))
        comp = dict(zlib=True, complevel=9)  # best compression
        encoding = {var: comp for var in ds}
        ds.to_netcdf(savepath / filename, 'w', encoding=encoding)
    print('Done!')
    return ds


def plot_skew(sound_path=sound_path, date='2018-01-16T12:00', two=False):
    from metpy.plots import SkewT
    from metpy.units import units
    import matplotlib.pyplot as plt
    import pandas as pd
    import xarray as xr
    da = xr.open_dataarray(sound_path / 'ALL_bet_dagan_soundings.nc')
    p = da.sel(time=date, var='PRES').values * units.hPa
    dt = pd.to_datetime(da.sel(time=date).time.values)
    if not two:
        T = da.sel(time=date, var='TEMP').values * units.degC
        Td = da.sel(time=date, var='DWPT').values * units.degC
        Vp = VaporPressure(da.sel(time=date, var='TEMP').values) * units.Pa
        dt = pd.to_datetime(da.sel(time=date).time.values)
        fig = plt.figure(figsize=(9, 9))
        title = da.attrs['description'] + ' ' + dt.strftime('%Y-%m-%d %H:%M')
        skew = SkewT(fig)
        skew.plot(p, T, 'r', linewidth=2)
        skew.plot(p, Td, 'g', linewidth=2)
        # skew.ax.plot(p, Vp, 'k', linewidth=2)
        skew.ax.set_title(title)
        skew.ax.legend(['Temp', 'Dewpoint'])
    elif two:
        dt1 = pd.to_datetime(dt.strftime('%Y-%m-%dT00:00'))
        dt2 = pd.to_datetime(dt.strftime('%Y-%m-%dT12:00'))
        T1 = da.sel(time=dt1, var='TEMP').values * units.degC
        T2 = da.sel(time=dt2, var='TEMP').values * units.degC
        fig = plt.figure(figsize=(9, 9))
        title = da.attrs['description'] + ' ' + dt.strftime('%Y-%m-%d')
        skew = SkewT(fig)
        skew.plot(p, T1, 'r', linewidth=2)
        skew.plot(p, T2, 'b', linewidth=2)
        # skew.ax.plot(p, Vp, 'k', linewidth=2)
        skew.ax.set_title(title)
        skew.ax.legend(['Temp at ' + dt1.strftime('%H:%M'),
                        'Temp at ' + dt2.strftime('%H:%M')])
    return


#def es(T):
#    """ARM function for water vapor saturation pressure"""
#    # T in celsius:
#    import numpy as np
#    es = 6.1094 * np.exp(17.625 * T / (T + 243.04))
#    # es in hPa
#    return es

def run_pyigra_save_xarray(station, path=sound_path):
    import subprocess
    filepath = path / 'igra_{}_raw.txt'.format(station)
    command = '/home/ziskin/miniconda3/bin/PyIGRA --id {} -o {}'.format(station,filepath)
    subprocess.call([command], shell=True)
    # pyigra_to_xarray(station + '_pt.txt', path=path)
    return


def pyigra_to_xarray(station, path=sound_path):
    import pandas as pd
    import xarray as xr
    # import numpy as np
    filepath = path / 'igra_{}_raw.txt'.format(station)
    df = pd.read_csv(filepath, delim_whitespace=True, na_values=[-9999.0, 9999])
    dates = df['NOMINAL'].unique().tolist()
    print('splicing dataframe and converting to xarray dataset...')
    ds_list = []
    for date in dates:
        dff = df.loc[df.NOMINAL == date]
        # release = dff.iloc[0, 1]
        dff = dff.drop(['NOMINAL', 'RELEASE'], axis=1)
        dss = dff.to_xarray()
        dss = dss.drop('index')
        dss = dss.rename({'index': 'point'})
        dss['point'] = range(dss.point.size)
        # dss.attrs['release'] = release
        ds_list.append(dss)
    print('concatenating to time-series dataset')
    datetimes = pd.to_datetime(dates, format='%Y%m%d%H')
    # max_ind = np.max([ds.index.size for ds in ds_list])
    # T = np.nan * np.ones((len(dates), max_ind))
    # P = np.nan * np.ones((len(dates), max_ind))
    # for i, ds in enumerate(ds_list):
    #     tsize = ds['TEMPERATURE'].size
    #     T[i, 0:tsize] = ds['TEMPERATURE'].values
    #     P[i, 0:tsize] = ds['PRESSURE'].values
    # Tda = xr.DataArray(T, dims=['time', 'point'])
    # Tda.name = 'Temperature'
    # Tda.attrs['units'] = 'deg C'
    # Tda['time'] = datetimes
    # Pda = xr.DataArray(P, dims=['time', 'point'])
    # Pda.name = 'Pressure'
    # Pda.attrs['units'] = 'hPa'
    # Pda['time'] = datetimes
    # ds = Tda.to_dataset(name='Temperature')
    # ds['Pressure'] = Pda
    units = {'PRESSURE': 'hPa', 'TEMPERATURE': 'deg_C', 'RELHUMIDITY': '%',
             'DEWPOINT': 'deg_C', 'WINDSPEED': 'm/sec',
             'WINDDIRECTION': 'azimuth'}
    ds = xr.concat(ds_list, 'time')
    ds['time'] = datetimes
    for da, unit in units.items():
        ds[da].attrs['unit'] = unit
    ds.attrs['name'] = 'radiosonde soundings from IGRA'
    ds.attrs['station'] = station
    filename = 'igra_{}.nc'.format(station)
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in ds.data_vars}
    ds.to_netcdf(path / filename, 'w', encoding=encoding)
    print('saved {} to {}.'.format(filename, path))
    return ds


def process_mpoint_da_with_station_num(path=sound_path, station='08001', k_iqr=1):
    from aux_gps import path_glob
    import xarray as xr
    from aux_gps import keep_iqr
    file = path_glob(sound_path, 'ALL*{}*.nc'.format(station))
    da = xr.open_dataarray(file[0])
    ts, tm, tpw = calculate_ts_tm_tpw_from_mpoint_da(da)
    ds = xr.Dataset()
    ds['Tm'] = xr.DataArray(tm, dims=['time'], name='Tm')
    ds['Tm'].attrs['unit'] = 'K'
    ds['Tm'].attrs['name'] = 'Water vapor mean atmospheric temperature'
    ds['Ts'] = xr.DataArray(ts, dims=['time'], name='Ts')
    ds['Ts'].attrs['unit'] = 'K'
    ds['Ts'].attrs['name'] = 'Surface temperature'
    ds['Tpw'] = xr.DataArray(tpw, dims=['time'], name='Tpw')
    ds['Tpw'].attrs['unit'] = 'mm'
    ds['Tpw'].attrs['name'] = 'precipitable_water'
    ds['time'] = da.time
    ds = keep_iqr(ds, k=k_iqr, dim='time')
    yr_min = ds.time.min().dt.year.item()
    yr_max = ds.time.max().dt.year.item()
    ds = ds.rename({'time': 'sound_time'})
    filename = 'station_{}_soundings_ts_tm_tpw_{}-{}.nc'.format(station, yr_min, yr_max)
    print('saving {} to {}'.format(filename, path))
    comp = dict(zlib=True, complevel=9)  # best compression
    encoding = {var: comp for var in ds}
    ds.to_netcdf(path / filename, 'w', encoding=encoding)
    print('Done!')
    return ds


def calculate_ts_tm_tpw_from_mpoint_da(da):
    """ calculate the atmospheric mean temperature and precipitable_water"""
    import numpy as np
    times_tm = []
    times_tpw = []
    times_ts = []
    station_num = [x for x in da.attrs['description'].split(' ') if x.isdigit()]
    print('calculating ts, tm and tpw from station {}'.format(station_num))
    ds = da.to_dataset('var')
    for itime in range(ds.time.size):
        tempc = ds['TEMP'].isel(time=itime).dropna('mpoint').reset_coords(drop=True)
        # dwptc = ds['DWPT'].isel(time=itime).dropna('mpoint').reset_coords(drop=True)
        hghtm = ds['HGHT'].isel(time=itime).dropna('mpoint').reset_coords(drop=True)
        preshpa = ds['PRES'].isel(time=itime).dropna('mpoint').reset_coords(drop=True)   # in hPa
        WVpress = VaporPressure(tempc, units='hPa', method='Buck')
        Mixratio = MixRatio(WVpress, preshpa)  # both in hPa
        tempk = tempc + 273.15
        Rho = DensHumid(tempc, preshpa, WVpress, out='both')
        specific_humidity = (Mixratio / 1000.0) / \
             (1 + 0.001 * Mixratio / 1000.0)
        try:
            numerator = np.trapz(WVpress / tempk, hghtm)
            denominator = np.trapz(WVpress / tempk**2.0, hghtm)
            tm = numerator / denominator
        except ValueError:
            tm = np.nan
        try:
            tpw = np.trapz(specific_humidity * Rho, hghtm)
        except ValueError:
            tpw = np.nan
        times_tm.append(tm)
        times_tpw.append(tpw)
        times_ts.append(tempk[0].values.item())
    Tm = np.array(times_tm)
    Ts = np.array(times_ts)
    Tpw = np.array(times_tpw)
    return Ts, Tm, Tpw


def MixRatio(e, p):
    """Mixing ratio of water vapour
    INPUTS
    e (Pa) Water vapor pressure
    p (Pa) Ambient pressure
    RETURNS
    qv (g kg^-1) Water vapor mixing ratio`
    """
    MW_dry_air = 28.9647  # gr/mol
    MW_water = 18.015  # gr/mol
    Epsilon = MW_water / MW_dry_air  # Epsilon=Rs_da/Rs_v;
    # The ratio of the gas constants
    return 1000 * Epsilon * e / (p - e)


def DensHumid(tempc, pres, e, out='dry_air'):
    """Density of moist air.
    This is a bit more explicit and less confusing than the method below.
    INPUTS:
    tempc: Temperature (C)
    pres: static pressure (hPa)
    e: water vapor partial pressure (hPa)
    OUTPUTS:
    rho_air (kg/m^3)
    SOURCE: http://en.wikipedia.org/wiki/Density_of_air
    """
    tempk = tempc + 273.15
    prespa = pres * 100.0
    epa = e * 100.0
    Rs_v = 461.52  # Specific gas const for water vapour, J kg^{-1} K^{-1}
    Rs_da = 287.05  # Specific gas const for dry air, J kg^{-1} K^{-1}
    pres_da = prespa - epa
    rho_da = pres_da / (Rs_da * tempk)
    rho_wv = epa/(Rs_v * tempk)
    if out == 'dry_air':
        return rho_da
    elif out == 'wv_density':
        return rho_wv
    elif out == 'both':
        return rho_da + rho_wv


def VaporPressure(tempc, phase="liquid", units='hPa', method=None):
    import numpy as np
    """Water vapor pressure over liquid water or ice.
    INPUTS:
    tempc: (C) OR dwpt (C), if SATURATION vapour pressure is desired.
    phase: ['liquid'],'ice'. If 'liquid', do simple dew point. If 'ice',
    return saturation vapour pressure as follows:
    Tc>=0: es = es_liquid
    Tc <0: es = es_ice
    RETURNS: e_sat  (Pa) or (hPa) units parameter choice
    SOURCE: http://cires.colorado.edu/~voemel/vp.html (#2:
    CIMO guide (WMO 2008), modified to return values in Pa)
    This formulation is chosen because of its appealing simplicity,
    but it performs very well with respect to the reference forms
    at temperatures above -40 C. At some point I'll implement Goff-Gratch
    (from the same resource).
    """
    if units == 'hPa':
        unit = 1.0
    elif units == 'Pa':
        unit = 100.0
    if method is None:
        over_liquid = 6.112 * np.exp(17.67 * tempc / (tempc + 243.12)) * unit
        over_ice = 6.112 * np.exp(22.46 * tempc / (tempc + 272.62)) * unit
    elif method == 'Buck':
        over_liquid = 6.1121 * \
            np.exp((18.678 - tempc / 234.5) * (tempc / (257.4 + tempc))) * unit
        over_ice = 6.1125 * \
            np.exp((23.036 - tempc / 333.7) * (tempc / (279.82 + tempc))) * unit
    # return where(tempc<0,over_ice,over_liquid)

    if phase == "liquid":
        # return 6.112*exp(17.67*tempc/(tempc+243.12))*100.
        return over_liquid
    elif phase == "ice":
        # return 6.112*exp(22.46*tempc/(tempc+272.62))*100.
        return np.where(tempc < 0, over_ice, over_liquid)
    else:
        raise NotImplementedError


def dewpoint(e):
    """Calculate the ambient dewpoint given the vapor pressure.

    Parameters
    ----------
    e : Water vapor partial pressure in mb (hPa)
    Returns
    -------
    Dew point temperature in deg_C
    See Also
    --------
    dewpoint_rh, saturation_vapor_pressure, vapor_pressure
    Notes
    -----
    This function inverts the [Bolton1980]_ formula for saturation vapor
    pressure to instead calculate the temperature. This yield the following
    formula for dewpoint in degrees Celsius:

    .. math:: T = \frac{243.5 log(e / 6.112)}{17.67 - log(e / 6.112)}

    """
    import numpy as np
    # units are degC
    sat_pressure_0c = 6.112  # in millibar
    val = np.log(e / sat_pressure_0c)
    return 243.5 * val / (17.67 - val)


def dewpoint_rh(temperature, rh):
    """Calculate the ambient dewpoint given air temperature and relative
    humidity.
    Parameters
    ----------
    temperature : in deg_C
        Air temperature
    rh : in %
        Relative Humidity
    Returns
    -------
       The dew point temperature
    See Also
    --------
    dewpoint, saturation_vapor_pressure
    """
    import numpy as np
    import warnings
    if np.any(rh > 120):
        warnings.warn('Relative humidity >120%, ensure proper units.')
    return dewpoint(rh / 100.0 * VaporPressure(temperature, units='hPa',
                    method='Buck'))

#def ea(T, rh):
#    """water vapor pressure function using ARM function for sat."""
#    # rh is relative humidity in %
#    return es(T) * rh / 100.0
