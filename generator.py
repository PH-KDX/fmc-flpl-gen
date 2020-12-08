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
connection_object = sqlite3.connect(":memory:")

cursor_object = connection_object.cursor()

# Load navigational databases:

airports_json = open('airports.json', 'rt')
airports = json.loads(airports_json.read())

waypoints_json = open('nav_data.json', 'rt')
waypoints = json.loads(waypoints_json.read())

# Route variable usage:
# ["dep","arr","fltnbr",[["waypoint", lat, lon, alt, e, f],
# ["waypoint", lat, lon, alt, e, f]]]

# this must ALWAYS be the case, or the FMC will do weird stuff with the route.

in_db = False
f = None

# for use in latitude and longitude entry
def is_float(value):
  try:
    float(value)
    return True
  except ValueError:
    return False

# cuz I have to use it 10 times and had enough of typing out the string
error_msg = "Not an option, please try again"

# called for waypoints and airports which are not in database
def manual_coords():
    print("Not in the database, please enter location manually")
    while True:
        lat = input("Latitude:\n>")
        if is_float(lat):
            lat=float(lat)
            break
        else:
            print(error_msg)
    while True:
        lon = input("Longitude:\n>")
        if is_float(lon):
            lon=float(lon)
            break
        else:
            print(error_msg)
    return lat, lon

def airport_coords(airport):
    if airport in airports:
        lat = float(airports[airport][0])
        lon = float(airports[airport][1])
    else:
        coords=manual_coords()
        lat=float(coords[0])
        lon=float(coords[1])
    return lat, lon

def create_header(dep,arr,fltnbr):
    # return a concatenation of these variables in the appropriate JSON format as the header
    return '[\"' + dep + '\",\"' + arr + '\",\"' + fltnbr + '\",['

# function to create a header and start counting leg distance
def init_params():
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
    dep_coords = airport_coords(dep)
    lat_dep = dep_coords[0]
    lon_dep = dep_coords[1]

    # arrival
    arr = input("arrival airport ICAO code\n>").upper()
    arr_coords = airport_coords(arr)
    lat_arr = arr_coords[0]
    lon_arr = arr_coords[1]

    # flight number
    fltnbr = input("type flight number, or leave blank to skip\n>").upper()

    lat0 = lat_dep
    lon0 = lon_dep

    return create_header(dep,arr,fltnbr)


def insert_row(waypoint_num,waypoint,lat,lon,alt,in_db,f):
    cursor_object.execute("INSERT INTO Route VALUES (?,?,?,?,?,?,?)", (waypoint_num,waypoint,lat,lon,alt,in_db,f))

# calculate between-waypoint leg distance with Haversine formula
def leg_dist(lat0,lon0,lat,lon):

    R = 3441.036714 # this is in nautical miles.

    dLat = math.radians(lat - lat0)
    dLon = math.radians(lon - lon0)
    lat0_rad = math.radians(lat0)
    lat_rad = math.radians(lat)

    a = math.sin(dLat/2)**2 + math.cos(lat0_rad)*math.cos(lat_rad)*math.sin(dLon/2)**2
    c = 2*math.asin(math.sqrt(a))

    return R * c

# full list of options if there are multiple for a waypoint
def print_waypoints_list(waypoint,opt_len):
    # counter
    opts_counter=0
    while opts_counter<opt_len:
        lat=waypoints[waypoint][opts_counter][0]
        lon=waypoints[waypoint][opts_counter][1]
        dist=leg_dist(lat0,lon0,lat,lon)
        print(str(opts_counter),") coordinates ",waypoints[waypoint][opts_counter], ", leg distance ", round(dist, 3), "nm", sep="")
        opts_counter += 1

# orders rows by ID
def row_order():
    cursor_object.execute("CREATE TABLE Route_temp AS SELECT * FROM Route ORDER BY Waypoint_num")
    cursor_object.execute("DROP TABLE Route")
    cursor_object.execute("CREATE TABLE Route AS SELECT * FROM Route_temp")
    cursor_object.execute("DROP TABLE Route_temp")

