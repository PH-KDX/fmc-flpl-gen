# Copyright 2020 PH-KDX.
# This file is part of FMC Flightplan Generator.

#   FMC Flightplan Generator is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as published
#   by the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   FMC Flightplan Generator is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with FMC Flightplan Generator.
#   If not, see <https://www.gnu.org/licenses/>.


import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sqlite3
import math

# Create database connection to an in-memory database for route compilation
connection_object = sqlite3.connect(":memory:")

cursor_object = connection_object.cursor()

# Load navigational databases:

with open('airports.json', 'rt') as airports_json:
    airports = json.load(airports_json)

with open('nav_data.json', 'rt') as waypoints_json:
    waypoints = json.load(waypoints_json)

# Route variable usage:
# ["dep","arr","fltnbr",[["waypoint", lat, lon, alt, in_db, "notes"],
# ["waypoint", lat, lon, alt, in_db, "notes"]]]

# in_db must be set to false
# If not, the FMC attempts to snap coordinates to those in the navfile


# calculate between-waypoint leg distance with Haversine formula
def dist(lat0, lon0, lat, lon):

    R = 3441.036714  # this is in nautical miles.

    dLat = math.radians(lat - lat0)
    dLon = math.radians(lon - lon0)
    lat0_rad = math.radians(lat0)
    lat_rad = math.radians(lat)

    a = (math.sin(dLat/2)**2
         + math.cos(lat0_rad)*math.cos(lat_rad)*math.sin(dLon/2)**2)
    c = 2*math.asin(math.sqrt(a))

    return R * c


# SQLite functions

# inserts a new waypoint in the table
def insert_row(waypoint_id, waypoint, lat, lon, alt, in_db, notes):
    cursor_object.execute(
        "INSERT INTO Route VALUES (?,?,?,?,?,?,?)",
        (
            waypoint_id,
            waypoint,
            lat,
            lon,
            alt,
            in_db,
            notes
            )
        )


# counts waypoints in the SQLite table
def waypoint_counter():
    cursor = cursor_object.execute("SELECT * FROM Route")
    waypoint_id = len(cursor.fetchall())
    return waypoint_id


# fetches all info about a waypoint by ID
def waypoint_info(waypoint_id):
    cursor = cursor_object.execute(
        "SELECT * FROM Route WHERE Waypoint_id=?",
        [waypoint_id])
    row = cursor.fetchall()[0]
    waypoint_contents = {
        "id": row[0],
        "waypoint": row[1],
        "lat": row[2],
        "lon": row[3],
        "alt": row[4],
        "in_db": bool(row[5]),
        "notes": row[6]
        }
    return waypoint_contents


# orders rows by ID
def row_order():
    cursor_object.execute(
        "CREATE TABLE Route_temp AS SELECT * FROM Route ORDER BY Waypoint_id")
    cursor_object.execute("DROP TABLE Route")
    cursor_object.execute("CREATE TABLE Route AS SELECT * FROM Route_temp")
    cursor_object.execute("DROP TABLE Route_temp")


# function for naming waypoint IDs during route creation
def row_move(waypoint_id, direction):
    if direction == "up":
        # move the previous waypoint to far away
        cursor_object.execute(
            ("UPDATE Route SET Waypoint_id=10000000 WHERE Waypoint_id=(\
                SELECT Waypoint_id-1 FROM Route WHERE Waypoint_id=?)"),
            [waypoint_id]
            )
        # move the waypoint to be moved to the place just vacated
        cursor_object.execute(
            "UPDATE Route SET Waypoint_id=Waypoint_id-1 WHERE Waypoint_id=?",
            [waypoint_id]
            )
    elif direction == "down":
        # move the next waypoint to a place far away
        cursor_object.execute(
            ("UPDATE Route SET Waypoint_id=10000000 WHERE Waypoint_id=(\
                SELECT Waypoint_id+1 FROM Route WHERE Waypoint_id=?)"),
            [waypoint_id]
            )
        # move the waypoint to be moved to the place just vacated
        cursor_object.execute(
            "UPDATE Route SET Waypoint_id=Waypoint_id+1 WHERE Waypoint_id=?",
            [waypoint_id]
            )
        # move the far-away waypoint to the place vacated by the moved waypoint
    cursor_object.execute(
        "UPDATE Route SET Waypoint_id=? WHERE Waypoint_id=10000000",
        [waypoint_id]
        )


# XML functions
# convert ugly XML text to a prettified version
def prettify(elem):
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


# Python functions
# calculates total route distance
def route_distance():
    total_dist = 0
    waypoint_len = waypoint_counter()
    lat0 = lat_dep
    lon0 = lon_dep
    if waypoint_len > 0:
        for i in range(1, waypoint_len):
            info = waypoint_info(i)
            lat = info["lat"]
            lon = info["lon"]
            leg_dist = dist(lat0, lon0, lat, lon)
            total_dist += leg_dist
            lat0 = lat
            lon0 = lon
    leg_dist = dist(lat0, lon0, lat_arr, lon_arr)
    total_dist += leg_dist
    return total_dist


