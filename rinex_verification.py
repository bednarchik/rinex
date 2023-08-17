# -*- coding: utf-8 -*-
__author__ = 'Ricardo Vidal'
"""
Script works like this:
1. For each GPS system it reads csv processed rinex files from canadian website
2. Reads the TRINAV/SPN logged file containing raw (not offset corrected) positions as output by Fugro/Veripos
3. creates a pandas dataframe for the rinex file and for the TRINAV/SPN file
    3.1. On both rinex and TRINAV/SPN file identifies the GPS Time columns and calculates seconds into the present day - new column
    3.2. On TRINAV/SPN file identifies the lat & lon columns and converts them to decimal degree
4. Merges dataframes from rinex and TRINAV/SPN based on gps_seconds column
5. Obtains lat/lon differences in [degrees] and converts them in [m]. It is expected that the lat lon are in WGS-84
6. Statistics are calculated
6. The differences in lat/lon in [m] are plotted with matplotlib.
7. Gyros also plotted 
8. Plots and statistics are output to pdf

Assumptions:

in TRINAV/SPN file:
    A string containing 'lat', 'Lat' or 'LAT' is expected in a column with the GPS system name
    A string containing 'gyro', 'Gyro', 'THDG' is expected in at least one column for plotting gyro data
    TRINAV file contains a column called 'Time' and is a gps time string as output by QCPR
    SPN file contains a column with the string 'GPSTIME', which contains the gps time in seconds for a day only
    
--If this script needs maintaining contact any of the following people:
Ricardo Vidal
Aziz Wayudin
Martin Empsall
Fernando Gonzalez

--Virtualenv
a virtualenv 'rinexx' is supplied with the minimum python modules for building the exe. 
1. put the virtualenv in c:/virtualenv/rinexx
2. from your cmd execute c:\virtualenv\rinexx\Scripts\activate
3. cd to the root of your project
4. run script as source\rinex_verification.py


--For packaging into .exe file using pyInstaller:

1. keep the directory structure where this file is in /source directory
2. follow instructions at the head of file README.md
3. if the help needs modifying, do that in the word document and output a help.pdf file in /source
4. do not delete or move logo or help file, nor the .spec and README file 
5 .exe will be output in /dist directory. That .exe can be taken alone and distributed.

--TO DO

1. improvements in the code: 
- get rid of so many inline functions
- split long funtions like read_file_csv() which not only reads the files but merges the dataframes
2. produce height difference? (what for??)
3. run it in Red Hat?

"""

import os
import sys
import subprocess
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
from fpdf import FPDF
import datetime

pd.options.display.width = 0
STAGE= 'production'
#STAGE= 'testing'
VERSION= 'Version 2.1 - Feb 2023'




# ----- for pyinstaller
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    if STAGE == 'testing':
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ----- produces a timetag to append to report name
def timetag():
    now = datetime.datetime.now()
    return str(now.year) + str(now.month).zfill(2) + str(now.day).zfill(2) + "_" +  str(now.hour).zfill(2) + str(now.minute).zfill(2) + str(now.second).zfill(2)

# ----- helper funtion to convert a gps epoch into datetime
def gps2time(gpstime):
    GPS_EPOCH = datetime.datetime(1980, 1, 6)
    return GPS_EPOCH + datetime.timedelta(seconds=gpstime)

# ----- reverse helper funtion to convert a datetime into gps epoch
def time2gps(dat):
    GPS_EPOCH = datetime.datetime(1980, 1, 6)
    delta = dat - GPS_EPOCH
    return (delta.days * 24 * 60 * 60) + delta.seconds

# ----- helper function to convert a dms lat/lon to decimal degree
def dms_to_dec(_dms):
    dms = str(_dms)
    
    #----- SPN logs xx:xx:xxN, so put a space in between to better handle the dms string
    dms = dms.replace(":"," ")
    dms = dms.replace("E"," E")
    dms = dms.replace("N"," N")
    dms = dms.replace("W"," W")
    dms = dms.replace("S"," S")
          
    if len(dms.split()) < 3:
        return _dms
    else:
        
        deg = float(dms.split()[0])
        min = float(dms.split()[1])
        if len(dms.split()) == 4:
            sec = float(dms.split()[2])

        else:
            sec = 0
        if "S" in dms:
            return (deg + (min / 60) + (sec / 3600)) * (-1)
        elif "W" in dms:
            return (deg + (min / 60) + (sec / 3600)) * (-1)
        else:
            return deg + (min / 60) + (sec / 3600)

