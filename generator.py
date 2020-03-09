# Copyright 2020 PH-KDX, Eddie.
# This file is part of FMC Flightplan Generator.

#     FMC Flightplan Generator is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     FMC Flightplan Generator is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with FMC Flightplan Generator.  If not, see <https://www.gnu.org/licenses/>.

import json

import sqlite3

import math

# Create database connection to an in-memory database for route compilation
connectionObject = sqlite3.connect(":memory:")

cursorObject = connectionObject.cursor()

# Load navigational databases:

airports_json = open('airports.json', 'rt')
airports = json.loads(airports_json.read())

waypoints_json = open('nav_data.json', 'rt')
waypoints = json.loads(waypoints_json.read())

# Route variable usage:
# ["dep","arr","fltnbr",[["waypoint", lat, lon, alt, e, f],
# ["waypoint", lat, lon, alt, e, f]]]

# this must ALWAYS be the case, or the FMC will do weird stuff with the route.

e = False
f = None

# for use in latitude and longitude entry
def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False

# cuz I have to use it 10 times and had enough of typing out the string
nOptErrorMsg = "Not an option, please try again"

# called for waypoints and airports which are not in database
def manualCoords():
    print("Not in the database, please enter location manually")
    while True:
        lat = input("Latitude:\n>")
        if isfloat(lat):
            lat=float(lat)
            break
        else:
            print(nOptErrorMsg)
    while True:
        lon = input("Longitude:\n>")
        if isfloat(lon):
            lon=float(lon)
            break
        else:
            print(nOptErrorMsg)
    return lat, lon

def airportCoords(airport):
    if airport in airports:
        lat = float(airports[airport][0])
        lon = float(airports[airport][1])
    else:
        coords=manualCoords()
        lat=float(coords[0])
        lon=float(coords[1])
    return lat, lon

def createHeader(dep,arr,fltnbr):
    # return a concatenation of these variables in the appropriate JSON format as the header
    return '[\"' + dep + '\",\"' + arr + '\",\"' + fltnbr + '\",['

# function to create a header and start counting leg distance
def initParams():
    global lat0
    global lon0
    global dep
    global arr
    global lat_dep
    global lon_dep
    global lat_arr
    global lon_arr
    global dist_total

    dist_total=0
    # departure
    dep = input("departure airport ICAO code\n>").upper()
    dep_coords = airportCoords(dep)
    lat_dep = dep_coords[0]
    lon_dep = dep_coords[1]

    # arrival
    arr = input("arrival airport ICAO code\n>").upper()
    arr_coords = airportCoords(arr)
    lat_arr = arr_coords[0]
    lon_arr = arr_coords[1]

    # flight number
    fltnbr = input("type flight number, or leave blank to skip\n>").upper()

    lat0 = lat_dep
    lon0 = lon_dep

    return createHeader(dep,arr,fltnbr)


def insertRow(waypoint_num,waypoint,lat,lon,alt,e,f):
    cursorObject.execute("INSERT INTO Route VALUES (?,?,?,?,?,?,?)", (waypoint_num,waypoint,lat,lon,alt,e,f))

# calculate between-waypoint leg distance with Haversine formula
def legDist(lat0,lon0,lat,lon):

    R = 3441.036714 # this is in nautical miles.

    dLat = math.radians(lat - lat0)
    dLon = math.radians(lon - lon0)
    lat0_rad = math.radians(lat0)
    lat_rad = math.radians(lat)

    a = math.sin(dLat/2)**2 + math.cos(lat0_rad)*math.cos(lat_rad)*math.sin(dLon/2)**2
    c = 2*math.asin(math.sqrt(a))

    return R * c

# if coords can't be automatically retrieved from the database:
def assignWaypointManual():
    print("Not in the database, please enter location manually")
    lat = float(input("Latitude:\n>"))
    lon = float(input("Longitude:\n>"))
    return lat, lon

# full list of options if there are multiple for a waypoint
def printWaypointsList(waypoint,opt_len):
    # counter
    opts_counter=0
    while opts_counter<opt_len:
        lat=waypoints[waypoint][opts_counter][0]
        lon=waypoints[waypoint][opts_counter][1]
        dist=legDist(lat0,lon0,lat,lon)
        print(str(opts_counter),") coordinates ",waypoints[waypoint][opts_counter], ", leg distance ", round(dist, 3), "nm", sep="")
        opts_counter=opts_counter+1