# called for waypoints and airports which are not in database
def manual_coords():
    print("Not in the database, please enter location manually")
    while True:
        lat = input("Latitude:\n>")
        try:
            lat = float(lat)
            break
        except ValueError:
            print("Please enter a valid number")
    while True:
        lon = input("Longitude:\n>")
        try:
            lon = float(lon)
            break
        except ValueError:
            print("Please enter a valid number")
    return lat, lon


def route_dict_creator(dep, arr, fltnbr):
    waypoint_len = waypoint_counter()
    waypoints_dict = []
    for i in range(waypoint_len):
        row = waypoint_info(i+1)
        row_dict = [row["id"],
                    row["waypoint"],
                    row["lat"],
                    row["lon"],
                    row["alt"],
                    row["in_db"],
                    row["notes"]]
        waypoints_dict.append(row_dict)
    route_dict = []
    route_dict.append(dep)
    route_dict.append(arr)
    route_dict.append(fltnbr)
    route_dict.append(waypoints_dict)
    return route_dict


# full list of options if there are multiple for a waypoint
def print_waypoints_list(waypoint, opt_len):
    print(f"The following options were found for waypoint {waypoint}:")
    dash = '-' * 60
    print(dash)
    print("{:^10}{:^16}{:^16}{:^12}".format("Number",
                                                         "Latitude",
                                                         "Longitude",
                                                         "Leg distance"))
    print(dash)
    waypoint_len = waypoint_counter()
    if waypoint_len > 0:
        # the number of waypoints is the id of the previous waypoint
        last_row = waypoint_info(waypoint_len)
        lat0 = last_row["lat"]
        lon0 = last_row["lon"]
    else:
        lat0 = lat_dep
        lon0 = lon_dep
    # counter
    for i in range(opt_len):
        lat = waypoints[waypoint][i][0]
        lon = waypoints[waypoint][i][1]
        leg_dist = dist(lat0, lon0, lat, lon)
        leg_dist = round(leg_dist, 3)

        print("{:^10}{:^16}{:^16}{:^12}".format(i,
                                                             lat,
                                                             lon,
                                                             leg_dist))
        # set coordinates to measure from for next iteration
        lat_0 = lat
        lon_0 = lon
    print(dash)


def print_route_intermediate():
    cursor_object.execute("select * from Route")
    results = cursor_object.fetchall()
    if len(results) == 0:
        print("No route yet!")
    else:
        print("Route so far")
        dash = '-' * 75
        print(dash)
        print("{:<5}{:^9}{:^15}{:^15}{:^11}{:<8}".format("ID",
                                                         "Name",
                                                         "Latitude",
                                                         "Longitude",
                                                         "Altitude",
                                                         "Notes"))
        print(dash)
        for row in results:
            list1 = list(row)
            print("{:<5}{:^9}{:^15}{:^15}{:^11}{:<8}".format(list1[0],
                                                             list1[1],
                                                             list1[2],
                                                             list1[3],
                                                             str(list1[4]),
                                                             str(list1[6])))
        print(dash)
        dist_temp = route_distance()
        print("Total distance is", round(dist_temp, 3), "nm.")


# user interaction for waypoint addition
def add_waypoint_menu():
    waypoint = input("Waypoint\n>").upper()
    # first find the number of waypoints
    waypoint_len = waypoint_counter()

    # if it's not in the database
    if waypoint not in waypoints:
        coords = manual_coords()
    else:
        # number of waypoints with the same name in the database
        opt_len = (len(waypoints[waypoint]))
        # with only one waypoint option obviously number 0 must be chosen
        if opt_len == 1:
            coords = waypoints[waypoint][0]
        # however, if there are multiple options
        else:
            print_waypoints_list(waypoint, opt_len)
            while True:
                print("Choose the correct waypoint by number from the list:")
                waypoint_choice = input()
                if (waypoint_choice.isdigit() and
                        0 <= int(waypoint_choice) < opt_len):
                    waypoint_choice = int(waypoint_choice)
                    coords = waypoints[waypoint][waypoint_choice]
                    break
                else:
                    print("Not an option, sorry")

    # waypoint_len references the length **before** the waypoint addition
    if waypoint_len == 0:
        lat0 = lat_dep
        lon0 = lon_dep
    else:
        prev_waypoint = waypoint_info(waypoint_len)
        lat0 = prev_waypoint["lat"]
        lon0 = prev_waypoint["lon"]
    lat = coords[0]
    lon = coords[1]

    leg_distance = dist(lat0, lon0, lat, lon)

    print(f"Your chosen waypoint is {waypoint}")
    print(f"Its coordinates are {lat}, {lon}")
    print(f"Its leg distance is {round(leg_distance, 3)} nm.")

    print("press c to confirm waypoint choice, or anything else to cancel")

    if input() == "c":
        waypoint_id = waypoint_len+1
        print("VNAV altitude")
        while True:
            print("Enter number in feet, or press Enter to skip:")
            alt = input()
            try:
                alt = (None if alt == "" else float(alt))
                break
            except ValueError:
                pass
        print("Waypoint notes")
        print("Enter a note for this waypoint, or press Enter to skip:")
        notes = input()
        notes = None if notes == "" else notes

        # this must always be the case
        in_db = False

        insert_row(waypoint_id, waypoint, lat, lon, alt, in_db, notes)

    else:
        print("cancelling waypoint insertion")