# ----- helper function to convert strings to float replacing empty strings with np.nan
# ----- not in use now, but might come handy for other logging systems
def to_float_np(s):
    if len(s) == 0:
        return np.nan
    else:
        return float(s)
        
# ----- helper function to convert strings to float
def to_float(s):
    return float(s)
    
# ----- helper function to convert decimal hours to hours, minutes and seconds
def dec_hour_to_hms(dec_hour):
    hours = int(dec_hour)
    minutes = int(60 * (dec_hour % 1))
    seconds = int(60 * (minutes % 1))
    return (str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2))

# ----- function to read start and stop of Rinex/Navigation logging period
def start_stop_df_m(df):
    reverse = 0
    
    # ----- slice a column as a list. get the first year and day. Use it for both start and end of matching records
    year = str(df.year[0])    
    day = str(df.day_of_year[0]).zfill(3)

    # ----- slice a column as a list. get the first and last decimal hour of matching records
    time_first = float(df.decimal_hour[0])
    time_last = float(df.decimal_hour[len(df)-1])
       
    hours, minutes, seconds = dec_hour_to_hms(time_first)
    first = datetime.datetime.strptime(year + '_' + day + '_' + hours + '_' + minutes + '_' + seconds, '%Y_%j_%H_%M_%S')
    #print(year + '_' + day + '_' + hours + '_' + minutes + '_' + seconds)
   
    hours, minutes, seconds = dec_hour_to_hms(time_last)
    last = datetime.datetime.strptime(year + '_' + day + '_' + hours + '_' + minutes + '_' + seconds, '%Y_%j_%H_%M_%S')
    #print(year + '_' + day + '_' + hours + '_' + minutes + '_' + seconds)
    
    if time_first > time_last:
        reverse = 1
        start = last
        stop = first
    else:
        reverse = 0
        start = first
        stop = last
        
    return [start, stop, reverse]

# ----- helper function to get full column name of a dataframe based on one string occurrence and a list of strings
def column_name(df, str1, strings):
    column_n =''
    for column in df.columns:
        if str1 in column:
           for s in strings:
               if  s in column:
                   column_n = column
    return column_n  

# ----- helper function to get full column name of a dataframe based on a list of strings
def column_name_single(df, strings):
    column_n =''
    for column in df.columns:

       for s in strings:
           if  s in column:
               column_n = column
    return column_n 

