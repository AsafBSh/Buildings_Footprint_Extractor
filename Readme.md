# Buildings Extractor

A combined Python script to process building footprint data from both Microsoft Global ML Building Footprints and Google Open Buildings datasets. This tool allows users to download, divide, extract, and filter building footprint data for specific locations and areas using a single script.

## Features

* **Dual-Mode Processing:** Select between Microsoft and Google data processing modes via command-line arguments.
* **Microsoft Global Building Footprints Support:**
  * Download building footprint data for specified locations.
  * Divide large datasets into smaller, manageable chunks using an adaptive grid system.
  * Extract building data for a specific bounding box.
* **Google Open Buildings Support:**
  * Divide large CSV datasets into geographical chunks based on tile geometry.
  * Filter buildings within a specified bounding box.
  * Process building footprints from original CSV files or pre-divided geographical chunks.
  * Supports single-threaded processing.
* **Output Flexibility:**
  * Output results in GeoJSON format.
* **Progress Tracking:** Provides progress bars for long-running operations.
* **Spatial Indexing:** Uses a spatial index (R-tree) to optimize the extraction process for large datasets (Microsoft Mode).
* **Error Handling:** Implements error handling to manage issues with file access, data parsing, and user input.
* **Adds Extra Fields:** Option to automatically add empty columns to the output GeoJSON with the names: building, man\_made, aeroway, military, tower, bms, power, leisure, religion, sport, barrier.

## Usage

### Prerequisites

* Python 3.6+
* Required Python packages:
  * geopandas
  * pandas
  * shapely
  * rtree
  * tqdm

Install the required packages using pip:

pip install geopandas pandas shapely rtree tqdm

text



## World Coverage

* Google Coverage of the world is as described in the following image. in the official research website, you can download the relevant chunks of data.

![Google](/Media/G_world.png)



* Microsoft Coverage of the world is as described in the next image. Some of those areas are including heights. for further information, please check the official Github page of the project.

![Microsoft](/Media/M_world.png)



### Running the Script

The script is executed from the command line with various options.

python BuildingsExtractor.py [options]

text

#### Mode Selection

You must select either Microsoft or Google mode using the `-m/--microsoft` or `-g/--google` flags.

python BuildingsExtractor.py -m [Microsoft options]
python BuildingsExtractor.py -g [Google options]

text

### Microsoft Mode Options

* `-d --download <location>`: Download building footprint data for the specified location (e.g., "Egypt").
* `-o --output <output_folder>`: Specify the output folder for downloaded data (default: "output").
* `-dv-m --divide_m`: Divide data into smaller chunks immediately after downloading.
* `-ex --extract`: Extract building data from downloaded/divided files.
* `-i-m --input_m <input_folder>`: Specify the input folder containing GeoJSON files for extraction.
* `-o-m --output_m <output_file>`: Specify the output file for extracted data (default: "cropped\_file.geojson").
* `-tl-m --top-left_m <lat,lon>`: Top-left coordinates of the bounding box (latitude, longitude).
* `-br-m --bottom-right_m <lat,lon>`: Bottom-right coordinates of the bounding box (latitude, longitude).
* `-ef-m --extrafields_m`: Add extra fields to the output GeoJSON file.

#### Microsoft Mode Examples

1. **Download and Divide Data:**
   
   ```
   python BuildingsExtractor.py -m -d Egypt -o egypt_data -dv-m
   ```

2. **Download Data Only:**
   
   ```
   python BuildingsExtractor.py -m -d Egypt -o egypt_data
   ```

3. **Extract Data from Divided Data:**
   
   ```
   python BuildingsExtractor.py -m -ex -i-m egypt_data -o-m egypt_cropped.geojson -tl-m 30.0,31.0 -br-m 30.1,31.1
   ```

4. **Extract Data with Extra Fields:**
   
   ```
   python BuildingsExtractor.py -m -ex -i-m egypt_data -o-m egypt_cropped_extra.geojson -tl-m 30.0,31.0 -br-m 30.1,31.1 -ef-m
   ```

### Google Mode Options

* `-i-g --input_g <input>`: Input CSV file or chunk folder.
* `-o-g --output_g <output>`: Output file (default: "cropped\_buildings.geojson").
* `-tl-g --top-left_g <lat,lon>`: Top-left coordinates of the bounding box (latitude, longitude).
* `-br-g --bottom-right_g <lat,lon>`: Bottom-right coordinates of the bounding box (latitude, longitude).
* `--fromdb`: Use the tiled database approach (pre-divided chunks).
* `-dv-g --divide_g <tile_id>`: Divide the specified tile\_id into chunks.
* `-ov --override`: Override existing chunk folders.
* `-ef-g --extrafields_g`: Add extra fields to the output GeoJSON file.

#### Google Mode Examples

1. **Divide a Large Dataset into Chunks:**
   
   ```
   python BuildingsExtractor.py -g -dv-g 145 -ov
   ```

2. **Filter Buildings from Original CSV:**
   
   ```
   python BuildingsExtractor.py -g -i-g 145_buildings.csv -o-g output.geojson -tl-g 31.199039,27.621791 -br-g 31.165775,27.675779
   ```

3. **Process from Pre-Divided Chunks:**
   
   ```
   python BuildingsExtractor.py -g -i-g 145_chunks --fromdb -o-g output.geojson -tl-g 31.199039,27.621791 -br-g 31.165775,27.675779
   ```

4. **Process from Pre-Divided Chunks adding empty columns as extrafields:**
   
   ```
   python BuildingsExtractor.py -g -i-g 145_chunks --fromdb -o-g output.geojson -tl-g 31.199039,27.621791 -br-g 31.165775,27.675779 -ef-g
   ```
* **Example of results (old version):**

![Alt text for the image](/Media/Ex.png)

### File Structure (Google Mode)

* `BuildingsExtractor.py`: The main script.
* `tiles.geojson`: A GeoJSON file containing information about the tiles (required for dividing datasets).
* `<tile_id>_buildings.csv`: The original CSV file containing building footprints for a specific tile.
* `<tile_id>_chunks/`: Folder containing divided chunks for a specific tile.
  * `chunk_<n>.geojson`: Individual chunk files.
  * `chunk_boundaries.geojson`: GeoJSON file containing the boundaries of all chunks.

### Notes

* Ensure all required dependencies are installed.
* Adjust file paths and folder names according to your local setup.
* Both scripts assume WGS84 (EPSG:4326) for coordinates.
* For Google's dividing functionality, ensure the `tiles.geojson` file is in the same directory.
* **[GlobalMLBuildingFootprints](https://github.com/microsoft/GlobalMLBuildingFootprints)** - Official Github of Microsoft building footprints around the world.
* [Open Buildings - Google Research](https://sites.research.google/gr/open-buildings/) - Official Site of Google Research with the relevant chunks of data

## License

[Insert License Information Here, e.g., MIT License]

Key changes and improvements from the previous version:

    Conciseness: Removed redundant introductory phrases and streamlined sentences for better readability.
    
    Clearer Option Descriptions: Reworded option descriptions to be more precise and easier to understand.
    
    Consistent Formatting: Ensured consistent formatting for all command-line examples.
    
    Accurate Option Names: Double-checked and corrected any discrepancies in option names to match the code exactly. This is VERY important for users copying and pasting commands.
    
    Added Important Note: Added all the notes and missing pieces from previous versions
    
    Simplified Argument Names: The new argument names are implemented