# moves row to bottom, deletes it, reduces waypoint_num by one
def row_delete(waypt_id, num_waypoints):
    for i in range(waypt_id, num_waypoints):
        row_move(i, "down")
    cursor_object.execute(
        "DELETE FROM Route WHERE Waypoint_id=?", [num_waypoints]
        )
    row_order()


def row_delete_menu():
    print_route_intermediate()
    num_waypoints = waypoint_counter()
    # if there's no waypoints, the route print will say no route exists
    if 0 < num_waypoints:
        waypt_id = input("ID of waypoint to be deleted\n>")
        if waypt_id.isdigit() and 0 < int(waypt_id) <= num_waypoints:
            waypt_id = int(waypt_id)
            print(f"Confirm deletion of waypoint number {waypt_id}?")
            print("Enter y to confirm, anything else to cancel.")
            confirm = input(">")
            if confirm == "y":
                row_delete(waypt_id, num_waypoints)
            else:
                print("Cancelling waypoint deletion.")
        else:
            print("Not a waypoint option, sorry")


def airport_coords(icao):
    if icao in airports:
        lat = float(airports[icao][0])
        lon = float(airports[icao][1])
    else:
        lat, lon = manual_coords()
    return lat, lon


def route_to_file_menu(json_route):
    print("Write route to file? Enter c to confirm, or anything else to skip")
    write_to_file = input(">")

    if str(write_to_file).lower() == "c":
        dumpfile_name = input("Please type the filename for your dumpfile\n>")
        with open(dumpfile_name, "w") as route_file_txt:
            route_file_txt.write(json_route)
        print(f"Route has been written to {dumpfile}")

    else:
        print("Skipping write of route to file.")


def route_menu():
    while True:
        num_waypoints = waypoint_counter()
        print("Please enter:\n"
              "i to insert a waypoint\n"
              "s to shift a waypoint\n"
              "d to delete a waypoint\n"
              "v to view route\n"
              "x to return to main menu")
        insert = input(">").lower()

        if insert == "i":
            add_waypoint_menu()

        elif insert == "s":
            if num_waypoints == 0:
                print("No route yet!")
            elif num_waypoints == 1:
                print("Cannot shift a route with only one waypoint.")
            else:
                row_move_menu()

        elif insert == "d":
            row_delete_menu()

        elif insert == "v":
            print_route_intermediate()

        elif insert == "x":
            break

        else:
            print("Sorry, not an option.")


def main_menu():
    while True:
        print("\nPlease enter:\n"
              "e to edit/view route\n"
              "f to finish\n"
              "x to cancel route")
        insert = input(">").lower()
        if insert == "e":
            route_menu()
        elif insert == "f":
            break
        elif insert == "x":
            print("\nAre you sure you want to discard your route?\n"
                  "Enter y to discard, or any other input to cancel")
            quit_test = input(">")
            if quit_test == "y":
                quit()
        else:
            print("Sorry, not an option. Please try again.")


# initial input from user
def intro():
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
    return dep, lat_dep, lon_dep, arr, lat_arr, lon_arr, fltnbr


def main():
    # HACK: it's a pain to pass them all the way through
    global lat_dep
    global lon_dep
    global lat_arr
    global lon_arr

    # initial params by user
    dep, lat_dep, lon_dep, arr, lat_arr, lon_arr, fltnbr = intro()

    # table containing list of waypoints in route
    create_table = ("CREATE TABLE Route(Waypoint_id INTEGER, Waypoint TEXT, "
                    "Latitude REAL, Longitude REAL, Altitude INTEGER, "
                    "In_db INTEGER, Notes TEXT)")
    cursor_object.execute(create_table)

    main_menu()

    # get each row in the Route table as a SQLite tuple
    cursor_object.execute("SELECT * FROM Route")
    results = cursor_object.fetchall()

    route_dict = route_dict_creator(dep, arr, fltnbr)
    route_json = json.dumps(route_dict)
    print("\nYour FMC flight plan is\n\n")
    print(route_json)

    #route_to_file_menu(formatted_route)

    # generate_map(results)

    # input("press enter to exit")
    connection_object.close()


main()
