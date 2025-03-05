import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, box, mapping, Polygon, MultiPolygon
from shapely import wkt
import os
import argparse
from tqdm import tqdm
import math
import json
import numpy as np
import sys
from rtree import index
import re
import shutil

def download_and_process_data(location, output_folder, divide_immediately=True):
    """
    Download and process Microsoft building footprint data for a specified location.
    """
    print(f"Downloading data for {location}...")
    try:
        dataset_links = pd.read_csv(
            "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
        )
    except Exception as e:
        print(f"Error downloading dataset links: {e}")
        sys.exit(1)

    location_links = dataset_links[dataset_links.Location == location]
    if location_links.empty:
        print(
            f"Error: No data found for '{location}'. Please check the location name and try again."
        )
        print("Available locations:")
        print(", ".join(sorted(dataset_links["Location"].unique())))
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)
    all_data = []
    for _, row in tqdm(
        location_links.iterrows(), total=len(location_links), desc="Processing data"
    ):
        try:
            df = pd.read_json(row.Url, lines=True)
            df["geometry"] = df["geometry"].apply(shape)
            gdf = gpd.GeoDataFrame(df, crs=4326)
            all_data.append(gdf)
        except Exception as e:
            print(f"Error processing data from {row.Url}: {e}")
            continue

    if not all_data:
        print("Error: No data could be processed. Exiting.")
        sys.exit(1)

    combined_gdf = pd.concat(all_data)
    bounds = combined_gdf.total_bounds

    if divide_immediately:
        divide_data(combined_gdf, output_folder, location, bounds)
    else:
        combined_gdf.to_file(f"{output_folder}/{location}.geojson", driver="GeoJSON")


def divide_data(gdf, output_folder, location, bounds):
    """
    Divide a large GeoDataFrame into smaller GeoJSON files based on adaptive grid.
    """
    x_min, y_min, x_max, y_max = bounds
    area = (x_max - x_min) * (y_max - y_min)
    # Aim for approximately 100 chunks
    chunk_area = area / 100
    grid_size = math.sqrt(chunk_area)

    x_ranges = list(np.arange(x_min, x_max, grid_size))
    y_ranges = list(np.arange(y_min, y_max, grid_size))

    metadata = {}
    for x in tqdm(x_ranges, desc="Dividing data"):
        for y in y_ranges:
            cell = box(x, y, min(x + grid_size, x_max), min(y + grid_size, y_max))
            cell_gdf = gdf[gdf.intersects(cell)]

            if not cell_gdf.empty:
                filename = f"{location}_{x:.6f}_{y:.6f}.geojson"
                cell_gdf.to_file(
                    os.path.join(output_folder, filename), driver="GeoJSON"
                )

                # Store chunk coordinates in metadata
                metadata[filename] = {
                    "x_min": x,
                    "y_min": y,
                    "x_max": min(x + grid_size, x_max),
                    "y_max": min(y + grid_size, y_max),
                }

    # Save metadata to a separate file
    with open(os.path.join(output_folder, f"{location}_metadata.json"), "w") as f:
        json.dump(metadata, f)