# function for naming waypoint IDs during route creation
def row_move(waypt_id, direction):
    if direction == "up":
        cursor_object.execute("UPDATE Route SET Waypoint_num=10000000 WHERE Waypoint_num=(SELECT Waypoint_num-1 FROM Route WHERE Waypoint_num=?)", (waypt_id,))
        cursor_object.execute("UPDATE Route SET Waypoint_num=Waypoint_num-1 WHERE Waypoint_num=?", (waypt_id,))
    elif direction == "down":
        cursor_object.execute("UPDATE Route SET Waypoint_num=10000000 WHERE Waypoint_num=(SELECT Waypoint_num+1 FROM Route WHERE Waypoint_num=?)", (waypt_id,))
        cursor_object.execute("UPDATE Route SET Waypoint_num=Waypoint_num+1 WHERE Waypoint_num=?", (waypt_id,))
    cursor_object.execute("UPDATE Route SET Waypoint_num=? WHERE Waypoint_num=10000000", (waypt_id,))

# moves row to bottom, deletes it, reduces waypoint_num by one
def row_delete(waypt_id):
    global waypoint_num
    for i in range(waypt_id, waypoint_num):
        row_move(i, "down")
    cursor_object.execute("DELETE FROM Route WHERE Waypoint_num=?", (waypoint_num,))
    waypoint_num = waypoint_num - 1
    row_order()

def assign_waypoint_auto(waypoint, waypoint_choice, opt_len):
    waypoint_choice=int(waypoint_choice)
    coords=waypoints[waypoint][waypoint_choice]
    return coords

def get_alt():
    alt = input("VNAV altitude; enter number in feet or enter any non-numerical input to skip:\n>")
    if is_float(alt):
        pass
    else:
        alt=None
    return alt

# iteratively shifts the waypoint one step at a time shift_spaces times
def row_move_menu():
    waypt_id=input("Waypoint ID to shift:\n>")

    if waypt_id.isdigit() and 0 < int(waypt_id) <= waypoint_num:
        waypt_id = int(waypt_id)
    else:
        print(error_msg)
        return

    direction=input("Direction to shift waypoint (u for up/ d for down):\n>")

    if direction.isalpha() and (direction.lower() == "u" or direction.lower() == "d"):
        direction = direction.lower()
    else:
        print(error_msg)
        return

    shift_spaces=input("Spaces to shift waypoint:\n>")
    if shift_spaces.isdigit():
        shift_spaces = int(shift_spaces)
    else:
        print(error_msg)
        return


    if direction == "u":
        end_id = waypt_id - shift_spaces
        if end_id > 0:
            for i in range(waypt_id, end_id, -1):
                row_move(i, "up")
            row_order()
            print("Waypoint has been shifted", shift_spaces, "space(s) up.")
        else:
            print("Choice exceeds route range; please try again.")

    elif direction == "d":
        end_id = waypt_id + shift_spaces
        if end_id <= waypoint_num:
            for i in range(waypt_id, end_id):
                row_move(i, "down")
            row_order()
            print("Waypoint has been shifted", shift_spaces, "space(s) down.")
        else:
            print("Choice exceeds route range; please try again.")

    else:
        print(error_msg)

def row_delete_menu():
    waypt_id = input("ID of waypoint to delete\n>")
    if waypt_id.isdigit() and 0 < int(waypt_id) <= waypoint_num:
        waypt_id = int(waypt_id)
        print("Confirm deletion of waypoint number ", waypt_id, "?\nEnter y to confirm, anything else to cancel.", sep="")
        confirm = input(">")
        if confirm == "y":
            row_delete(waypt_id)
        else:
            print("Cancelling waypoint deletion.")
    else:
        print(error_msg)