# orders rows by ID
def rowOrder():
    cursorObject.execute("CREATE TABLE Route_temp AS SELECT * FROM Route ORDER BY Waypoint_num")
    cursorObject.execute("DROP TABLE Route")
    cursorObject.execute("CREATE TABLE Route AS SELECT * FROM Route_temp")
    cursorObject.execute("DROP TABLE Route_temp")

# function for naming waypoint IDs during route creation
def rowMove(waypt_id, direction):
    if direction == "up":
        cursorObject.execute("UPDATE Route SET Waypoint_num=10000000 WHERE Waypoint_num=(SELECT Waypoint_num-1 FROM Route WHERE Waypoint_num=?)", (waypt_id,))
        cursorObject.execute("UPDATE Route SET Waypoint_num=Waypoint_num-1 WHERE Waypoint_num=?", (waypt_id,))
    elif direction == "down":
        cursorObject.execute("UPDATE Route SET Waypoint_num=10000000 WHERE Waypoint_num=(SELECT Waypoint_num+1 FROM Route WHERE Waypoint_num=?)", (waypt_id,))
        cursorObject.execute("UPDATE Route SET Waypoint_num=Waypoint_num+1 WHERE Waypoint_num=?", (waypt_id,))
    cursorObject.execute("UPDATE Route SET Waypoint_num=? WHERE Waypoint_num=10000000", (waypt_id,))

# moves row to bottom, deletes it, reduces waypoint_num by one
def rowDelete(waypt_id):
    global waypoint_num
    for i in range(waypt_id, waypoint_num):
        rowMove(i, "down")
    cursorObject.execute("DELETE FROM Route WHERE Waypoint_num=?", (waypoint_num,))
    waypoint_num = waypoint_num - 1
    rowOrder()

def assignWaypointAuto(waypoint, waypoint_choice, opt_len):
    waypoint_choice=int(waypoint_choice)
    coords=waypoints[waypoint][waypoint_choice]
    return coords

def getAlt():
    alt = input("VNAV altitude; enter number in feet or enter any non-numerical input to skip:\n>")
    if isfloat(alt):
        pass
    else:
        alt=None
    return alt

# iteratively shifts the waypoint one step at a time shift_spaces times
def rowMoveMenu():
    waypt_id=input("Waypoint ID to shift:\n>")

    if waypt_id.isdigit() and 0 < int(waypt_id) <= waypoint_num:
        waypt_id = int(waypt_id)
    else:
        print(nOptErrorMsg)
        return

    direction=input("Direction to shift waypoint (u for up/ d for down):\n>")

    if direction.isalpha() and (direction.lower() == "u" or direction.lower() == "d"):
        direction = direction.lower()
    else:
        print(nOptErrorMsg)
        return

    shift_spaces=input("Spaces to shift waypoint:\n>")
    if shift_spaces.isdigit():
        shift_spaces = int(shift_spaces)
    else:
        print(nOptErrorMsg)
        return


    if direction == "u":
        end_id = waypt_id - shift_spaces
        if end_id > 0:
            direction = direction.lower()
            for i in range((waypt_id), (end_id), -1):
                rowMove(i, "up")
            rowOrder()
            print("Waypoint has been shifted", shift_spaces, "space(s) up.")
        else:
            print("Choice exceeds route range; please try again.")

    elif direction == "d":
        end_id = waypt_id + shift_spaces
        if (end_id) <= waypoint_num:
            direction = direction.lower()
            for i in range(waypt_id, (end_id)):
                rowMove(i, "down")
            rowOrder()
            print("Waypoint has been shifted", shift_spaces, "space(s) down.")
        else:
            print("Choice exceeds route range; please try again.")

    else:
        print(nOptErrorMsg)

def rowDeleteMenu():
    waypt_id = input("ID of waypoint to delete\n>")
    if waypt_id.isdigit() and 0 < int(waypt_id) <= waypoint_num:
        waypt_id = int(waypt_id)
        print("Confirm deletion of waypoint number ", waypt_id, "?\nEnter y to confirm, anything else to cancel.", sep="")
        confirm = input(">")
        if confirm == "y":
            rowDelete(waypt_id)
        else:
            print("Cancelling waypoint deletion.")
    else:
        print(nOptErrorMsg)