# ----- function to read the rinex files and the navigation file
def read_file_csv(fr, ft, system, NAV):

    # -----------read the rinex file using python engine to use regex as delimiter
    df_r = pd.read_csv(fr, sep='\s*,\s*', engine='python')
    
    # -----------read the nav file using python engine to use regex as delimiter    
    if 'TRINAV' in NAV:
        df_n = pd.read_csv(ft, sep='\s*,\s* ', engine='python')

        # -----------TRINAV file is logged with an extra comma in the name when logged from rtDisplay, but not from QCPR
        # -----------Get rid of the trailing comma in the first case
        if ',' in (df_n.columns[-1]): 
            df_n = df_n.rename(columns=({df_n.columns[-1]: df_n.columns[-1][:-1]}))
            
        # -----------TRINAV file is logged with an extra trailing comma when logged from rtDisplay, AND from QCPR
        #------------Get rid of the comma if in the data  
        #------------Horrible lambda!!!!, should be a def, (TODO)       
        df_n[df_n.columns[-1]] = df_n[df_n.columns[-1]].apply(lambda s: s[:-1] if ',' in s else s)
    
    else:
        df_n = pd.read_csv(ft, sep='\s*,\s*', engine='python')
 
    #print(df_n)
    
    # -----------convert gyro strings into float64
    if 'TRINAV' in NAV:
        if 'Gyro' in df_n.columns[-1] or 'gyro' in df_n.columns[-1]:
            df_n[df_n.columns[-1]] = df_n[df_n.columns[-1]].apply(to_float)
    else:
        if 'THDG' in df_n.columns[-1]:
            df_n[df_n.columns[-1]] = df_n[df_n.columns[-1]].apply(to_float)
            
                            
    # -----------convert lat lon strings into dms float64
    for key, value in df_n.dtypes.items():
        for s in ['lat','Lat','LAT','lon','Lon','LON']:         
            if s in key:
                df_n[key] = df_n[key].apply(dms_to_dec)                
            

    # # # -----------convert time to decimal day 
    # df_r['decimal_day'] = df_r['decimal_hour'].apply(lambda x: round(float(x) / 24, 6))
    
    # if 'TRINAV' in NAV:
        # df_n['decimal_day'] = df_n['Time'].apply(lambda x: round((float(x) % 86400) / 86400, 6))
    # else:
        # name_column_gpstime = column_name_single(df_n, ['GPSTIME'])
        # #----- SPN is a gps time seconds into the current gps week
        # df_n['decimal_day'] = df_n[name_column_gpstime].apply(lambda x: round((float(x) % 86400) / 86400, 6))
     
               
    # # -----------merge Navigation and rinex files by decimal_day, that is, by matching time
    # df_m = pd.merge(df_r, df_n, how='inner', left_on='decimal_day', right_on='decimal_day')
  
  
    # -----------convert time to gps seconds of the day 
    df_r['day_seconds'] = df_r['decimal_hour'].apply(lambda x: int(round(float(x) * 3600, 1)))
   
    # -----------convert time to gps seconds of the day 
    if 'TRINAV' in NAV:
        df_n['day_seconds'] = df_n['Time'].apply(lambda x: (int(x) % 86400))
    else:
        name_column_gpstime = column_name_single(df_n, ['GPSTIME'])
        #----- SPN is gps time seconds into the current gps week
        df_n['day_seconds'] = df_n[name_column_gpstime].apply(lambda x: (int(x) % 86400))
    #print (df_r['day_seconds'], df_n['day_seconds'])      

        
    # -----------merge Navigation and rinex files by decimal_day, that is, by matching time
    df_m = pd.merge(df_r, df_n, how='inner', left_on='day_seconds', right_on='day_seconds')


    # -----------if there is no matching time between Navigation and rinex exit with a message.
    if len(df_m) == 0: 
        tk.messagebox.showerror(title="No matching Epoch", message="The rinex file and the Navigation log \n do not have matching times")
        exit
    
    # -----------reverse the dataframe for plotting from earlier to later date
    first, last, reverse = start_stop_df_m (df_m)
    if reverse == 1:
        df_m = df_m[::-1]

    # -----------output dataframe to csv for testing
    df_m.to_csv('C:/tmp/combined_data.csv', sep=',', encoding='utf-8', index=False)

    # -----------lat and lon factor degree->metres --(the maths are taken from Willy's original spreadsheet)
    lat_mean = df_m['latitude_decimal_degree'].mean()
    f = 1 / 298.257223563
    sq_ex = f * (2 + f) / (1 - f) ** 2
    v2 = 1 + ((sq_ex ** 2) * math.cos(lat_mean / 180 * math.pi))
    c = 6378137 / (1 - f)
    lat_factor = c * math.pi / (v2 ** 1.5) / 180
    lon_factor = lat_factor * math.cos(lat_mean * math.pi / 180)

    # -----------diff the systems
    name_column_lat = column_name(df_n, system, ['LAT', 'lat', 'Lat'])
    name_column_lon = column_name(df_n, system, ['LON', 'lon', 'Lon'])     

    df_m[system + '_lat_diff'] = df_m['latitude_decimal_degree'] - df_m[name_column_lat]
    df_m[system + '_lon_diff'] = df_m['longitude_decimal_degree'] - df_m[name_column_lon]
       
    df_m[system + '_lat_diff'] = df_m[system + '_lat_diff'].apply(lambda x: x * lat_factor) 
    df_m[system + '_lon_diff'] = df_m[system + '_lon_diff'].apply(lambda x: x * lon_factor)

    # -----------convert 'Time' to datetime object and formate as HH:MM
    if 'TRINAV' in NAV:
        #-----------TRINAV
        df_m['Time'] = df_m['Time'].apply(lambda x: gps2time(float(x)).strftime("%H:%M"))
    else:
        #-----------SPN
        name_column_gpstime = column_name_single(df_n, ['GPSTIME'])        
        df_m['Time'] = df_m[name_column_gpstime].apply(lambda x: gps2time(float(x)).strftime("%H:%M"))

    df_m.to_csv('C:/tmp/combined_data.csv', sep=',', encoding='utf-8', index=False)


    return df_m

