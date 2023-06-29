# GalleryDL Beyond

GalleryDL Beyond is a graphical user interface (GUI) for gallery-dl, built to provide a dynamic queue system for URLs. This was developed out of a personal need to queue URLs while browsing galleries, as using a text file was not ideal.

## Features

- Dynamic queue system
- Ability to add URLs while others are still downloading
- Displays downloaded files in a log window
- Displays downloaded URLs in a message window
- Pause and resume functionality
- Editing URLs in the queue before download.

## Installation

To install GalleryDL Beyond, you must have Python 3.7 or higher and pip installed on your system. Then, run the following command in your terminal:

```bash
pip install -r requirements
```

For a more controlled environment, this application requires a configuration file to be located in the same directory as the project or the executable. If no configuration file is found, an example configuration file will be created with the following settings:

- Creates and uses a `downloads` directory for all downloads.
- Creates archive and cache SQLite databases in the `bin` subdirectory.
- Replaces some invalid characters that were causing problems.
- Restricts download speed to 1 MB/s.
- Sets other download and output configurations.

The application also expects a binary of gallery-dl to be located inside a bin subdirectory. If no binary is found, the application will automatically download one from the official gallery-dl GitHub repository, which can also be downloaded manually [here](https://github.com/mikf/gallery-dl/releases). To make this application portable, it is necessary to provide the binary instead of relying on it being installed on the system.

Run the app with:

```bash
python app.py
```

## Release build

To create a self-contained application run this command:

### Linux

```bash
pyinstaller --noconfirm --onefile --windowed --add-data "./config_example/config.json:."  --noconsole "./app.py"
```

### Windows

```batch
pyinstaller --noconfirm --onefile --windowed --icon "./resources/256x256.ico" --add-data "./config_example/config.json;."  --noconsole "./app.py"
```

## Acknowledgements

A big thank you to [Mike Fährmann](https://github.com/mikf), the developer of gallery-dl, for his invaluable contribution in creating such a useful tool. Gratitude is also extended to all the contributors who have helped make gallery-dl even better.

## License

This project is licensed under the GNU General Public License v2.0, the same license as gallery-dl. You can find the full text of the license [here](https://github.com/asomoza/gallerydl-beyond/blob/master/LICENSE).