def addWaypoint(waypoint):
    global lat0
    global lon0
    global dist_total
    global waypoint_num
    # number of waypoints
    if waypoint in waypoints:
        opt_len=(len(waypoints[waypoint]))
        # with only one waypoint option obviously number 0 must be chosen
        if opt_len == 1:
            coords=assignWaypointAuto(waypoint, "0", opt_len)
        elif opt_len > 1:
            print("The following options were found for waypoint", waypoint)
            dist=printWaypointsList(waypoint,opt_len)
            while True:
                waypoint_choice=str(input("choose the correct waypoint by number from the list:\n>"))
                if waypoint_choice.isdigit() == True and 0<=int(waypoint_choice) and int(waypoint_choice)<opt_len:
                    coords=assignWaypointAuto(waypoint, waypoint_choice, opt_len)
                    break
                else:
                    print(nOptErrorMsg)
        else:
            pass
    else:
        coords=manualCoords()
    lat=coords[0]
    lon=coords[1]
    dist=legDist(lat0,lon0,lat,lon)
    print("your chosen waypoint is ", waypoint, ", with coordinates of ",lat,", ",lon, " and a leg distance of ", round(dist, 3), " nm.", sep="")
    confirm = input("press c to confirm waypoint choice, or anything else to cancel\n>")
    if confirm == "c":
        waypoint_num = waypoint_num+1
        alt=getAlt()
        insertRow(waypoint_num,waypoint,lat,lon, alt, e, f)
        dist_total=dist_total+dist
        lat0=lat
        lon0=lon
    else:
        print("cancelling waypoint insertion")

def mainMenu(header):
    global waypoint_num
    waypoint_num=0
    while True:
        insert=input("\nPlease enter:\ne to edit route\nf to finish\nx to cancel route\n>").lower()
        if insert == "e":
            routeMenu(header)
        elif insert == "f":
            break
        elif insert == "x":
            quit_test=input("\nAre you sure you want to discard your route?\nEnter y to discard, or any other input to cancel\n>")        
            if quit_test == "y":
                quit()
            else:
                pass
        else:
            print(nOptErrorMsg)

def routeMenu(header):
    while True:
        insert=input("\nPlease enter:\ni to insert a waypoint\ns to shift a waypoint\nd to delete a waypoint\nv to view route\nx to return to main menu\n>").lower()
        if insert == "i":
            waypoint=input("Waypoint\n>").upper()
            addWaypoint(waypoint)
        elif insert == "s":
            if waypoint_num == 0:
                print("No route yet!")
            elif waypoint_num == 1:
                print("Cannot shift a route with only one waypoint.")
            else:
                rowMoveMenu()
        elif insert == "d":
            rowDeleteMenu()
        elif insert == "v":
            printRouteIntermediate(header)
        elif insert == "x":
            break
        else:
            print(nOptErrorMsg)

# This is some very dirty code for writing a KML file with the rote as a map.
# I'm doing this to avoid requiring pip

# airport
def KMLArpt(arpt,lat_arpt,lon_arpt):
    f.write("\t<Placemark>\n")
    f.write("\t\t<name>" + arpt + "</name>\n")
    f.write("\t\t<Point>\n")
    f.write("\t\t\t<coordinates>" + str(lon_arpt) + "," + str(lat_arpt) + "</coordinates>\n")
    f.write("\t\t</Point>\n")
    f.write("\t</Placemark>\n")

# waypoint
def KMLWaypoint(line,f):
    f.write("\t<Placemark>\n")
    f.write("\t\t<name>" + str(line[0]) + "</name>\n")
    f.write("\t\t<Point>\n")
    f.write("\t\t\t<coordinates>" + str(line[3]) + "," + str(line[2]) + "</coordinates>\n")
    f.write("\t\t</Point>\n")
    f.write("\t</Placemark>\n")

# line between waypoints
def KMLConnector(prevWpt,lat,lon):
    f.write("\t<Placemark>\n")
    f.write("\t\t<name>" + str(round(legDist(prevWpt[0],prevWpt[1],lat,lon),2)) + " nm" + "</name>\n")
    f.write("\t\t<LineString>\n")
    f.write("\t\t\t<extrude>1</extrude>\n")
    f.write("\t\t\t<tessellate>1</tessellate>\n")
    f.write("\t\t\t<altitudeMode>absolute</altitudeMode>\n")
    f.write("\t\t\t<coordinates>\n")
    f.write("\t\t\t\t" + str(prevWpt[1]) + "," + str(prevWpt[0])+"\n")
    f.write("\t\t\t\t" + str(lon) + "," + str(lat)+"\n")
    f.write("\t\t\t</coordinates>\n")
    f.write("\t\t</LineString>\n")
    f.write("\t</Placemark>\n")