# -----------function to get statistics from each difference rinex-navigation
def stats(df, system, type):
    return df[system + '_' + type + '_diff'].describe()

# -----------function to plot the gyros vs time
def plot_gyros(df):

    # -----------create axes to reuse
    plt.rcParams.update({'font.size': 6})

    ax = plt.gca()
    w = 5
    l = 3

    # -----------set title, axis labels and scale, grid
    plt.title('Gyro heading ')
    plt.xlabel('Time [hh:mm]')
    plt.ylabel('Bearing [°]')
    # -----------set y-axis scale
    average = 0
    minvalue = 0
    maxvalue = 0

    # -----------plot Gyros
    for column in df.columns:
        if 'Gyro' in column or 'gyro' in column or 'THDG' in column:
            try:
                minvalue = int(df[column].min())
                maxvalue = int(df[column].max())
                average = int(df[column].mean())
                df.plot(figsize=(w, l), kind='line', x='Time', y=column, linewidth=1, ax=ax)
            except:
                pass
    plt.ylim(minvalue - 10, maxvalue + 10)
    plt.grid()

    plt.xlabel('Time [hh:mm]')

    plt.savefig('gyros.png')

    # -----------clear current figure
    plt.clf()

# -----------function to plot the difference between a rinex file and navigation log
def plot_diff(df, system):

    # -----------create axes to reuse
    plt.rcParams.update({'font.size': 6})

    ax = plt.gca()
    w = 5
    l = 3
    # -----------plot the time series
    df.plot(figsize=(w, l), kind='line', x='Time', y=system + '_lat_diff', color='red', linewidth=0.15, ax=ax)
    df.plot(figsize=(w, l), kind='line', x='Time', y=system + '_lon_diff', color='blue', linewidth=0.15, ax=ax)

    # -----------set title, axis labels and scale, grid
    plt.title(system + ' - Difference between RINEX processed and NAVIGATION logged ')
    plt.xlabel('Time [hh:mm]')
    plt.ylabel('Difference [m]')
    
    # -----------set y-axis scale
    plt.ylim(-1, 1)
    plt.grid(.5)

    # -----------plt.show()
    plt.savefig(system + '.png')

    # -----------clear current figure
    plt.clf()

def add_logo(pdf):
    try:
        # -----------for pyisnstaller
        pdf.image(resource_path('logo.png'))
    except:
        # -----------for testing
        pdf.image('logo.png')

def cleanup(systems):
    # -----------remove the .png's produced by matplotlib
    try:
        os.remove('gyros.png') 
    except:
        pass
    for i, system in enumerate(systems):
        try: 
            os.remove(system + '.png')
        except:
            pass