def add_waypoint(waypoint):
    global lat0
    global lon0
    global dist_total
    global waypoint_num
    # number of waypoints
    if waypoint in waypoints:
        opt_len=(len(waypoints[waypoint]))
        # with only one waypoint option obviously number 0 must be chosen
        if opt_len == 1:
            coords=assign_waypoint_auto(waypoint, "0", opt_len)
        elif opt_len > 1:
            print("The following options were found for waypoint", waypoint)
            print_waypoints_list(waypoint,opt_len)
            while True:
                waypoint_choice=str(input("choose the correct waypoint by number from the list:\n>"))
                if waypoint_choice.isdigit() and 0 <= int(waypoint_choice) < opt_len:
                    coords=assign_waypoint_auto(waypoint, waypoint_choice, opt_len)
                    break
                else:
                    print(error_msg)
        else:
            pass
    else:
        coords=manual_coords()
    lat=coords[0]
    lon=coords[1]
    dist=leg_dist(lat0,lon0,lat,lon)
    print("your chosen waypoint is ", waypoint, ", with coordinates of ",lat,", ",lon, " and a leg distance of ", round(dist, 3), " nm.", sep="")
    confirm = input("press c to confirm waypoint choice, or anything else to cancel\n>")
    if confirm == "c":
        waypoint_num = waypoint_num+1
        alt=get_alt()
        insert_row(waypoint_num,waypoint,lat,lon, alt, in_db, f)
        dist_total=dist_total+dist
        lat0=lat
        lon0=lon
    else:
        print("cancelling waypoint insertion")

def main_menu(header):
    global waypoint_num
    waypoint_num=0
    while True:
        insert=input("\nPlease enter:\ne to edit route\nf to finish\nx to cancel route\n>").lower()
        if insert == "e":
            route_menu(header)
        elif insert == "f":
            break
        elif insert == "x":
            quit_test=input("\nAre you sure you want to discard your route?\nEnter y to discard, or any other input to cancel\n>")        
            if quit_test == "y":
                quit()
            else:
                pass
        else:
            print(error_msg)

def route_menu(header):
    while True:
        insert=input("\nPlease enter:\ni to insert a waypoint\ns to shift a waypoint\nd to delete a waypoint\nv to view route\nx to return to main menu\n>").lower()
        if insert == "i":
            waypoint=input("Waypoint\n>").upper()
            add_waypoint(waypoint)
        elif insert == "s":
            if waypoint_num == 0:
                print("No route yet!")
            elif waypoint_num == 1:
                print("Cannot shift a route with only one waypoint.")
            else:
                row_move_menu()
        elif insert == "d":
            row_delete_menu()
        elif insert == "v":
            print_route_intermediate(header)
        elif insert == "x":
            break
        else:
            print(error_msg)

# This is some very dirty code for writing a kml file with the rote as a map.
# I'm doing this to avoid requiring pip

# airport
def kml_arpt(arpt,lat_arpt,lon_arpt, f):
    f.write("\t<Placemark>\n")
    f.write("\t\t<name>" + arpt + "</name>\n")
    f.write("\t\t<Point>\n")
    f.write("\t\t\t<coordinates>" + str(lon_arpt) + "," + str(lat_arpt) + "</coordinates>\n")
    f.write("\t\t</Point>\n")
    f.write("\t</Placemark>\n")

# waypoint
def kml_waypoint(line,f):
    f.write("\t<Placemark>\n")
    f.write("\t\t<name>" + str(line[1]) + "</name>\n")
    f.write("\t\t<Point>\n")
    f.write("\t\t\t<coordinates>" + str(line[3]) + "," + str(line[2]) + "</coordinates>\n")
    f.write("\t\t</Point>\n")
    f.write("\t</Placemark>\n")

# line between waypoints
def kml_connector(prev_wpt,lat,lon, f):
    f.write("\t<Placemark>\n")
    f.write("\t\t<name>" + str(round(leg_dist(prev_wpt[0],prev_wpt[1],lat,lon),2)) + " nm" + "</name>\n")
    f.write("\t\t<LineString>\n")
    f.write("\t\t\t<extrude>1</extrude>\n")
    f.write("\t\t\t<tessellate>1</tessellate>\n")
    f.write("\t\t\t<altitudeMode>absolute</altitudeMode>\n")
    f.write("\t\t\t<coordinates>\n")
    f.write("\t\t\t\t" + str(prev_wpt[1]) + "," + str(prev_wpt[0])+"\n")
    f.write("\t\t\t\t" + str(lon) + "," + str(lat)+"\n")
    f.write("\t\t\t</coordinates>\n")
    f.write("\t\t</LineString>\n")
    f.write("\t</Placemark>\n")

