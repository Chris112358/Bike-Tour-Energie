# -*- coding: utf-8 -*-
"""
Script for getting the used energie and calories for a bike tour.
"""

from lxml import etree
import datetime
import math
import matplotlib.pyplot as plt

class MyError(Exception):
    pass


def _getTime(timestr):
    time = timestr.split('T')[1]
    time = time.split('Z')[0]
    return time


def _getTimeDif(first, second, in_seconds = True):
    Format = '%H:%M:%S.%f'
    
    diff = datetime.datetime.strptime(second, Format) - datetime.datetime.strptime(first, Format)
    
    if in_seconds:
        sec = diff.seconds
        mic = diff.microseconds
        
        diff = sec + mic/10**6
        
        if diff // 1 != sec:
            raise MyError('Something went wrong, false seconds')
    return diff


def distance(origin, destination, hight):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371000 # m

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c

    dist = math.sqrt(d**2 + hight**2)
    slope = hight / d

    return dist, slope


def Forces(velocity_in=10, velocity_out=10, slope=0.1, mass=80, delta_time=.1):
    
    g = 9.81
    mu_RR = .004  #rollforce coeficiant
    c_w = 1.1
    rho = 1.2 # air density
    A = 1.7 * .3 #body face 
    
    #easy constanants
    #g = 10
    #mu_RR = .001
    #c_w = 1
    #rho = 1
    #A = 0.5
    
    a = math.atan(slope)
    
    F_G = mass * g  #Gravity
    F_N = math.cos(a) * F_G  #always positive #normal force against the bottom
    F_H = math.sin(a) * F_G  #negative if driven downhill positive else #force faced always downhills
    
    eps = abs(F_N**2 + F_H**2 - F_G**2)
    
    if eps > 0.001:
        raise MyError('Some calculations went wrong diffrence of eps = {}'.format(eps))
        
    F_RR = F_N * mu_RR  #rolling force
    F_L = .5 * c_w * rho * A * velocity_in**2  #air resistance
    
    
    F_tot = F_H + F_RR + F_L   #force against velocity

    acc = (velocity_out - velocity_in)/delta_time #acceleration
    
    F_needed = (mass * acc) + F_tot  # force needed to get to the endvelocity of that intervall
    
    if F_needed < 0:
        #print('no extraforce needed')
        F_needed = 0
    
    way = .5 * (velocity_in + velocity_out) * delta_time  #way driven in the time delta time
     
    Energie = F_needed * way  #energie / work needed to get to that end speed
    
    return Energie


def integrate(xAxe, yAxe, method='trapezoidal'):
    
    if len(xAxe) != len(yAxe):
        raise MyError('x and y must be the same length')
    
    integral = []
    
    if method == 'rectangle':
        for idx in range(len(xAxe)):
            if idx == 0:
                width = .5 * (xAxe[1] - xAxe[0])
            elif idx == len(xAxe) - 1:
                width = .5 * (xAxe[-1] - xAxe[-2])
            else:
                width = (xAxe[idx + 1] - xAxe[idx - 1]) * .5
                
            integral.append(width * yAxe[idx])
            
    elif method == 'trapezoidal':
        for idx in range(len(xAxe)):
            if idx == 0:
                integral.append(0)
            else:
                width = xAxe[idx] - xAxe[idx - 1]
                trapez = yAxe[idx] + yAxe[idx - 1]
                integral.append(width * trapez * .5)
            
    else:
        raise MyError('No such implementation for this quadrature rule')
        
    return sum(integral)


def load_lists(file):
    gpx = etree.parse(file)

    root = gpx.getroot()
    
    META = root[0]
    TRACK = root[1]
    TRACKSEGMENT = TRACK[1]
    
    NAME = META[0].text
    #time in seconds
    Time = []
    Timedif = []
    Runtime = []
    #Distance in meters
    Place = []
    Dist = []
    Hight = []
    Hightdif = []
    #speed in [m/s]
    Velocity = []    
    
    for point in TRACKSEGMENT:
        lon = float(point.get('lon'))
        lat = float(point.get('lat'))
        Time.append(_getTime(point[1].text))
        Place.append([lat, lon])
        Hight.append(float(point[0].text))
        
        if Timedif == []:
            Timedif.append(0)
            Dist.append((0,0))
            Hightdif.append(0)
            Velocity.append(0)
            Runtime.append(0)
            
        else:
            Timedif.append(_getTimeDif(Time[-2], Time[-1]))
            Runtime.append(_getTimeDif(Time[0], Time[-1]))
            Hightdif.append(Hight[-1] - Hight[-2])
            Dist.append(distance(Place[-2], Place[-1], Hightdif[-1]))
                
            if Timedif[-1] == 0 and Dist[-1][0] == 0:
                Velocity.append(0)
            elif Timedif[-1] == 0:
                raise MyError('Hey you teleported, how can you be at two diffrent places at the same time.')
            else:
                Velocity.append(Dist[-1][0] / Timedif[-1])
                            
    Duration = _getTimeDif(Time[0], Time[-1], in_seconds=False) # Duration of the tour in total
    
    Dict = {'Time': Time, 'Timedif': Timedif, 'Runtime': Runtime,
            'Place': Place, 'Dist': Dist, 'Hight': Hight,
            'Hightdif': Hightdif, 'Velocity': Velocity, 'Duration': Duration,
            'Name': NAME}
    return Dict
        
        
def main(locdata, weight):

    Data = load_lists(locdata)
    
    Velocity = Data['Velocity']
    Timedif = Data['Timedif']
    Dist = Data['Dist']
    Runtime = Data['Runtime']
    #Energie in joul = kg*m*m/s/s
    Energie = []
    
    for idx in range(len(Velocity)):
        if idx == 0:
            Energie.append(0)
        else:
            #get the Energie needed to get from Time[-2] to Time[-1] Energie in Joul
            Energie.append(Forces(velocity_in=Velocity[-2], velocity_out=Velocity[-1], 
                                  slope=Dist[-1][1], mass=weight, delta_time=Timedif[-1])) 
    

    
    I = integrate(Runtime, Energie, method = 'rectangle')
    I = integrate(Runtime, Energie)

    print('Energie in Joul = {}'.format(I) )
    print('Energie in kcal = {}'.format(I * 0.000239006))
    print('middle speed = {}'.format(sum(Velocity) / len(Velocity) * 3.6))
    
    upward = sum(i for i in Data['Hightdif'] if i>0)
    downward = sum(i for i in Data['Hightdif'] if i<0)
    
    print('Total up = {}, total down = {}'.format(upward, downward))


    #plt.plot(Runtime, Data['Hight'])
    plt.plot(Runtime, Velocity)
                        
    
if __name__ == '__main__':
                                
    localdata = 'C:/Users/chris/Desktop/Tour.gpx'
    weight = 100
        
    main(localdata, weight)
    
    

    