# bringing it all together
def createKMLRoute(dep,lat_dep,lon_dep,arr,lat_arr,lon_arr,route,dumpfile,insert_arr):
    global f
    f = open(dumpfile, "w")
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
    f.write("<Document>\n")
    KMLArpt(dep,lat_dep,lon_dep)
    prevWpt=[lat_dep,lon_dep]
    for line in route:
        KMLConnector(prevWpt,float(line[2]),float(line[3]))
        KMLWaypoint(line,f)
        prevWpt=[float(line[2]),float(line[3])]
    if insert_arr==True:
        KMLConnector(prevWpt,lat_arr,lon_arr)
        KMLArpt(arr,lat_arr,lon_arr)
    else:
        pass
    f.write("</Document>\n")
    f.write("</kml>\n")
    f.close()

def generateMap(results):
    maps_choice=input("Export route as Google Maps file? Enter c to confirm, or anything else to skip\n>")
    if str(maps_choice).lower() == "c":
        while True:
            dumpfile=input("Please type dumpfile name (full path) ending in .kml\n>")
            if dumpfile[-4:] == ".kml" and dumpfile.count(".") == 1:
                break
            else:
                print("Sorry, not a valid filename.")

        print("Include arrival airport in route map?")
        print("Hint: if the route already has a runway line-up you probably don't want the airport as well.")
        insert_arr=str(input("Enter y to include, or leave blank to omit\n>")).lower()

        if insert_arr=="y":
            insert_arr=True
        else:
            insert_arr=False
        createKMLRoute(dep,lat_dep,lon_dep,arr,lat_arr,lon_arr,results,dumpfile,insert_arr)
        print("Route map has been written to "+dumpfile)
        return dumpfile
    else:
        print("Skipping Google Maps route generation")

def printRouteIntermediate(header):
    cursorObject.execute("select * from Route")
    results = cursorObject.fetchall()
    if len(results) == 0:
        print("No route yet!")
    else:
        print("Route so far:\nID: Name, latitude, longitude, altitude")
        for row in results:
            list1=list(row)
            print(list1[0],": ", list1[1],", ", list1[2],", ", list1[3],", ", list1[4], sep="")
        dist=legDist(lat0,lon0,lat_arr,lon_arr)
        dist_temp=dist_total+dist
        print("Total distance is", round(dist_temp, 3), "nm.")

def printRouteFormatted(header, results):
    global dist_total
    dist=legDist(lat0,lon0,lat_arr,lon_arr)
    dist_total=dist_total+dist
    rowsRem=len(results)

    #print header
    print("\nYour route is:\n\n")
    formattedroute = header

    for row in results:
    #convert to list for parsing purposes
        list1=list(row)
    #change integer back to boolean form (it was corrupted by the SQLite conversion)
        list1[5]=bool(int(list1[5]))
    #convert it to json so the appropriate format is diplayed on print
        json1 = json.dumps(list1[1:])
    #print it
        if rowsRem>1:
            formattedroute=formattedroute+json1+","
        else:
            formattedroute=formattedroute+json1
        rowsRem=rowsRem-1

    #print closing brackets to end route
    formattedroute=formattedroute+"]]\n"
    print(formattedroute)
    print("Route distance is", round(dist_total, 3), "nautical miles.")

    return formattedroute

def routeToFile(formattedroute):
    write_to_file = input("Write route to file? Enter c to confirm, or anything else to skip\n>")
    if str(write_to_file).lower() == "c":
        while True:
            dumpfile=input("Please type dumpfile name (full path) ending in .txt\n>")
            if dumpfile[-4:] == ".txt" and dumpfile.count(".") == 1:
                break
            else:
                print("Sorry, not a valid filename.")
        route_file_txt = open(dumpfile, "w")
        route_file_txt.write(formattedroute)
        route_file_txt.close()

        print("Route has been written to "+dumpfile)
    else:
        print("Skipping write of route to file.")


def main():
    header = initParams()
    
    # table containing list of waypoints in route
    createTable = "CREATE TABLE Route(Waypoint_num INTEGER, Waypoint TEXT, Latitude REAL, Longitude REAL, Altitude INTEGER, toLast TEXT, Last TEXT)"
    cursorObject.execute(createTable)

    mainMenu(header)

    # get each row in the Route table as a SQLite tuple
    cursorObject.execute("select * from Route")
    results = cursorObject.fetchall()

    formattedroute = printRouteFormatted(header,results)

    routeToFile(formattedroute)

    generateMap(results)

    input("press enter to exit")
    connectionObject.close()

main()