# bringing it all together
def create_kml_route(dep,lat_dep,lon_dep,arr,lat_arr,lon_arr,route,dumpfile,insert_arr):
    global f
    f = open(dumpfile, "w")
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
    f.write("<Document>\n")
    kml_arpt(dep,lat_dep,lon_dep, f)
    prev_wpt=[lat_dep,lon_dep]
    for line in route:
        kml_connector(prev_wpt, float(line[2]), float(line[3]), f)
        kml_waypoint(line,f)
        prev_wpt=[float(line[2]),float(line[3])]
    if insert_arr:
        kml_connector(prev_wpt,lat_arr,lon_arr,f)
        kml_arpt(arr,lat_arr,lon_arr, f)
    else:
        pass
    f.write("</Document>\n")
    f.write("</kml>\n")
    f.close()

def generate_map(results):
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
        create_kml_route(dep,lat_dep,lon_dep,arr,lat_arr,lon_arr,results,dumpfile,insert_arr)
        print("Route map has been written to "+dumpfile)
        return dumpfile
    else:
        print("Skipping Google Maps route generation")

def print_route_intermediate(header):
    cursor_object.execute("select * from Route")
    results = cursor_object.fetchall()
    if len(results) == 0:
        print("No route yet!")
    else:
        print("Route so far:\nID: Name, latitude, longitude, altitude")
        for row in results:
            list1=list(row)
            print(list1[0],": ", list1[1],", ", list1[2],", ", list1[3],", ", list1[4], sep="")
        dist=leg_dist(lat0,lon0,lat_arr,lon_arr)
        dist_temp=dist_total+dist
        print("Total distance is", round(dist_temp, 3), "nm.")

def print_route_formatted(header, results):
    global dist_total
    dist=leg_dist(lat0,lon0,lat_arr,lon_arr)
    dist_total=dist_total+dist
    rows_rem=len(results)

    #print header
    print("\nYour route is:\n\n")
    formatted_route = header

    for row in results:
    #convert to list for parsing purposes
        list1=list(row)
    #change integer back to boolean form (it was corrupted by the SQLite conversion)
        list1[5]=bool(int(list1[5]))
    #convert it to json so the appropriate format is diplayed on print
        json1 = json.dumps(list1[1:])
    #print it
        if rows_rem>1:
            formatted_route=formatted_route+json1+","
        else:
            formatted_route=formatted_route+json1
        rows_rem=rows_rem-1

    #print closing brackets to end route
    formatted_route=formatted_route+"]]\n"
    print(formatted_route)
    print("Route distance is", round(dist_total, 3), "nautical miles.")

    return formatted_route

def route_to_file(formatted_route):
    write_to_file = input("Write route to file? Enter c to confirm, or anything else to skip\n>")
    if str(write_to_file).lower() == "c":
        while True:
            dumpfile=input("Please type dumpfile name (full path) ending in .txt\n>")
            if dumpfile[-4:] == ".txt" and dumpfile.count(".") == 1:
                break
            else:
                print("Sorry, not a valid filename.")
        route_file_txt = open(dumpfile, "w")
        route_file_txt.write(formatted_route)
        route_file_txt.close()

        print("Route has been written to "+dumpfile)
    else:
        print("Skipping write of route to file.")


def main():
    header = init_params()
    
    # table containing list of waypoints in route
    create_table = "CREATE TABLE Route(Waypoint_num INTEGER, Waypoint TEXT, Latitude REAL, Longitude REAL, Altitude INTEGER, toLast TEXT, Last TEXT)"
    cursor_object.execute(create_table)

    main_menu(header)

    # get each row in the Route table as a SQLite tuple
    cursor_object.execute("select * from Route")
    results = cursor_object.fetchall()

    formatted_route = print_route_formatted(header,results)

    route_to_file(formatted_route)

    generate_map(results)

    input("press enter to exit")
    connection_object.close()

main()