def extract_data(input_folder, output_file, top_left, bottom_right, extrafields=False):
    if not os.path.isdir(input_folder):
        print(f"Error: The input folder '{input_folder}' does not exist.")
        sys.exit(1)

    # Check if output file already exists
    if os.path.exists(output_file):
        while True:
            response = input(
                f"The file '{output_file}' already exists. Do you want to overwrite it? (y/n): "
            ).lower()
            if response == "y":
                break
            elif response == "n":
                new_name = input("Please enter a new file name: ")
                output_file = (
                    new_name if new_name.endswith(".geojson") else new_name + ".geojson"
                )
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    bbox = box(
        min(top_left[1], bottom_right[1]),
        min(top_left[0], bottom_right[0]),
        max(top_left[1], bottom_right[1]),
        max(top_left[0], bottom_right[0]),
    )

    metadata_file = next(
        (f for f in os.listdir(input_folder) if f.endswith("_metadata.json")), None
    )

    if not metadata_file:
        print("Error: Metadata file not found. Cannot perform efficient extraction.")
        sys.exit(1)

    try:
        with open(os.path.join(input_folder, metadata_file), "r") as f:
            metadata = json.load(f)
    except json.JSONDecodeError:
        print("Error: Invalid metadata file. Cannot perform efficient extraction.")
        sys.exit(1)

    # Create a spatial index
    idx = index.Index()
    for i, (filename, chunk_coords) in enumerate(metadata.items()):
        idx.insert(
            i,
            (
                chunk_coords["x_min"],
                chunk_coords["y_min"],
                chunk_coords["x_max"],
                chunk_coords["y_max"],
            ),
        )

    # Find potentially intersecting files
    intersecting_files = []
    for i in idx.intersection(bbox.bounds):
        filename = list(metadata.keys())[i]
        chunk_coords = metadata[filename]
        if bbox.intersects(
            box(
                chunk_coords["x_min"],
                chunk_coords["y_min"],
                chunk_coords["x_max"],
                chunk_coords["y_max"],
            )
        ):
            intersecting_files.append(filename)

    print(f"Found {len(intersecting_files)} potentially intersecting files.")

    # Create useful fields
    extra_fields = [
        "building",
        "man_made",
        "aeroway",
        "military",
        "tower",
        "bms",
        "power",
        "leisure",
        "religion",
        "sport",
        "barrier",
    ]

    all_features = []
    for filename in tqdm(intersecting_files, desc="Extracting data"):
        file_path = os.path.join(input_folder, filename)
        if not os.path.exists(file_path):
            print(f"Warning: File {filename} not found. Skipping.")
            continue

        try:
            gdf = gpd.read_file(file_path)
            filtered = gdf[gdf.intersects(bbox)]
            for _, row in filtered.iterrows():
                feature = {
                    "type": "Feature",
                    "properties": {"type": "Feature"},
                    "geometry": mapping(row.geometry),
                }

                try:
                    properties_dict = json.loads(row["properties"])
                    feature["properties"].update(properties_dict)
                    if extrafields:
                        for field in extra_fields:
                            feature["properties"][field] = ""
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse properties for a feature. Skipping.")
                    continue
                all_features.append(feature)
        except Exception as e:
            print(f"Error processing file {filename}: {e}")
            continue

    if all_features:
        # Create a GeoDataFrame from the features
        result_gdf = gpd.GeoDataFrame.from_features(all_features)
        # Set the CRS to EPSG:4326 (WGS84)
        result_gdf.set_crs(epsg=4326, inplace=True)
        # Save the GeoDataFrame to a GeoJSON file
        try:
            result_gdf.to_file(output_file, driver="GeoJSON")
        except Exception as e:
            print(f"Error while saving file: {e}")
            return

        print(f"Extracted {len(result_gdf)} buildings to {output_file}")
    else:
        print("No buildings found in the specified area.")


def parse_polygon(polygon_str):
    """Parse a POLYGON or MULTIPOLYGON string into a Shapely geometry object."""
    if isinstance(polygon_str, str):
        try:
            return wkt.loads(polygon_str)
        except:
            coords_str = re.findall(r'\(\((.*?)\)\)', polygon_str)
            if coords_str:
                all_coords = [
                    [tuple(map(float, pair.split())) for pair in coord.split(',')]
                    for coord in coords_str
                ]
                if len(all_coords) == 1:
                    return Polygon(all_coords[0])
                else:
                    return MultiPolygon([Polygon(coords) for coords in all_coords])
            return polygon_str

def load_and_filter_polygons(input_file, output_file, top_left, bottom_right, chunksize=100000, use_chunks=False, extrafields=False):
    """
    Load polygons from chunked GeoJSON files or CSV, filter them based on a bounding box,
    and save the filtered polygons to a new GeoJSON file.
    """
    bb = box(min(top_left[1], bottom_right[1]),
            min(top_left[0], bottom_right[0]),
            max(top_left[1], bottom_right[1]),
            max(top_left[0], bottom_right[0]))

    extra_fields = [
        "building",
        "man_made",
        "aeroway",
        "military",
        "tower",
        "bms",
        "power",
        "leisure",
        "religion",
        "sport",
        "barrier",
    ]
    filtered_polygons = []
    total_processed = 0
    if use_chunks:
        # Working with geographical chunks (GeoJSON files)
        chunk_boundaries = gpd.read_file(os.path.join(input_file, "chunk_boundaries.geojson"))
        relevant_chunks = chunk_boundaries[chunk_boundaries.intersects(bb)]
        with tqdm(total=len(relevant_chunks), desc="Processing chunks") as pbar:
            for _, chunk in relevant_chunks.iterrows():
                chunk_file = os.path.join(input_file, f"chunk_{chunk['chunk_id']}.geojson")
                gdf_chunk = gpd.read_file(chunk_file)
                # Filter polygons within the chunk
                filtered_chunk = gdf_chunk[gdf_chunk.intersects(bb)]
                if extrafields:
                    for field in extra_fields:
                        filtered_chunk[field] = ""
                filtered_polygons.append(filtered_chunk)
                pbar.update(1)
    else:
        # Working with original CSV file
        chunks = pd.read_csv(input_file, chunksize=chunksize, dtype={'geometry': str})
        with tqdm(total=None, desc="Processing CSV chunks") as pbar:
            for chunk in chunks:
                # Convert string representation of polygons to Shapely geometries
                chunk['geometry'] = chunk['geometry'].apply(parse_polygon)
                gdf_chunk = gpd.GeoDataFrame(chunk, geometry='geometry')
                # Drop rows with invalid geometries
                gdf_chunk = gdf_chunk.dropna(subset=['geometry'])
                # Verify CRS
                if gdf_chunk.crs is None:
                    gdf_chunk.set_crs(epsg=4326, inplace=True) # Assuming WGS84, adjust if different
                # Filter polygons within the chunk
                filtered_chunk = gdf_chunk[gdf_chunk.intersects(bb)]
                if extrafields:
                    for field in extra_fields:
                        filtered_chunk[field] = ""
                filtered_polygons.append(filtered_chunk)
                pbar.update(len(chunk))

    # Combine all filtered chunks
    if filtered_polygons:
        final_result = gpd.GeoDataFrame(pd.concat(filtered_polygons, ignore_index=True))
        # Simplify geometries (optional, may reduce precision)
        final_result['geometry'] = final_result['geometry'].simplify(tolerance=0.0001)
        # Write to file (CSV or GeoJSON based on output_file extension)
        if output_file:
            if output_file.lower().endswith('.geojson'):
                final_result.to_file(output_file, driver='GeoJSON')
            else:
                final_result.to_csv(output_file, index=False)

        return final_result
    else:
        print("No polygons found within the specified bounding box.")
        return gpd.GeoDataFrame()

