## FMC Flightplan Generator

This program generates flight plans for the Flight Management Computer by Harry Xue.
It also creates .kml files with a visual representation of the generated route, which can be imported into Google Maps.

Ensure that `generator.py` is in the same directory as `airports.json` and `nav_data.json`.
Run using Python 3.

Does not require `pip`.

When running the program from VSCode, replace `airports.json` and `nav_data.json` on lines `30` and `33` of `generator.py` with their respective full paths on the user's system, or change the dynamic working directory to be that containing `generator.py`.


    Copyright 2020 PH-KDX, Eddie.
    This file is part of FMC Flightplan Generator.

    FMC Flightplan Generator is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    FMC Flightplan Generator is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with FMC Flightplan Generator.  If not, see <https://www.gnu.org/licenses/>.