# -----------function to produce report
def pdf_collect(systems, statistics, start_stop_times, descriptions, info, text_work_scope):
    #-----------This def will produce a pdf report using FPDF
    pdf = FPDF('P')
    
    # -----------Front page
    pdf.add_page()
    pdf.set_xy(10, 0)
    pdf.set_font('arial', 'B', 36)
    pdf.set_text_color(68, 68, 68)
    pdf.ln(15)
    pdf.cell(120, 12, "", 0, 0, 'C')
    pdf.image(resource_path('logo.png'))
    #pdf.image('logo.png')
    pdf.ln(25)
    #pdf.image('./files/SW_Amundsen.png')
    pdf.ln(25)
    pdf.cell(180, 20, "DGNSS Verification - RINEX", 0, 1, 'C')
    pdf.ln(20)
    pdf.set_font('arial', 'B', 20)
    pdf.cell(180, 15, info[0], 0, 2, 'C')
    pdf.cell(180, 15, info[1], 0, 2, 'C')
    pdf.cell(180, 15, info[2], 0, 2, 'C')
    pdf.cell(180, 15, info[3], 0, 2, 'C')

    # -----------Second page introductory
    pdf.add_page()
    pdf.set_xy(10, 0)
    pdf.ln(15)

    pdf.cell(120, 12, "", 0, 0, 'C')
    pdf.image(resource_path('logo.png'))

    pdf.ln(10)
    pdf.cell(10, 12, "", 0, 0, 'C')
    pdf.set_font('arial', 'B', 14)
    pdf.set_text_color(68, 68, 68)
    pdf.cell(20, 20, "Scope of Work:", 0, 1, 'C')
    pdf.set_font('arial', '', 9)
    pdf.set_text_color(78, 78, 78)

    pdf.multi_cell(170, 6, text_work_scope, 0)

    for i, system in enumerate(systems):
        try:
            start_logging = start_stop_times[system][0].strftime('%d-%m-%Y at %H:%M:%S')
            stop_logging = start_stop_times[system][1].strftime('%d-%m-%Y at %H:%M:%S')
            pdf.add_page()
            pdf.set_xy(10, 0)
            pdf.set_font('arial', 'B', 16)
            pdf.ln(5)
            pdf.cell(120, 12, "", 0, 0, 'C')
            # pdf.image('logo.png')
            pdf.image(resource_path('logo.png'))
            pdf.ln(5)
            pdf.cell(180, 12, "DGNSS Verification - RINEX", 0, 2, 'C')
            pdf.ln(5)
            pdf.set_font('arial', "", 12)
            pdf.cell(160, 8, '                 System  : ' + system + ' - ' + descriptions[i], 0, 2, 'L')
            pdf.cell(160, 8, '                 Start logging  : ' + start_logging, 0, 2, 'L')
            pdf.cell(160, 8, '                 Stop logging  : ' + stop_logging, 0, 2, 'L')
            pdf.ln(3)
            pdf.image(system + '.png')
            pdf.ln(3)
            pdf.set_font('arial', 'B', 12)

            pdf.cell(75, 10, "Statistics", 0, 2, 'C')
            pdf.cell(90, 10, " ", 0, 2, 'C')
            pdf.cell(25)
            pdf.cell(50, 10, 'Stat', 1, 0, 'C')
            pdf.cell(40, 10, 'Lat diff [m]', 1, 0, 'C')
            pdf.cell(40, 10, 'Lon diff [m]', 1, 1, 'C')
            pdf.set_font('arial', "", 11)
            names = {'max': 'Max', 'min': 'Min', 'mean': 'Mean', 'std': 'Std Dev', 'count': '# of obs'}
            for stat in ('max', 'min', 'mean', 'std', 'count'):
                pdf.cell(25)
                pdf.cell(50, 10, names[stat], 1, 0, 'C')
                if 'count' in stat:
                    pdf.cell(80, 10, str('{:.0f}'.format(statistics[system + '_lat'][stat])), 1, 1, 'C')
                else:
                    pdf.cell(40, 10, str('{:.4f}'.format(statistics[system + '_lat'][stat])), 1, 0, 'C')
                    pdf.cell(40, 10, str('{:.4f}'.format(statistics[system + '_lon'][stat])), 1, 1, 'C')
        except:
            pass

    # -----------extra page for gyro plot
    pdf.add_page()
    pdf.set_xy(10, 0)
    pdf.set_font('arial', 'B', 16)
    pdf.ln(5)
    pdf.cell(120, 12, "", 0, 0, 'C')
    # pdf.image('logo.png')
    pdf.image(resource_path('logo.png'))
    pdf.ln(5)
    pdf.cell(180, 12, "DGNSS Verification - RINEX", 0, 2, 'C')
    pdf.ln(5)
    pdf.set_font('arial', "", 12)
    pdf.cell(160, 8, '                 System  : Gyros', 0, 2, 'L')
    pdf.ln(3)
    pdf.image('gyros.png')
    pdf.ln(3)
    pdf.set_font('arial', 'B', 12)

    # -----------produce the actual report
    print (timetag())
    try:
        pdf.output('RINEX_verification_report' + timetag() + '.pdf', 'F')
    except:
        tk.messagebox.showerror(title="PDF open already", message="Please close the PDF produced on previous runs \nto overwrite it")

    try:
        subprocess.Popen(['RINEX_verification_report' + timetag() + '.pdf'], shell=True)
    except:
        pass