def parse_coordinates(coord_str):
    """Parse a string of coordinates into a tuple of floats."""
    try:
        lat, lon = map(float, coord_str.split(','))
        return (lat, lon)
    except ValueError:
        raise argparse.ArgumentTypeError("Coordinates must be in the format 'latitude,longitude'")

def load_tiles_geojson(file_path='tiles.geojson'):
    """ Load Google's tiles file to understand the regions of the relevant CSV data"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    features = data['features']
    tiles = []
    for feature in features:
        tile = {
            'tile_id': feature['properties']['tile_id'],
            'tile_url': feature['properties']['tile_url'],
            'size_mb': feature['properties']['size_mb'],
            'geometry': Polygon(feature['geometry']['coordinates'][0])
        }
        tiles.append(tile)
    return tiles

def create_geographic_chunks(tile_geometry, num_chunks=1000):
    """Create geographic chunks within the given tile geometry."""
    minx, miny, maxx, maxy = tile_geometry.bounds
    dx = (maxx - minx) / int(num_chunks ** 0.5)
    dy = (maxy - miny) / int(num_chunks ** 0.5)

    chunks = []
    for i in range(int(num_chunks ** 0.5)):
        for j in range(int(num_chunks ** 0.5)):
            chunk_box = box(minx + i * dx, miny + j * dy, minx + (i + 1) * dx, miny + (j + 1) * dy)
            if chunk_box.intersects(tile_geometry):
                chunks.append(chunk_box)
    return chunks

def divide_database(tile_id, override=False, num_chunks=1000):
    """ Divide the CSV buildings footprint database into smaller pieces"""
    tiles = load_tiles_geojson()
    tile = next((t for t in tiles if t['tile_id'] == tile_id), None)

    if not tile:
        print(f"Error: Tile {tile_id} not found in tiles.geojson.")
        return

    file_name = f"{tile_id}_buildings.csv"
    output_folder = f"{tile_id}_chunks"

    if not os.path.exists(file_name):
        print(f"Error: File {file_name} not found.")
        return

    if os.path.exists(output_folder):
        if not override:
            user_input = input(f"Folder {output_folder} already exists. Do you want to override it? (y/n): ")
            if user_input.lower() != 'y':
                print("Operation cancelled.")
                return
        shutil.rmtree(output_folder)

    os.makedirs(output_folder)
    print(f"Dividing {file_name} into geographic chunks. This may take a while for large files...")

    # Create geographic chunks
    chunks = create_geographic_chunks(tile['geometry'], num_chunks)

    # Read the CSV file into a GeoDataFrame
    df = pd.read_csv(file_name)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df['geometry']))

    # Set the CRS if it's not already set
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True) # Assuming WGS84, adjust if different

    # Process each chunk
    for i, chunk in enumerate(tqdm(chunks, desc="Processing chunks")):
        chunk_gdf = gdf[gdf.intersects(chunk)]
        if not chunk_gdf.empty:
            chunk_gdf.to_file(f"{output_folder}/chunk_{i}.geojson", driver='GeoJSON')

    # Save chunk boundaries as a single GeoJSON file
    chunk_boundaries = gpd.GeoDataFrame(geometry=chunks)
    chunk_boundaries['chunk_id'] = range(len(chunks))
    chunk_boundaries.to_file(f"{output_folder}/chunk_boundaries.geojson", driver="GeoJSON")

    print(f"Database divided into chunks in folder: {output_folder}")

def main():
    parser = argparse.ArgumentParser(
        description="Process Microsoft Global ML Building Footprints or Google Building Footprint Data"
    )

    # mutually exclusive group for selecting processing mode
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-m",
        "--microsoft",
        action="store_true",
        help="Enable Microsoft Global Building Footprints mode",
    )
    group.add_argument(
        "-g",
        "--google",
        action="store_true",
        help="Enable Google Building Footprint Processor mode",
    )

    # Microsoft arguments
    parser.add_argument(
        "-d", "--download", type=str, help="Download data for specified location"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output",
        help="Output folder for download and divide operations",
    )
    parser.add_argument(
        "-dv-m", "--divide_m", action="store_true", help="Divide data immediately after download"
    )
    parser.add_argument(
        "-ex", "--extract", action="store_true", help="Extract data from downloaded files"
    )
    parser.add_argument(
        "-i-m", "--input_m", type=str, help="Input folder containing GeoJSON files for extraction"
    )
    parser.add_argument(
        "-o-m", "--output_m",
        type=str,
        default="cropped_file.geojson",
        help="Output file for extracted data",
    )
    parser.add_argument("-tl-m", "--top-left_m", type=str, help="Top-left coordinates (lat,lon)")
    parser.add_argument(
        "-br-m", "--bottom-right_m", type=str, help="Bottom-right coordinates (lat,lon)"
    )
    parser.add_argument('-ef-m', '--extrafields_m', action='store_true', help="Add useful fields to the output GeoJSON")

    # Google arguments
    parser.add_argument('-i-g', '--input_g', help="Input CSV file or chunk folder for Google data")
    parser.add_argument('-o-g', '--output_g', default='cropped_buildings.geojson', help="Output file (default: cropped_buildings.geojson) for Google data")
    parser.add_argument('-tl-g', '--top-left_g', type=parse_coordinates, help="Top-left coordinates of the bounding box (latitude,longitude) for Google data")
    parser.add_argument('-br-g', '--bottom-right_g', type=parse_coordinates, help="Bottom-right coordinates of the bounding box (latitude,longitude) for Google data")
    parser.add_argument('--fromdb', action='store_true', help="Use the tiled database approach")
    parser.add_argument('-dv-g', '--divide_g', type=str, help="Divide the specified tile_id into chunks")
    parser.add_argument('-ov', '--override', action='store_true', help="Override existing chunk folders")
    parser.add_argument('-ef-g', '--extrafields_g', action='store_true',
                        help="Add useful fields to the output GeoJSON for google")

    args = parser.parse_args()

    if args.microsoft:
        if args.download:
            download_and_process_data(args.download, args.output_m, args.divide_m)
        if args.extract:
            if not (args.input_m and args.top_left_m and args.bottom_right_m):
                parser.error("--input, --top-left_m, and --bottom-right_m are required for extraction")
            try:
                top_left = list(map(float, args.top_left_m.split(',')))
                bottom_right = list(map(float, args.bottom_right_m.split(',')))
                extract_data(args.input_m, args.output_m, top_left, bottom_right, args.extrafields_m)
            except ValueError:
                parser.error("--top-left_m and --bottom-right_m must be in the format lat,lon")


    elif args.google:
        if args.divide_g:
            divide_database(args.divide_g, override=args.override)
        elif args.input_g and args.output_g and args.top_left_g and args.bottom_right_g:
            use_chunks = args.fromdb
            input_file = args.input_g
            output_file = args.output_g
            top_left = args.top_left_g
            bottom_right = args.bottom_right_g

            if use_chunks:
                if not os.path.isdir(input_file):
                    print(f"Error: {input_file} is not a directory. When using --fromdb, input should be a chunk folder.")
                    return
            else:
                if not os.path.isfile(input_file):
                    print(f"Error: {input_file} is not a file. When not using --fromdb, input should be a CSV file.")
                    return

            filtered_polygons = load_and_filter_polygons(input_file, output_file, top_left, bottom_right, use_chunks=use_chunks, extrafields=args.extrafields_g)

            num_filtered = len(filtered_polygons)
            if num_filtered > 0:
                print(f"Operation completed successfully. {num_filtered} polygons were cropped and exported to {output_file}")
            else:
                print(f"Operation completed, but no polygons were found within the specified bounding box. The output file {output_file} is empty.")
        else:
            parser.error("For Google filtering operations, the following arguments are required: -i/--input_g, -o/--output_g, --top-left_g, --bottom-right_g")

if __name__ == "__main__":
    main()