class Window(tk.Frame):
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.master = master
        self.init_window()

        # -----------create variables for files
        self.system_1 = 'FU1G4_XX'
        self.system_2 = 'FU1XP_XX'
        self.system_3 = 'FU2G4_XX'
        self.system_4 = 'FU2XP_XX'

        self.description_system_1 = 'FUGRO G4'
        self.description_system_2 = 'FUGRO XP'
        self.description_system_3 = 'FUGRO G4 NG'
        self.description_system_4 = 'FUGRO XP NG'

        self.file_1 = tk.StringVar()
        self.file_2 = tk.StringVar()
        self.file_3 = tk.StringVar()
        self.file_4 = tk.StringVar()
        self.file_navigation = tk.StringVar()

    def init_window(self):
        # -----------title of the master widget
        self.master.title("RINEX comparison with Trinav")

        # -----------widget takes the full space of the root window
        self.pack(fill=tk.BOTH, expand=1)

        # -----------labels
        self.lbl_vessel = tk.Label(self, text="Vessel:")
        self.lbl_location = tk.Label(self, text="Location:")
        self.lbl_client = tk.Label(self, text="Client:")
        self.lbl_jobno = tk.Label(self, text="Job number:")
        self.lbl_systems = tk.Label(self, text="Systems")
        self.lbl_descriptions = tk.Label(self, text="Descriptions")
        self.lbl1 = tk.Label(self, text="")
        self.lbl2 = tk.Label(self, text="")
        self.lbl3 = tk.Label(self, text="")
        self.lbl4 = tk.Label(self, text="")
        self.lbl_navigation = tk.Label(self, text="")
        self.lbl_text1= tk.Label(self, text="Scope of Work Section: THIS SECTION IS EDITABLE")
        self.lbl_text1["background"] = 'Azure'
        
        self.lbl_nav = tk.Label(self, text="Navigation System")
        self.lbl_version = tk.Label(self, text=VERSION)
        
        
        # -----------entry texts
        self.entry1 = tk.Entry(self)
        self.entry2 = tk.Entry(self)
        self.entry3 = tk.Entry(self)
        self.entry4 = tk.Entry(self)

        self.entry_description_1 = tk.Entry(self, width=30)
        self.entry_description_2 = tk.Entry(self, width=30)
        self.entry_description_3 = tk.Entry(self, width=30)
        self.entry_description_4 = tk.Entry(self, width=30)

        self.entry_vessel = tk.Entry(self, width=30)
        self.entry_location = tk.Entry(self, width=30)
        self.entry_client = tk.Entry(self, width=30)
        self.entry_jobno = tk.Entry(self, width=30)

        # -----------buttons
        self.helpButton = tk.Button(self, text="Help", command=self.client_help)
        self.quitButton = tk.Button(self, text="Exit  ", command=self.client_exit)
        self.openButton1 = tk.Button(self, text="Open RINEX processed file System 1", command=self.open_file_1)
        self.openButton2 = tk.Button(self, text="Open RINEX processed file System 2", command=self.open_file_2)
        self.openButton3 = tk.Button(self, text="Open RINEX processed file System 3", command=self.open_file_3)
        self.openButton4 = tk.Button(self, text="Open RINEX processed file System 4", command=self.open_file_4)
        self.openButton_navigation = tk.Button(self, text="Open NAVIGATION logged file    ", command=self.open_file_navigation)
        self.processButton = tk.Button(self, text="              PROCESS                  ", command=self.process)
        self.processButton.config(background='lightgray')

        # -----------Text boxes
        self.text1 = tk.Text(self, height=14, width=90, wrap=tk.WORD)

        # -----------Combo box
        self.nav = tk.StringVar()
        self.cb_nav = ttk.Combobox(self, textvariable=self.nav)
        self.cb_nav['values'] = ['TRINAV', 'SPN']
        self.cb_nav['state'] = 'readonly'
        self.nav = 'TRINAV'
        
        self.cb_nav.current(0)


        self.cb_nav.bind('<<ComboboxSelected>>', self.nav_changed)
        
        # -----------add default text to entry texts

        self.entry1.insert(10, "FU1G4_XX")
        self.entry2.insert(10, "FU1XP_XX")
        self.entry3.insert(10, "FU2G4_XX")
        self.entry4.insert(10, "FU2XP_XX")

       
        self.entry_description_1.insert(10, 'Starpack computations XP')
        self.entry_description_2.insert(10, 'Starpack computations G4')
        self.entry_description_3.insert(10, 'Starfix NG computations XP')
        self.entry_description_4.insert(10, 'Starfix NG computations G4')
        self.entry_vessel.insert(10, 'SW Amundsen')

        # -----------add default text to entry texts
        text_work_scope = 'This verification is performed by logging raw GNSS data in RINEX format, and having the data post processed by a recognised 3rd party.\n' \
                     'Shearwater\'s standard is to use the Natural Resources of Canada (NRCAN) online service for post processing RINEX data.\n\n' \
                     'Logged raw data RINEX data from GNSS receivers is uploaded directly from the vessel, and the processed result received back from NRCAN almost instantly.\n' \
                     'The post processed positions from each of the GNNS receivers are then compared with DGNSS generated positions logged in the NAVIGATION system.\n' \
                     'The comparison graphs are provided in this document and provide proof of the validity of the corrections and hence that the onboard installation is valid.\n' \
                     'Gyro plots are also provided to show movements of the vessel during logging.'

        self.text1.insert('1.0',text_work_scope)
        self.text1.config(background="Azure")

        # -----------place button on window
        self.openButton1.grid(column=3, row=1)
        self.openButton2.grid(column=3, row=2)
        self.openButton3.grid(column=3, row=3)
        self.openButton4.grid(column=3, row=4)
        self.openButton_navigation.grid(column=3, row=5)
        self.processButton.grid(column=3, row=8)
        self.helpButton.grid(column=3, row=10)
        self.quitButton.grid(column=3, row=11)

        # -----------place labels on window
        self.lbl_systems.grid(column=0, row=0)
        self.lbl_descriptions.grid(column=1, row=0)
        self.lbl1.grid(column=4, row=1)
        self.lbl2.grid(column=4, row=2)
        self.lbl3.grid(column=4, row=3)
        self.lbl4.grid(column=4, row=4)
        self.lbl_navigation.grid(column=4, row=5)
        
        self.lbl_nav.grid(column=0, row=7) 
        self.lbl_vessel.grid(column=0, row=8)
        self.lbl_location.grid(column=0, row=9)
        self.lbl_client.grid(column=0, row=10)
        self.lbl_jobno.grid(column=0, row=11)
        self.lbl_text1.grid(column=0, row=14)
        self.lbl_version.grid(column=0, row=23)

        # -----------place entries on window
        self.entry1.grid(column=0, row=1)
        self.entry2.grid(column=0, row=2)
        self.entry3.grid(column=0, row=3)
        self.entry4.grid(column=0, row=4)
        self.entry_description_1.grid(column=1, row=1, columnspan= 2)
        self.entry_description_2.grid(column=1, row=2, columnspan= 2)
        self.entry_description_3.grid(column=1, row=3, columnspan= 2)
        self.entry_description_4.grid(column=1, row=4, columnspan= 2)    
        self.entry_vessel.grid(column=1, row=8)
        self.entry_location.grid(column=1, row=9)
        self.entry_client.grid(column=1, row=10)
        self.entry_jobno.grid(column=1, row=11)
        
        # -----------place combo box in window      
        self.cb_nav.grid(column=1, row=7)        

        # -----------place text boxes on window
        self.text1.grid(column=0, row=15, columnspan=4)
        

        
    def nav_changed(self, event):
        self.nav = self.cb_nav.get()
        self.entry1.delete(0, tk.END)
        self.entry2.delete(0, tk.END)
        self.entry3.delete(0, tk.END)
        self.entry4.delete(0, tk.END)
        if 'TRINAV' in  self.nav:
            self.entry1.insert(10, "FU1G4_XX")
            self.entry2.insert(10, "FU1XP_XX")
            self.entry3.insert(10, "FU2G4_XX")
            self.entry4.insert(10, "FU2XP_XX")
        else:
            self.entry1.insert(10, "COR_SP1_XP_A")
            self.entry2.insert(10, "COR_SP1_G4_A")
            self.entry3.insert(10, "COR_NG_XP_B")
            self.entry4.insert(10, "COR_NG_G4_B")
        
    def open_file_1(self):
        self.file_1 = filedialog.askopenfilename()
        self.lbl1['text'] = self.file_1.split('/')[-1]

    def open_file_2(self):
        self.file_2 = filedialog.askopenfilename()
        self.lbl2['text'] = self.file_2.split('/')[-1]

    def open_file_3(self):
        self.file_3 = filedialog.askopenfilename()
        self.lbl3['text'] = self.file_3.split('/')[-1]

    def open_file_4(self):
        self.file_4 = filedialog.askopenfilename()
        self.lbl4['text'] = self.file_4.split('/')[-1]

    def open_file_navigation(self):
        self.file_navigation = filedialog.askopenfilename()
        self.lbl_navigation['text'] = self.file_navigation.split('/')[-1]

    def process(self):
        v1 = str(self.entry1.get())
        v2 = str(self.entry2.get())
        v3 = str(self.entry3.get())
        v4 = str(self.entry4.get())

        d1 = str(self.entry_description_1.get())
        d2 = str(self.entry_description_2.get())
        d3 = str(self.entry_description_3.get())
        d4 = str(self.entry_description_4.get())

        systems = [v1, v2, v3, v4]
        descriptions = [d1, d2, d3, d4]
        files = [self.file_1, self.file_2, self.file_3, self.file_4]
        info = [self.entry_vessel.get(), self.entry_location.get(), self.entry_client.get(), self.entry_jobno.get()]
        scope_work = self.text1.get('1.0',tk.END )

        statistics = {}
        start_stop_times = {}
        
        # -----------produce the merged dataframe for each system
        for i, system in enumerate(systems):
            try:
                df_merged = read_file_csv(files[i], self.file_navigation, system, self.nav)
            except:
                print ("cannot produce merged dataframe on system:" + str(i))
                continue

            plot_diff(df_merged, system)
            plot_gyros(df_merged)

            start_stop_times.update({system: start_stop_df_m(df_merged)})
            
            # -----------produce statistics            
            statistics.update({system + '_lat': (stats(df_merged, system, 'lat'))})
            statistics.update({system + '_lon': (stats(df_merged, system, 'lon'))})
        
        # -----------produce the report 
        pdf_collect(systems, statistics, start_stop_times, descriptions, info, scope_work)
        cleanup(systems)

    def client_exit(self):
        self.quit()

    def client_help(self):
        subprocess.Popen([resource_path('help.pdf')], shell=True)

# ----- MAIN -----#
if __name__ == "__main__":
    # ------call tk
    root = tk.Tk()
    #root.geometry("725x520")
    root.geometry("960x560")
    app = Window(root)
    root.mainloop()
    root.destroy()
     
#     fr = "C:/Users/empnav/Documents/CORAL_dataset/NG__270F.csv"
#     ft = "C:/Users/empnav/Documents/CORAL_dataset/SPN_RINEX_Verification_Data"
#     system = "COR_NG_XP_B"
#     df_merged = read_file_csv(fr, ft, system)
#     print (df_merged)
#     first, last, reverse = start_stop_df_m (df_merged)


    
    